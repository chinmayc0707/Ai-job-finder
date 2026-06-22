import re

with open('templates/index.html', 'r') as f:
    content = f.read()

chatbot_ui_html = """
  <!-- Chatbot Modal -->
  <div class="chatbot-modal" id="chatbotModal">
    <div class="chatbot-header">
      <div class="chatbot-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px;"><path d="M12 8V4H8"></path><rect width="16" height="12" x="4" y="8" rx="2"></rect><path d="M2 14h2"></path><path d="M20 14h2"></path><path d="M15 13v2"></path><path d="M9 13v2"></path></svg>
        AI Career Assistant
      </div>
      <button class="chatbot-close" id="chatbotClose">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
    </div>
    <div class="chatbot-messages" id="chatbotMessages">
      <div class="chatbot-message bot">
        Hello! I'm your AI career assistant. How can I help you today?
      </div>
    </div>
    <div class="chatbot-input-area">
      <input type="text" class="chatbot-input" id="chatbotInput" placeholder="Type a message..." autocomplete="off" />
      <button class="chatbot-send" id="chatbotSend">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
      </button>
    </div>
  </div>

  <style>
    /* Chatbot Modal Styles */
    .chatbot-modal {
      position: fixed;
      bottom: 90px; /* Above the FAB */
      right: 24px;
      width: 350px;
      height: 500px;
      max-height: calc(100vh - 120px);
      background: var(--surface-card);
      border: 1px solid var(--hairline);
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.6);
      display: flex;
      flex-direction: column;
      z-index: 1000;
      opacity: 0;
      transform: translateY(20px) scale(0.95);
      pointer-events: none;
      transition: opacity 0.3s ease, transform 0.3s ease;
      overflow: hidden;
    }

    .chatbot-modal.active {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }

    .chatbot-header {
      padding: var(--sp-md);
      background: var(--surface-elev);
      border-bottom: 1px solid var(--hairline);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .chatbot-title {
      font-weight: 700;
      display: flex;
      align-items: center;
      color: var(--on-dark);
    }

    .chatbot-close {
      background: none;
      border: none;
      color: var(--muted);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 4px;
      border-radius: 4px;
      transition: background 0.2s, color 0.2s;
    }

    .chatbot-close:hover {
      background: var(--hairline);
      color: var(--on-dark);
    }

    .chatbot-messages {
      flex: 1;
      padding: var(--sp-md);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: var(--sp-sm);
    }

    .chatbot-message {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 0.95rem;
      line-height: 1.4;
      word-wrap: break-word;
    }

    .chatbot-message.bot {
      background: var(--surface-elev);
      color: var(--body-strong);
      align-self: flex-start;
      border-bottom-left-radius: 2px;
    }

    .chatbot-message.user {
      background: var(--m-blue-dk);
      color: var(--on-dark);
      align-self: flex-end;
      border-bottom-right-radius: 2px;
    }

    .chatbot-typing {
      display: flex;
      gap: 4px;
      padding: 12px 14px;
      background: var(--surface-elev);
      border-radius: 8px;
      border-bottom-left-radius: 2px;
      align-self: flex-start;
      width: fit-content;
    }

    .chatbot-typing span {
      width: 6px;
      height: 6px;
      background: var(--muted);
      border-radius: 50%;
      animation: typing 1.4s infinite ease-in-out both;
    }

    .chatbot-typing span:nth-child(1) { animation-delay: -0.32s; }
    .chatbot-typing span:nth-child(2) { animation-delay: -0.16s; }

    @keyframes typing {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }

    .chatbot-input-area {
      padding: var(--sp-sm) var(--sp-md);
      border-top: 1px solid var(--hairline);
      display: flex;
      gap: var(--sp-sm);
      align-items: center;
      background: var(--surface-card);
    }

    .chatbot-input {
      flex: 1;
      background: var(--canvas);
      border: 1px solid var(--hairline);
      color: var(--on-dark);
      padding: 10px 14px;
      border-radius: 20px;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
    }

    .chatbot-input:focus {
      border-color: var(--m-blue-lt);
    }

    .chatbot-send {
      background: var(--m-blue-dk);
      color: white;
      border: none;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s, transform 0.1s;
    }

    .chatbot-send:hover {
      background: var(--m-blue-lt);
    }

    .chatbot-send:active {
      transform: scale(0.95);
    }

    /* Make selection work well inside input */
    .chatbot-input::selection {
      background: white;
      color: black;
    }
  </style>
"""

# Insert modal HTML and CSS right before the final scripts
content = content.replace('  <!-- Chatbot Lottie Button -->', chatbot_ui_html + '\n  <!-- Chatbot Lottie Button -->')


chatbot_js = """
    // Chatbot UI Logic
    const chatbotModal = document.getElementById('chatbotModal');
    const chatbotClose = document.getElementById('chatbotClose');
    const chatbotInput = document.getElementById('chatbotInput');
    const chatbotSend = document.getElementById('chatbotSend');
    const chatbotMessages = document.getElementById('chatbotMessages');

    // Toggle Modal
    chatbotFab.addEventListener('click', () => {
      chatbotModal.classList.toggle('active');
      if (chatbotModal.classList.contains('active')) {
        setTimeout(() => chatbotInput.focus(), 300);
      }
    });

    // Close Modal
    chatbotClose.addEventListener('click', () => {
      chatbotModal.classList.remove('active');
    });

    // Function to add a message to the UI
    function appendMessage(text, sender) {
      const msgDiv = document.createElement('div');
      msgDiv.classList.add('chatbot-message', sender);
      msgDiv.textContent = text;
      chatbotMessages.appendChild(msgDiv);
      chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    // Function to show typing indicator
    function showTyping() {
      const typingDiv = document.createElement('div');
      typingDiv.classList.add('chatbot-typing');
      typingDiv.id = 'chatbotTyping';
      typingDiv.innerHTML = '<span></span><span></span><span></span>';
      chatbotMessages.appendChild(typingDiv);
      chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    // Function to remove typing indicator
    function hideTyping() {
      const typingDiv = document.getElementById('chatbotTyping');
      if (typingDiv) typingDiv.remove();
    }

    // Handle Send
    function handleSend() {
      const text = chatbotInput.value.trim();
      if (!text) return;

      // User message
      appendMessage(text, 'user');
      chatbotInput.value = '';

      // Bot response simulation
      showTyping();
      setTimeout(() => {
        hideTyping();
        appendMessage("I'm an AI assistant in a demo state. I can't process requests yet, but I'm ready to help you find your dream job once fully implemented!", 'bot');
      }, 1500);
    }

    chatbotSend.addEventListener('click', handleSend);
    chatbotInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') handleSend();
    });
"""

# Insert the javascript before the final reverseToStart() definition or init call
content = content.replace('    function reverseToStart() {', chatbot_js + '\n    function reverseToStart() {')

with open('templates/index.html', 'w') as f:
    f.write(content)
