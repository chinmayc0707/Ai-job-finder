"""
rag/rag_engine.py
─────────────────
RAG pipeline for AI Job Finder.

The LLM receives retrieved job context and produces STRUCTURED output:
  - answer         : the text response shown to the user
  - cited_job_ids  : list of job IDs the LLM explicitly chose to recommend

Only jobs the LLM decided to mention appear as citation cards — not the
full retrieval set.

Supports pluggable LLMs (openai | openrouter | google | anthropic | groq)
via LLM_PROVIDER env var, and pluggable embeddings via EMBEDDING_PROVIDER.
"""

import os
import logging
import re
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
logger = logging.getLogger(__name__)


# ─── Pinecone vector store (lazy singleton) ───────────────────────────────────
_vectorstore = None

def _get_vectorstore():
    """Lazy-init the Pinecone vectorstore."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    from pinecone import Pinecone
    from langchain_pinecone import PineconeVectorStore
    from rag.embeddings import get_embeddings

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    index_name = os.getenv("PINECONE_INDEX_NAME", "ai-job-finder")
    index = pc.Index(index_name)
    embeddings = get_embeddings()

    _vectorstore = PineconeVectorStore(index=index, embedding=embeddings)
    return _vectorstore


def _job_to_document(job) -> Document:
    """Convert a Job ORM record into a LangChain Document."""
    content = (
        f"Job Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n"
        f"Salary: {job.salary or 'Not specified'}\n"
        f"Type: {job.job_type}\n"
        f"Description: {job.description or 'No description provided.'}"
    )
    metadata = {
        "job_id": int(job.id),
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary": job.salary or "Not specified",
        "job_type": job.job_type,
    }
    return Document(page_content=content, metadata=metadata)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#]+", (text or "").lower())
        if len(token) > 2
    }


def _extract_resume_from_history(chat_history: list[dict]) -> str:
    """Pull resume/profile text from earlier user messages."""
    resume_markers = (
        "here's my resume",
        "here is my resume",
        "my resume:",
        "resume:",
        "evaluate my profile",
    )
    chunks: list[str] = []

    for msg in chat_history:
        if msg.get("role") != "user":
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        lowered = content.lower()
        if any(marker in lowered for marker in resume_markers) or len(content) > 400:
            chunks.append(content)

    return "\n\n".join(chunks)


def _build_profile_context(
    question: str,
    chat_history: list[dict] | None = None,
    resume_text: str | None = None,
) -> str:
    """Combine uploaded resume, pasted profile, and chat history into one profile block."""
    parts: list[str] = []

    if resume_text and resume_text.strip():
        parts.append(resume_text.strip())

    history_profile = _extract_resume_from_history(chat_history or [])
    if history_profile and history_profile not in parts:
        parts.append(history_profile)

    profile = "\n\n".join(parts).strip()
    if not profile:
        return "No resume or profile provided yet."

    # Keep the profile block bounded for the LLM prompt.
    if len(profile) > 6000:
        profile = profile[:6000] + "\n...[profile truncated]"
    return profile


def _build_retrieval_query(
    question: str,
    chat_history: list[dict] | None = None,
    resume_text: str | None = None,
) -> str:
    """
    Build the semantic-search query from BOTH the user's prompt and resume/profile.
    This is what gets embedded for Pinecone / keyword fallback retrieval.
    """
    profile = _build_profile_context(question, chat_history, resume_text)
    sections = [f"Job search request: {question.strip()}"]

    if profile != "No resume or profile provided yet.":
        # Use a larger slice for retrieval than for the LLM prompt.
        profile_for_search = profile[:3000]
        sections.insert(0, f"Candidate skills and experience:\n{profile_for_search}")

    return "\n\n".join(sections)


def _jobs_from_database(search_query: str, limit: int = 10) -> list[Document]:
    """
    Fallback retrieval: load all jobs from the database, convert to Documents,
    and return the top `limit` matches based on keyword scoring.
    """
    from models import SessionLocal, Job

    session = SessionLocal()
    try:
        jobs = session.query(Job).all()
    finally:
        session.close()

    docs = [_job_to_document(job) for job in jobs]

    tokens = _tokenize(search_query)
    if not tokens:
        return docs[:limit]

    def score(doc: Document) -> int:
        haystack = (
            f"{doc.page_content} "
            f"{doc.metadata.get('title', '')} "
            f"{doc.metadata.get('company', '')} "
            f"{doc.metadata.get('location', '')}"
        ).lower()
        return sum(1 for token in tokens if token in haystack)

    ranked = sorted(docs, key=score, reverse=True)
    matched = [doc for doc in ranked if score(doc) > 0]
    return (matched or ranked)[:limit]


def _retrieve_jobs(
    question: str,
    chat_history: list[dict] | None = None,
    resume_text: str | None = None,
) -> list[Document]:
    """Retrieve relevant job docs using resume + prompt, via Pinecone with DB fallback."""
    search_query = _build_retrieval_query(question, chat_history, resume_text)
    has_profile = resume_text or _extract_resume_from_history(chat_history or [])
    top_k = 12 if has_profile else 10

    if os.environ.get("PINECONE_API_KEY"):
        try:
            vectorstore = _get_vectorstore()
            retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": top_k},
            )
            docs = retriever.invoke(search_query)
            if docs:
                return docs
            logger.warning("Pinecone returned no matching documents; falling back to database.")
        except Exception as exc:
            logger.warning("Pinecone retrieval failed; falling back to database: %s", exc)

    return _jobs_from_database(search_query, limit=top_k)


# ─── Pluggable LLM factory ────────────────────────────────────────────────────
def _get_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model_name = os.getenv("LLM_MODEL_NAME", "")
    import httpx
    http_client = httpx.Client(verify=False)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or "gpt-4o-mini",
            temperature=0.2,
            api_key=os.getenv("OPENAI_API_KEY"),
            http_client=http_client,
        )
    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or "meta-llama/llama-3.1-8b-instruct:free",
            temperature=0.2,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            request_timeout=90,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5000"),
                "X-Title": os.getenv("OPENROUTER_SITE_NAME", "AI Job Finder"),
            },
            http_client=http_client,
        )
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-1.5-flash",
            temperature=0.2,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name or "claude-3-haiku-20240307",
            temperature=0.2,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            http_client=http_client,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name or "llama-3.1-8b-instant",
            temperature=0.2,
            groq_api_key=os.getenv("GROQ_API_KEY"),
            http_client=http_client,
        )
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {provider!r}. "
            "Choose from: openai, openrouter, google, anthropic, groq"
        )


# ─── Format retrieved docs for the prompt ────────────────────────────────────
def _format_jobs(docs: list[Document]) -> str:
    """Render retrieved job docs into a readable block with IDs clearly labelled."""
    if not docs:
        return "No matching jobs found in the database."
    parts = []
    for doc in docs:
        meta = doc.metadata
        parts.append(
            f"--- Job ID: {meta.get('job_id')} ---\n"
            f"{doc.page_content}"
        )
    return "\n\n".join(parts)


def _clean_answer(text: str) -> str:
    """
    Safety net: if the LLM returned raw JSON instead of plain text,
    extract just the 'answer' field so the user never sees raw JSON.
    """
    import json
    text = text.strip()
    # Strip ```json ... ``` fence if present
    fenced = re.match(r'^```(?:json)?\s*([\s\S]+?)\s*```$', text)
    candidate = fenced.group(1) if fenced else text
    if candidate.lstrip().startswith('{'):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and isinstance(data.get('answer'), str):
                return data['answer']
        except (json.JSONDecodeError, ValueError):
            pass
    return text


def _extract_cited_job_ids(text: str) -> list[int]:
    """
    Try to extract cited_job_ids from the LLM's text response.
    Handles JSON blocks, fenced JSON, or inline JSON fragments.
    """
    import json

    # Look for the last ```json ... ``` block in the text (the citation block)
    fenced_blocks = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    for block in reversed(fenced_blocks):
        try:
            data = json.loads(block)
            if isinstance(data, dict) and 'cited_job_ids' in data:
                return [int(x) for x in data['cited_job_ids']]
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    # Fallback: look for cited_job_ids anywhere in the text
    match = re.search(r'cited_job_ids["\s:]*\[([^\]]*)\]', text)
    if match:
        try:
            return [int(x.strip()) for x in match.group(1).split(',') if x.strip()]
        except (ValueError, TypeError):
            pass
    return []


# ─── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are an AI career assistant for a job portal called AI Job Finder.

Your role is to help users find the right jobs by evaluating their skills, \
experience, and resume against the available job listings, while also honoring \
their stated preferences (role type, location, salary, remote/on-site, etc.).

USER PROFILE (resume, skills, and background):
{profile}

STRICT RULES — follow these without exception:
1. You may ONLY recommend or mention jobs that appear in the CONTEXT section below.
2. Do NOT invent, guess, or hallucinate any job titles, companies, salaries, or descriptions.
3. Match jobs using BOTH the user's profile/resume AND their current request \
   (for example: skills from the resume + "remote React roles" from the prompt).
4. If no jobs in the context match the user's profile and request, say:
   "I'm sorry, there are no matching jobs available right now. Please check back later \
or broaden your search criteria."
5. When recommending jobs, always mention the exact Job Title, Company, Location, \
and Salary (as shown in the context).
6. Assess job fit for the user — highlight strengths, potential gaps, and growth areas \
based on their profile and preferences.
7. Be professional, encouraging, and concise — like a knowledgeable career advisor.
8. Format your response in **Markdown** (headings, bullet lists, bold for job titles, etc.).
9. Do NOT answer questions unrelated to jobs, careers, or professional development.
10. At the END of your response, include a JSON block listing the IDs of jobs you \
referenced or recommended. Format it exactly like this:
```json
{{"cited_job_ids": [1, 2, 3]}}
```
If you did not cite any jobs, use an empty list: {{"cited_job_ids": []}}

CONTEXT (available job listings):
{context}"""


def _docs_to_jobs(cited_ids: list[int], doc_lookup: dict, doc_content_lookup: dict) -> list[dict]:
    jobs = []
    for jid in cited_ids:
        meta = doc_lookup.get(jid, {})
        description = ""
        content = doc_content_lookup.get(jid, "")
        desc_match = re.search(r"Description:\s*(.+)", content, re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()

        jobs.append({
            "id": jid,
            "title": meta.get("title", ""),
            "company": meta.get("company", ""),
            "location": meta.get("location", ""),
            "salary": meta.get("salary", "Not specified"),
            "type": meta.get("job_type", "Full-time"),
            "description": description,
        })
    return jobs


def _resolve_cited_jobs(
    raw_answer: str,
    answer: str,
    docs: list[Document],
    doc_lookup: dict[int, dict],
    doc_content_lookup: dict[int, str],
    *,
    has_profile: bool,
) -> list[dict]:
    """Map LLM citations to job cards, with retrieval fallback when needed."""
    cited_ids = _extract_cited_job_ids(raw_answer)
    cited_ids = [jid for jid in cited_ids if jid in doc_lookup]

    if not cited_ids:
        cited_ids = [
            jid for jid, meta in doc_lookup.items()
            if meta.get("title", "").lower() in answer.lower()
        ]

    # When the user shared a profile/resume or asked for matches, surface top
    # retrieved jobs if the model forgot the citation JSON block.
    if not cited_ids and docs and has_profile:
        cited_ids = [
            int(doc.metadata["job_id"])
            for doc in docs[:5]
            if doc.metadata.get("job_id") is not None
        ]

    return _docs_to_jobs(cited_ids, doc_lookup, doc_content_lookup)


# ─── Public API ───────────────────────────────────────────────────────────────
def ask(
    question: str,
    chat_history: list[dict] | None = None,
    resume_text: str | None = None,
) -> dict:
    """
    Run the RAG pipeline (non-streaming).

    Args:
        question:     The user's question string.
        chat_history: List of dicts [{"role": "user"|"assistant", "content": "..."}]
        resume_text:  Uploaded or pasted resume text (kept across follow-up turns).

    Returns:
        {
            "answer": str,
            "jobs": [{"id", "title", "company", "location", "salary", "type", "description"}, ...]
        }
    """
    chat_history = chat_history or []
    profile = _build_profile_context(question, chat_history, resume_text)
    has_profile = profile != "No resume or profile provided yet."

    docs = _retrieve_jobs(question, chat_history, resume_text)

    doc_lookup: dict[int, dict] = {}
    doc_content_lookup: dict[int, str] = {}
    for doc in docs:
        jid = doc.metadata.get("job_id")
        if jid is not None:
            doc_lookup[int(jid)] = doc.metadata
            doc_content_lookup[int(jid)] = doc.page_content

    context = _format_jobs(docs)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    lc_history = []
    for msg in chat_history:
        if msg.get("role") == "user":
            lc_history.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            lc_history.append(AIMessage(content=msg["content"]))

    invoke_input = {
        "profile": profile,
        "context": context,
        "input": question,
        "chat_history": lc_history,
    }

    llm = _get_llm()
    chain = prompt | llm
    result = chain.invoke(invoke_input)

    raw_answer = (
        result.content if hasattr(result, "content") else str(result)
    )

    answer = _clean_answer(raw_answer)
    jobs = _resolve_cited_jobs(
        raw_answer,
        answer,
        docs,
        doc_lookup,
        doc_content_lookup,
        has_profile=has_profile,
    )

    return {"answer": answer, "jobs": jobs}


def ask_stream(
    question: str,
    chat_history: list[dict] | None = None,
    resume_text: str | None = None,
):
    """
    Streaming RAG pipeline. Yields dicts:
      {"token": str}                                           — for each LLM token
      {"done": True, "jobs": [...], "full_answer": str}        — final event
    """
    chat_history = chat_history or []
    profile = _build_profile_context(question, chat_history, resume_text)
    has_profile = profile != "No resume or profile provided yet."

    docs = _retrieve_jobs(question, chat_history, resume_text)
    doc_lookup: dict[int, dict] = {}
    doc_content_lookup: dict[int, str] = {}
    for doc in docs:
        jid = doc.metadata.get("job_id")
        if jid is not None:
            doc_lookup[int(jid)] = doc.metadata
            doc_content_lookup[int(jid)] = doc.page_content
    context = _format_jobs(docs)

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    lc_history = []
    for msg in chat_history:
        if msg.get("role") == "user":
            lc_history.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            lc_history.append(AIMessage(content=msg["content"]))

    invoke_input = {
        "profile": profile,
        "context": context,
        "input": question,
        "chat_history": lc_history,
    }

    llm = _get_llm()
    messages = list(prompt.format_messages(**invoke_input))

    full_raw = ""
    for chunk in llm.stream(messages):
        token = chunk.content if hasattr(chunk, "content") else ""
        if token:
            full_raw += token
            yield {"token": token}

    answer = _clean_answer(full_raw)
    jobs = _resolve_cited_jobs(
        full_raw,
        answer,
        docs,
        doc_lookup,
        doc_content_lookup,
        has_profile=has_profile,
    )

    yield {"done": True, "jobs": jobs, "full_answer": answer}
