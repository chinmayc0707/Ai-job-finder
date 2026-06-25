"""
rag/indexer.py
──────────────
Indexes all jobs from the application database into Pinecone.

Each job becomes one vector with rich text content for semantic search,
and metadata (job_id, title, company, location, salary, job_type)
returned as citations.

Usage:
    python rag/indexer.py                      # run directly
    from rag.indexer import index_all_jobs      # call from app
"""

import os
import sys

# Allow running directly from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from rag.embeddings import get_embeddings, get_embedding_dimension
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec


def _get_embeddings():
    return get_embeddings()


def _get_or_create_index(pc: "Pinecone", index_name: str):
    """Create the Pinecone index, or recreate it if the dimension doesn't match."""
    import time
    dimension = get_embedding_dimension()
    existing_names = [idx.name for idx in pc.list_indexes()]

    if index_name in existing_names:
        # Check existing index dimension against what our embedding provider needs
        existing_index = pc.Index(index_name)
        try:
            stats = existing_index.describe_index_stats()
            existing_dim = stats.get("dimension", None)
        except Exception:
            existing_dim = None

        if existing_dim and existing_dim != dimension:
            print(f"[indexer] ⚠  Dimension mismatch detected!")
            print(f"[indexer]    Index '{index_name}' has {existing_dim} dims")
            print(f"[indexer]    Embedding provider needs {dimension} dims")
            print(f"[indexer]    Deleting and recreating index...")
            pc.delete_index(index_name)
            # Wait for Pinecone to finish deletion
            for i in range(12):
                time.sleep(5)
                remaining = [idx.name for idx in pc.list_indexes()]
                if index_name not in remaining:
                    break
                print(f"[indexer]    Waiting for deletion... ({(i+1)*5}s)")
            print(f"[indexer]    Old index deleted.")
        else:
            print(f"[indexer] Index '{index_name}' exists with correct dimension ({dimension}).")
            return existing_index

    print(f"[indexer] Creating Pinecone index '{index_name}' (dim={dimension})...")
    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    # Wait for index to be ready
    for i in range(12):
        time.sleep(5)
        try:
            idx = pc.Index(index_name)
            idx.describe_index_stats()
            break
        except Exception:
            print(f"[indexer]    Waiting for index to be ready... ({(i+1)*5}s)")
    print(f"[indexer] Index '{index_name}' ready.")
    return pc.Index(index_name)


def _job_to_document(job) -> Document:
    """Convert a Job record (ORM object) into a LangChain Document."""
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


def index_all_jobs():
    """
    Index all jobs from the database into Pinecone.

    Queries all Job records via SessionLocal and upserts them as vectors.
    """
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "ai-job-finder")

    if not api_key:
        raise RuntimeError("PINECONE_API_KEY not set in environment/.env")

    pc = Pinecone(api_key=api_key)
    index = _get_or_create_index(pc, index_name)
    embeddings = _get_embeddings()

    from models import SessionLocal, Job
    session = SessionLocal()
    try:
        jobs = session.query(Job).all()
        return _do_index(index, index_name, embeddings, jobs)
    finally:
        session.close()


def _do_index(index, index_name, embeddings, jobs):
    if not jobs:
        print("[indexer] No jobs found in database.")
        return 0

    print(f"[indexer] Indexing {len(jobs)} jobs...")

    # Clear existing vectors and re-index fresh
    try:
        index.delete(delete_all=True)
        print("[indexer] Cleared existing vectors.")
    except Exception as e:
        print(f"[indexer] Note: could not clear index (may be empty): {e}")

    docs = [_job_to_document(j) for j in jobs]
    ids = [f"job_{j.id}" for j in jobs]

    vectorstore = PineconeVectorStore(index=index, embedding=embeddings)
    vectorstore.add_documents(docs, ids=ids)

    print(f"[indexer] ✓ Successfully indexed {len(docs)} jobs into '{index_name}'.")
    return len(docs)


def index_single_job(job_dict: dict):
    """
    Upsert a single job into Pinecone (for add/edit operations).

    Args:
        job_dict: A dict from Job.to_dict() with keys:
                  id, title, company, location, salary, type, description, etc.
    """
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "ai-job-finder")

    if not api_key:
        print("[indexer] PINECONE_API_KEY not set — skipping vector upsert.")
        return

    pc = Pinecone(api_key=api_key)
    index = _get_or_create_index(pc, index_name)
    embeddings = _get_embeddings()

    # Build a Document from the dict (adapting keys from to_dict())
    content = (
        f"Job Title: {job_dict.get('title', '')}\n"
        f"Company: {job_dict.get('company', '')}\n"
        f"Location: {job_dict.get('location', '')}\n"
        f"Salary: {job_dict.get('salary', 'Not specified')}\n"
        f"Type: {job_dict.get('type', 'Full-time')}\n"
        f"Description: {job_dict.get('description', 'No description provided.')}"
    )
    metadata = {
        "job_id": int(job_dict["id"]),
        "title": job_dict.get("title", ""),
        "company": job_dict.get("company", ""),
        "location": job_dict.get("location", ""),
        "salary": job_dict.get("salary", "Not specified"),
        "job_type": job_dict.get("type", "Full-time"),
    }
    doc = Document(page_content=content, metadata=metadata)

    vectorstore = PineconeVectorStore(index=index, embedding=embeddings)
    vectorstore.add_documents([doc], ids=[f"job_{job_dict['id']}"])
    print(f"[indexer] Upserted job {job_dict['id']} ({job_dict.get('title', '')}).")


def delete_job_vector(job_id: int):
    """Remove a job's vector from Pinecone (call on job delete)."""
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "ai-job-finder")

    if not api_key:
        print("[indexer] PINECONE_API_KEY not set — skipping vector delete.")
        return

    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    index.delete(ids=[f"job_{job_id}"])
    print(f"[indexer] Deleted vector for job {job_id}.")


if __name__ == "__main__":
    count = index_all_jobs()
    print(f"[indexer] Done. {count} jobs indexed.")
