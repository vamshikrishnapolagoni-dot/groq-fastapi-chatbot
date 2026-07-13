// DOM Elements
const sidebar = document.getElementById('sidebar');
const menuBtn = document.getElementById('menuBtn');
const closeSidebarBtn = document.getElementById('closeSidebarBtn');
const themeToggleBtn = document.getElementById('themeToggleBtn');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const messagesContainer = document.getElementById('messagesContainer');
const welcomeScreen = document.getElementById('welcomeScreen');
const newChatBtn = document.getElementById('newChatBtn');

// App State
let chatHistory = []; // Format: [ [userMsg, assistantMsg], ... ]
let isGenerating = false;

// 1. Sidebar Toggle Mobile
if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
    });
}

if (closeSidebarBtn && sidebar) {
    closeSidebarBtn.addEventListener('click', () => {
        sidebar.classList.remove('open');
    });
}

// Close sidebar on click outer overlay for mobile
document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768) {
        if (!sidebar.contains(e.target) && !menuBtn.contains(e.target) && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    }
});

// 2. Theme Toggle (LocalStorage persistence)
const savedTheme = localStorage.getItem('theme') || 'dark';
if (savedTheme === 'light') {
    document.body.classList.add('light-theme');
    updateThemeIcon(true);
} else {
    updateThemeIcon(false);
}

if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
        const isLight = document.body.classList.toggle('light-theme');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        updateThemeIcon(isLight);
    });
}

function updateThemeIcon(isLight) {
    const icon = themeToggleBtn.querySelector('i');
    if (icon) {
        icon.className = isLight ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    }
}

// 3. Textarea Auto Resizing
if (chatInput) {
    chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight - 16) + 'px';
    });

    // Enter key submits the form, Shift+Enter adds newline
    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });
}

// 4. Suggestion Handling
window.useSuggest = function (text) {
    if (isGenerating) return;
    chatInput.value = text;
    chatInput.dispatchEvent(new Event('input'));
    chatInput.focus();
    chatForm.dispatchEvent(new Event('submit'));
};

// 5. New Chat Session Refresher
if (newChatBtn) {
    newChatBtn.addEventListener('click', () => {
        if (isGenerating) return;
        chatHistory = [];
        messagesContainer.innerHTML = '';
        messagesContainer.appendChild(welcomeScreen);
        welcomeScreen.style.display = 'flex';
        chatInput.value = '';
        chatInput.style.height = 'auto';
        chatInput.focus();
    });
}

// Render Markdown-like HTML (bold, lists, inline code, pre blocks)
function renderMarkdown(text) {
    let html = text;

    // Escape HTML to prevent injection
    html = html
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // Code blocks (```code```)
    html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
        // Strip out optional language prefix (e.g. python, javascript)
        const lines = code.trim().split('\n');
        let codeBody = code;
        if (lines.length > 0 && /^[a-zA-Z0-9+#]+$/.test(lines[0].trim())) {
            codeBody = lines.slice(1).join('\n');
        }
        return `<pre><code>${codeBody.trim()}</code></pre>`;
    });

    // Inline Code (`code`)
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold (**bold**)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic (*italic*)
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Unordered Lists (* item)
    html = html.replace(/^\s*[\-\*]\s+(.+)$/gm, '<li>$1</li>');
    // Wrap adjacent list elements in <ul>
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    // Fix nested list errors
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    // Convert remaining newlines to line breaks (outside of block containers like pre and ul)
    // To do this simply, replace \n with <br> only when not inside special tags,
    // or just use CSS white-space rendering, but paragraphs are cleaner.
    const parts = html.split(/(<pre>[\s\S]*?<\/pre>|<ul>[\s\S]*?<\/ul>)/g);
    for (let i = 0; i < parts.length; i++) {
        if (!parts[i].startsWith('<pre>') && !parts[i].startsWith('<ul>')) {
            parts[i] = parts[i].trim().split('\n\n').map(p => {
                if (p.trim() === '') return '';
                return `<p>${p.replace(/\n/g, '<br>')}</p>`;
            }).join('');
        }
    }
    html = parts.join('');

    return html;
}

// Add message to chat container
function appendMessage(sender, text, isUser = false) {
    // Hide welcome panel first time a message is added
    if (welcomeScreen && welcomeScreen.style.display !== 'none') {
        welcomeScreen.style.display = 'none';
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;

    const avatarHtml = isUser
        ? '<i class="fa-solid fa-user"></i>'
        : '<i class="fa-solid fa-robot"></i>';

    const senderText = isUser ? 'You' : 'Assistant';

    const contentHtml = isUser ? `<p>${text}</p>` : renderMarkdown(text);

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatarHtml}</div>
        <div class="message-content">
            <span class="message-sender">${senderText}</span>
            <div class="message-bubble">${contentHtml}</div>
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

// Append Simulated typing block
function appendTypingIndicator() {
    const indicatorDiv = document.createElement('div');
    indicatorDiv.id = 'typingIndicator';
    indicatorDiv.className = 'message assistant';
    indicatorDiv.innerHTML = `
        <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
            <span class="message-sender">Assistant</span>
            <div class="message-bubble">
                <div class="typing-indicator">
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                    <span class="typing-dot"></span>
                </div>
            </div>
        </div>
    `;
    messagesContainer.appendChild(indicatorDiv);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicatorDiv = document.getElementById('typingIndicator');
    if (indicatorDiv) {
        indicatorDiv.remove();
    }
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// 6. Form Submission / API call logic
if (chatForm) {
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const text = chatInput.value.trim();
        if (!text || isGenerating) return;

        // Visual State Changes
        isGenerating = true;
        chatInput.value = '';
        chatInput.style.height = 'auto';
        chatInput.disabled = true;
        sendBtn.disabled = true;
        sendBtn.style.opacity = 0.5;

        // Render User Query
        appendMessage('User', text, true);

        // Render typing animation
        appendTypingIndicator();

        try {
            // Post payload to FastAPI endpoint
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: text,
                    history: chatHistory
                })
            });

            removeTypingIndicator();

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to complete chat request.');
            }

            const data = await response.json();
            const reply = data.response;

            // Render Assistant Reply
            appendMessage('Assistant', reply, false);

            // Save history turn
            chatHistory.push([text, reply]);

        } catch (error) {
            console.error('API Error:', error);
            removeTypingIndicator();
            appendMessage('SystemError', `⚠️ *Failed to communicate with server.* Reason: ${error.message}`, false);
        } finally {
            // Restore visual input state
            isGenerating = false;
            chatInput.disabled = false;
            sendBtn.disabled = false;
            sendBtn.style.opacity = 1;
            chatInput.focus();
        }
    });
}
