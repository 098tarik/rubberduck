const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const welcome = document.getElementById('welcome');
const modelSelect = document.getElementById('modelSelect');
const sessionSelect = document.getElementById('sessionSelect');
const sessionBadge = document.getElementById('sessionIdBadge');
const modelNotice = document.getElementById('modelNotice');
const suggestBtn = document.getElementById('suggestBtn');

let sessionId = null;
let isStreaming = false;
let currentRequestId = null;
let currentAbortController = null;
let activeStreamToken = 0;
let progressBarTimer = null;
let progressValue = 0;

const SEND_ICON_SVG = `<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
const STOP_ICON_SVG = `<svg viewBox="0 0 24 24"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`;

const USER_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#7b9fff"/><ellipse cx="72" cy="72" rx="18" ry="12" fill="#5a7de0" transform="rotate(-10 72 72)"/><ellipse cx="42" cy="50" rx="13" ry="16" fill="#7b9fff"/><circle cx="36" cy="36" r="18" fill="#7b9fff"/><circle cx="30" cy="31" r="4" fill="white"/><circle cx="29" cy="31" r="2" fill="#1a1a2e"/><ellipse cx="18" cy="37" rx="10" ry="5" fill="#ff9a3c" transform="rotate(-10 18 37)"/></svg>`;
const ASSISTANT_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#0a0a0a"/><ellipse cx="42" cy="50" rx="13" ry="16" fill="#0a0a0a"/><circle cx="36" cy="36" r="18" fill="#0a0a0a"/><circle cx="30" cy="31" r="4" fill="white"/><circle cx="29" cy="31" r="2" fill="#333"/><ellipse cx="18" cy="37" rx="10" ry="5" fill="#0a0a0a" opacity="0.7" transform="rotate(-10 18 37)"/></svg>`;
const TYPING_AVATAR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 100" width="24" height="20"><ellipse cx="60" cy="68" rx="38" ry="28" fill="#0a0a0a"/><circle cx="36" cy="36" r="18" fill="#0a0a0a"/><circle cx="30" cy="31" r="4" fill="white"/></svg>`;
const DEFAULT_TYPING_STATUS = 'Preparing context...';

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

function releaseStreamingUI() {
    removeTypingIndicator();
    currentAbortController = null;
    currentRequestId = null;
    isStreaming = false;
    setSendMode();
    messageInput.focus();
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

function addTypingIndicator(statusText = DEFAULT_TYPING_STATUS) {
    const messageElement = document.createElement('div');
    messageElement.className = 'message assistant';
    messageElement.id = 'typing';

    const avatarElement = document.createElement('div');
    avatarElement.className = 'message-avatar';
    avatarElement.innerHTML = TYPING_AVATAR_SVG;

    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    contentElement.innerHTML = (
        '<div class="typing-shell">'
        + '<div class="typing-status"></div>'
        + '<div class="progress-bar-track"><div class="progress-bar-fill" id="progressBarFill"></div></div>'
        + '</div>'
    );

    messageElement.appendChild(avatarElement);
    messageElement.appendChild(contentElement);
    chatContainer.appendChild(messageElement);
    setTypingIndicatorStatus(statusText);
    scrollChatToBottom();
}

function startProgressBar() {
    progressValue = 0;
    clearInterval(progressBarTimer);
    const fill = document.getElementById('progressBarFill');
    if (fill) {
        fill.style.width = '0%';
    }
    progressBarTimer = setInterval(() => {
        // Eased fake progress: asymptotically approaches 88% — never completes on its own
        progressValue += (0.88 - progressValue) * 0.04;
        const fill = document.getElementById('progressBarFill');
        if (fill) {
            fill.style.width = `${progressValue * 100}%`;
        }
    }, 80);
}

function completeProgressBar(callback) {
    clearInterval(progressBarTimer);
    progressBarTimer = null;
    const fill = document.getElementById('progressBarFill');
    if (!fill) {
        callback();
        return;
    }
    fill.classList.add('complete');
    fill.style.width = '100%';
    setTimeout(callback, 380);
}

function removeTypingIndicator() {
    clearInterval(progressBarTimer);
    progressBarTimer = null;
    document.getElementById('typing')?.remove();
}

function setTypingIndicatorStatus(statusText) {
    const statusElement = document.querySelector('#typing .typing-status');
    if (!statusElement) {
        return;
    }

    statusElement.textContent = statusText || DEFAULT_TYPING_STATUS;
}

function clearModelNotice() {
    if (!modelNotice) {
        return;
    }

    modelNotice.hidden = true;
    modelNotice.innerHTML = '';
}

function showModelNotice(messageHtml) {
    if (!modelNotice) {
        return;
    }

    modelNotice.innerHTML = messageHtml;
    modelNotice.hidden = false;
}

function updateSelectedModel(modelName) {
    if (!modelName || !modelSelect) {
        return;
    }

    const existingOption = Array.from(modelSelect.options).find((option) => option.value === modelName);
    if (!existingOption) {
        return;
    }

    modelSelect.value = modelName;
}

function updateSessionBadge(serverSessionId) {
    if (!serverSessionId) {
        return;
    }

    sessionId = serverSessionId;
    sessionBadge.textContent = `session: ${serverSessionId.slice(0, 8)}…`;
}

async function streamAssistantResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let errorText = null;
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

            if (parsedPayload.status?.label) {
                updateSelectedModel(parsedPayload.status.model);
                if (
                    parsedPayload.status.reason === 'memory'
                    && parsedPayload.status.requested_model
                    && parsedPayload.status.model
                    && parsedPayload.status.requested_model !== parsedPayload.status.model
                ) {
                    showModelNotice(
                        `Selected model <strong>${parsedPayload.status.requested_model}</strong> did not fit in available memory, so RubberDuck used <strong>${parsedPayload.status.model}</strong> for this response.`
                    );
                }
                setTypingIndicatorStatus(parsedPayload.status.label);
                scrollChatToBottom();
            } else if (parsedPayload.text) {
                // Buffer text — do not render incrementally
                fullText += parsedPayload.text;
            } else if (parsedPayload.error) {
                errorText = parsedPayload.error;
                shouldStop = true;
                break;
            }
        }
    }

    // Fill bar to 100% quickly, then reveal the full message at once
    completeProgressBar(() => {
        removeTypingIndicator();
        if (errorText) {
            addMessage('assistant', `Quack! ${errorText}`);
        } else if (fullText) {
            addMessage('assistant', fullText);
        }
    });
}

async function cancelMessage() {
    const abortController = currentAbortController;
    const requestId = currentRequestId;
    activeStreamToken += 1;
    releaseStreamingUI();

    if (abortController) {
        abortController.abort();
    }

    if (requestId) {
        fetch(`/api/chat/${requestId}/cancel`, { method: 'POST' }).catch(() => {
            // ignore cancel errors — the stream will end naturally
        });
    }
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isStreaming) {
        return;
    }

    isStreaming = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    clearModelNotice();

    addMessage('user', text);
    addTypingIndicator();
    startProgressBar();
    setStopMode();

    const streamToken = ++activeStreamToken;
    currentAbortController = new AbortController();

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: sessionId,
                model: modelSelect.value,
            }),
            signal: currentAbortController.signal,
        });

        currentAbortController = null;

        if (!response.ok) {
            throw new Error(await response.text() || `HTTP ${response.status}`);
        }

        updateSessionBadge(response.headers.get('X-Session-Id'));
        currentRequestId = response.headers.get('X-Request-Id');
        await streamAssistantResponse(response);
        await loadSessions();
    } catch (error) {
        removeTypingIndicator();
        if (error?.name !== 'AbortError') {
            addMessage('assistant', `Quack! ${error?.message || 'Something went wrong.'}`);
        }
    }

    if (streamToken === activeStreamToken) {
        releaseStreamingUI();
    }
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

    if (suggestBtn) {
        suggestBtn.addEventListener('click', openRecommendations);
    }

}

async function initializeApp() {
    registerEventListeners();
    await Promise.all([loadModels(), loadSessions()]);
}

// ── Model Recommendations Modal ────────────────────────────────────────

function _ensureRecommendationsModal() {
    let overlayElement = document.getElementById('recommendationsOverlay');
    let bodyElement = document.getElementById('recModalBody');

    if (!overlayElement || !bodyElement) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="modal-overlay" id="recommendationsOverlay" hidden aria-modal="true" role="dialog" aria-labelledby="recModalTitle">
                <div class="modal" id="recommendationsModal">
                    <div class="modal-header">
                        <h2 id="recModalTitle">Recommendations</h2>
                        <button class="modal-close" type="button" id="closeRecommendationsBtn" aria-label="Close">X</button>
                    </div>
                    <div class="modal-body" id="recModalBody"></div>
                </div>
            </div>`;
        document.body.appendChild(wrapper.firstElementChild);
        overlayElement = document.getElementById('recommendationsOverlay');
        bodyElement = document.getElementById('recModalBody');
    }

    return { overlayElement, bodyElement };
}

function openRecommendations() {
    const { overlayElement, bodyElement } = _ensureRecommendationsModal();

    if (!overlayElement || !bodyElement) {
        showModelNotice('Model recommendations modal is unavailable right now.');
        return;
    }

    overlayElement.hidden = false;
    overlayElement.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', _recEscHandler);
    bodyElement.innerHTML = `
        <div class="rec-loading">
            <div class="rec-spinner"></div>
            <span>Detecting your hardware…</span>
        </div>`;
    _fetchRecommendations();
}

function closeRecommendations() {
    const overlayElement = document.getElementById('recommendationsOverlay');
    if (!overlayElement) {
        return;
    }

    overlayElement.hidden = true;
    overlayElement.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    document.removeEventListener('keydown', _recEscHandler);
}

function _recEscHandler(event) {
    if (event.key === 'Escape') {
        closeRecommendations();
    }
}

document.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) {
        return;
    }

    if (target.id === 'suggestBtn') {
        openRecommendations();
        return;
    }

    if (target.id === 'closeRecommendationsBtn') {
        closeRecommendations();
        return;
    }

    const overlayElement = document.getElementById('recommendationsOverlay');
    if (overlayElement && target === overlayElement) {
        closeRecommendations();
    }
});

async function _fetchRecommendations() {
    const bodyElement = document.getElementById('recModalBody');
    if (!bodyElement) {
        return;
    }

    try {
        const response = await fetch('/api/recommendations');
        if (!response.ok) {
            throw new Error(`Server error ${response.status}`);
        }
        const data = await response.json();
        _renderRecommendations(data);
    } catch (error) {
        bodyElement.innerHTML = `
            <div class="rec-error">
                <strong>Could not load recommendations</strong>
                ${error.message || 'Unknown error'}
            </div>`;
    }
}

function _hwBannerHtml(hw) {
    const gpuText = hw.gpus.length
        ? hw.gpus.map((g) => `${g.name} (${g.vram_gb} GB)`).join(', ')
        : 'None detected';

    return `
        <div class="hw-banner">
            <div class="hw-stat">
                <span class="hw-stat-label">Platform</span>
                <span class="hw-stat-value">${hw.platform}</span>
            </div>
            <div class="hw-stat">
                <span class="hw-stat-label">CPU</span>
                <span class="hw-stat-value">${hw.cpu_cores}c / ${hw.cpu_threads}t</span>
            </div>
            <div class="hw-stat">
                <span class="hw-stat-label">RAM</span>
                <span class="hw-stat-value">${hw.ram_gb} GB</span>
            </div>
            <div class="hw-stat">
                <span class="hw-stat-label">GPU</span>
                <span class="hw-stat-value ${hw.total_vram_gb > 0 ? 'gpu-accent' : ''}">${gpuText}</span>
            </div>
            ${hw.total_vram_gb > 0 ? `
            <div class="hw-stat">
                <span class="hw-stat-label">VRAM</span>
                <span class="hw-stat-value gpu-accent">${hw.total_vram_gb} GB</span>
            </div>` : ''}
        </div>`;
}

function _recCardHtml(rec) {
    const compatLabel = {
        full_gpu: '⚡ Full GPU',
        partial_gpu: '◑ Part GPU',
        cpu_ok: '○ CPU only',
    }[rec.compatibility] || rec.compatibility;

    const tradeoffsHtml = rec.tradeoffs
        .map((t) => `<div class="rec-tradeoff-item">${_escapeHtml(t)}</div>`)
        .join('');

    const strengthsHtml = rec.strengths
        .map((s) => `<span class="rec-tag">${_escapeHtml(s)}</span>`)
        .join('');

    const pullId = `pull-${rec.rank}`;

    return `
        <div class="rec-card">
            <div class="rec-card-header">
                <span class="rec-rank">#${rec.rank}</span>
                <div class="rec-title">
                    <div class="rec-model-name">${_escapeHtml(rec.display_name)}</div>
                    <div class="rec-meta">${_escapeHtml(rec.parameters)} · ${_escapeHtml(rec.context_window)} · ${_escapeHtml(rec.use_cases.join(', '))}</div>
                </div>
                <div class="rec-badges">
                    <span class="rec-badge compat-${rec.compatibility}">${compatLabel}</span>
                    <span class="rec-badge speed-${rec.speed}">${rec.speed}</span>
                </div>
            </div>
            <div class="rec-compat-detail">${_escapeHtml(rec.compatibility_detail)}</div>
            ${tradeoffsHtml ? `<div class="rec-tradeoffs">
                <div class="rec-tradeoffs-label">Tradeoffs</div>
                ${tradeoffsHtml}
            </div>` : ''}
            <div class="rec-strengths-row">${strengthsHtml}</div>
            <div class="rec-pull-cmd">
                <span class="rec-pull-code" id="${pullId}">${_escapeHtml(rec.ollama_pull)}</span>
                <button class="rec-copy-btn" onclick="_copyPull('${pullId}', this)">Copy</button>
            </div>
        </div>`;
}

function _renderRecommendations(data) {
    const bodyElement = document.getElementById('recModalBody');
    if (!bodyElement) {
        return;
    }

    const hw = data.hardware;
    const recs = data.recommendations || [];

    let html = _hwBannerHtml(hw);

    if (recs.length === 0) {
        html += `<div class="rec-error"><strong>No compatible models found</strong>Your hardware profile did not match any catalog entries.</div>`;
    } else {
        html += `<div class="rec-list">${recs.map(_recCardHtml).join('')}</div>`;
    }

    bodyElement.innerHTML = html;
}

function _copyPull(elementId, btn) {
    const text = document.getElementById(elementId)?.textContent || '';
    const original = btn.textContent;
    copyToClipboard(text, btn);
    void original; // already handled inside copyToClipboard
}

function _escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

window.newSession = newSession;
window.sendMessage = sendMessage;
window.cancelMessage = cancelMessage;
window.openRecommendations = openRecommendations;
window.closeRecommendations = closeRecommendations;
window._copyPull = _copyPull;

initializeApp();
