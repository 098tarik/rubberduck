const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const welcome = document.getElementById('welcome');
const modelSelect = document.getElementById('modelSelect');
const sessionSelect = document.getElementById('sessionSelect');
const sessionBadge = document.getElementById('sessionIdBadge');

let sessionId = null;
let isStreaming = false;
let currentRequestId = null;

const SEND_ICON_SVG = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
const STOP_ICON_SVG = `<svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`;

const USER_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#7b9fff"/><ellipse cx="72" cy="72" rx="18" ry="12" fill="#5a7de0" transform="rotate(-10 72 72)"/><ellipse cx="42" cy="50" rx="13" ry="16" fill="#7b9fff"/><circle cx="36" cy="36" r="18" fill="#7b9fff"/><circle cx="30" cy="31" r="4" fill="white"/><circle cx="29" cy="31" r="2" fill="#1a1a2e"/><ellipse cx="18" cy="37" rx="10" ry="5" fill="#ff9a3c" transform="rotate(-10 18 37)"/></svg>`;
const ASSISTANT_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#0a0a0a"/><ellipse cx="42" cy="50" rx="13" ry="16" fill="#0a0a0a"/><circle cx="36" cy="36" r="18" fill="#0a0a0a"/><circle cx="30" cy="31" r="4" fill="white"/><circle cx="29" cy="31" r="2" fill="#333"/><ellipse cx="18" cy="37" rx="10" ry="5" fill="#0a0a0a" opacity="0.7" transform="rotate(-10 18 37)"/></svg>`;
const TYPING_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#0a0a0a"/><circle cx="36" cy="36" r="18" fill="#0a0a0a"/><circle cx="30" cy="31" r="4" fill="white"/></svg>`;

if (window.marked && window.hljs) {
    marked.setOptions({
        gfm: true,
        breaks: true,
    });
}

function setSendMode() {
    sendBtn.innerHTML = SEND_ICON_SVG;
    sendBtn.onclick = sendMessage;
    sendBtn.disabled = false;
    sendBtn.classList.remove('stop');
    sendBtn.setAttribute('aria-label', 'Send message');
}

function setStopMode() {
    sendBtn.innerHTML = STOP_ICON_SVG;
    sendBtn.onclick = cancelMessage;
    sendBtn.disabled = false;
    sendBtn.classList.add('stop');
    sendBtn.setAttribute('aria-label', 'Stop response');
}

async function copyToClipboard(text, buttonElement) {
    const originalText = buttonElement.textContent;

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            fallbackCopyToClipboard(text);
        }

        buttonElement.textContent = 'Copied';
        window.setTimeout(() => {
            buttonElement.textContent = originalText;
        }, 1200);
    } catch {
        buttonElement.textContent = 'Failed';
        window.setTimeout(() => {
            buttonElement.textContent = originalText;
        }, 1200);
    }
}

function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.setAttribute('readonly', '');
    textArea.style.position = 'fixed';
    textArea.style.top = '-9999px';
    textArea.style.left = '-9999px';

    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    textArea.setSelectionRange(0, textArea.value.length);

    const copied = document.execCommand('copy');
    document.body.removeChild(textArea);

    if (!copied) {
        throw new Error('Clipboard copy failed.');
    }
}

async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const payload = await response.json();
        const models = (payload.models || []).filter((m) => !m.endsWith(':cloud'));

        modelSelect.innerHTML = '';
        const defaultModel = payload.default || 'deepseek-r1:8b';
        for (const model of models.length ? models : [defaultModel]) {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            if (model === defaultModel) {
                option.selected = true;
            }
            modelSelect.appendChild(option);
        }
    } catch {
        modelSelect.innerHTML = (
            '<option value="deepseek-r1:8b">deepseek-r1:8b</option>'
        );
    }
}

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const payload = await response.json();

        sessionSelect.innerHTML = '<option value="">▸ Resume session…</option>';
        for (const session of payload.sessions || []) {
            const option = document.createElement('option');
            option.value = session.id;
            option.textContent = session.preview.slice(0, 40)
                + (session.preview.length > 40 ? '…' : '');
            sessionSelect.appendChild(option);
        }
    } catch {
        sessionSelect.innerHTML = '<option value="">No sessions</option>';
    }
}

async function restoreSession(sessionIdToLoad) {
    const response = await fetch(`/api/sessions/${sessionIdToLoad}`);
    const payload = await response.json();

    chatContainer.innerHTML = '';
    if (welcome) {
        welcome.style.display = 'none';
    }

    for (const message of payload.messages) {
        addMessage(message.role, message.content);
    }

    sessionId = sessionIdToLoad;
    sessionBadge.textContent = `session: ${sessionIdToLoad.slice(0, 8)}…`;
}

function newSession() {
    sessionId = null;
    chatContainer.innerHTML = '';
    if (welcome) {
        welcome.style.display = '';
    }
    sessionBadge.textContent = '';
}

function autoResizeMessageInput() {
    messageInput.style.height = 'auto';
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
}

function scrollChatToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function createAvatarMarkup(role) {
    return role === 'user' ? USER_AVATAR_SVG : ASSISTANT_AVATAR_SVG;
}

function highlightCodeBlocks(containerElement) {
    if (!window.hljs) {
        return;
    }

    const codeBlocks = containerElement.querySelectorAll('pre code');
    for (const codeBlock of codeBlocks) {
        const languageClass = Array.from(codeBlock.classList).find(
            (className) => className.startsWith('language-')
        );
        const language = languageClass?.replace('language-', '');
        const sourceCode = codeBlock.textContent;

        if (!sourceCode) {
            continue;
        }

        const highlighted = language && window.hljs.getLanguage(language)
            ? window.hljs.highlight(sourceCode, { language })
            : window.hljs.highlightAuto(sourceCode);

        codeBlock.innerHTML = highlighted.value;
        codeBlock.classList.add('hljs');
    }
}

function renderAssistantContent(contentDiv, content) {
    contentDiv.innerHTML = marked.parse(content);
    highlightCodeBlocks(contentDiv);
}

function addMessage(role, content) {
    if (welcome) {
        welcome.style.display = 'none';
    }

    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;

    const avatarElement = document.createElement('div');
    avatarElement.className = 'message-avatar';
    avatarElement.innerHTML = createAvatarMarkup(role);

    const messageStackElement = document.createElement('div');
    messageStackElement.className = 'message-stack';

    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';

    const copyButtonElement = document.createElement('button');
    copyButtonElement.className = 'message-copy-btn';
    copyButtonElement.type = 'button';
    copyButtonElement.textContent = 'Copy';
    copyButtonElement.dataset.copyText = content;
    copyButtonElement.addEventListener('click', () => {
        copyToClipboard(copyButtonElement.dataset.copyText || '', copyButtonElement);
    });

    if (role === 'assistant' && content) {
        renderAssistantContent(contentElement, content);
    } else {
        contentElement.textContent = content;
    }

    messageStackElement.appendChild(contentElement);
    messageStackElement.appendChild(copyButtonElement);

    messageElement.appendChild(avatarElement);
    messageElement.appendChild(messageStackElement);
    chatContainer.appendChild(messageElement);
    scrollChatToBottom();

    return contentElement;
}

function addTypingIndicator() {
    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant';
    messageElement.id = 'typing';

    const avatarElement = document.createElement('div');
    avatarElement.className = 'message-avatar';
    avatarElement.innerHTML = TYPING_AVATAR_SVG;

    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    contentElement.innerHTML = (
        '<div class="typing-indicator"><span></span><span></span><span></span></div>'
    );

    messageElement.appendChild(avatarElement);
    messageElement.appendChild(contentElement);
    chatContainer.appendChild(messageElement);
    scrollChatToBottom();
}

function removeTypingIndicator() {
    document.getElementById('typing')?.remove();
}

function updateSessionBadge(serverSessionId) {
    if (!serverSessionId) {
        return;
    }

    sessionId = serverSessionId;
    sessionBadge.textContent = `session: ${serverSessionId.slice(0, 8)}…`;
}

async function streamAssistantResponse(response) {
    const contentDiv = addMessage('assistant', '');
    const copyButtonElement = contentDiv.parentElement.querySelector('.message-copy-btn');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let shouldStop = false;

    while (!shouldStop) {
        const { done, value } = await reader.read();
        if (done) {
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line.startsWith('data:')) {
                continue;
            }

            const payload = line.slice(5).trim();
            if (payload === '[DONE]') {
                shouldStop = true;
                break;
            }

            let parsedPayload;
            try {
                parsedPayload = JSON.parse(payload);
            } catch {
                continue;
            }

            if (parsedPayload.text) {
                fullText += parsedPayload.text;
                renderAssistantContent(contentDiv, fullText);
                copyButtonElement.dataset.copyText = fullText;
                scrollChatToBottom();
            } else if (parsedPayload.error) {
                contentDiv.textContent = `Error: ${parsedPayload.error}`;
                copyButtonElement.dataset.copyText = contentDiv.textContent;
                shouldStop = true;
                break;
            }
        }
    }
}

async function cancelMessage() {
    const requestId = currentRequestId;
    if (!requestId) {
        return;
    }
    currentRequestId = null;
    try {
        await fetch(`/api/chat/${requestId}/cancel`, { method: 'POST' });
    } catch {
        // ignore cancel errors — the stream will end naturally
    }
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isStreaming) {
        return;
    }

    isStreaming = true;
    sendBtn.disabled = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';

    addMessage('user', text);
    addTypingIndicator();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: sessionId,
                model: modelSelect.value,
            }),
        });

        if (!response.ok) {
            throw new Error(await response.text() || `HTTP ${response.status}`);
        }

        updateSessionBadge(response.headers.get('X-Session-Id'));
        currentRequestId = response.headers.get('X-Request-Id');
        removeTypingIndicator();
        setStopMode();
        await streamAssistantResponse(response);
        await loadSessions();
    } catch (error) {
        removeTypingIndicator();
        addMessage('assistant', `Quack! ${error?.message || 'Something went wrong.'}`);
    }

    currentRequestId = null;
    isStreaming = false;
    setSendMode();
    messageInput.focus();
}

function registerEventListeners() {
    sessionSelect.addEventListener('change', async () => {
        const selectedSessionId = sessionSelect.value;
        if (!selectedSessionId) {
            return;
        }

        try {
            await restoreSession(selectedSessionId);
        } catch (error) {
            alert(`Failed to load session: ${error.message}`);
        }

        sessionSelect.value = '';
    });

    messageInput.addEventListener('input', autoResizeMessageInput);
    messageInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
}

async function initializeApp() {
    registerEventListeners();
    await Promise.all([loadModels(), loadSessions()]);
}

window.newSession = newSession;
window.sendMessage = sendMessage;
window.cancelMessage = cancelMessage;

initializeApp();
