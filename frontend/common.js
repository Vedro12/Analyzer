/* ========================= COMMON (frontend/common.js) ========================= */
const API_URL = "http://127.0.0.1:8000";

function getSessionId() {
    let sessionId = localStorage.getItem("session_id");

    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem("session_id", sessionId);
    }

    return sessionId;
}

async function apiPost(path, body = {}) {
    const res = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
    });

    return await res.json();
}

function validateToken(token) {
    if (!token) return "Введите токен";
    if (token.length < 50) return "Токен слишком короткий";
    if (/\s/.test(token)) return "Токен не должен содержать пробелы";
    return "";
}

function validateFolderId(id) {
    if (!id) return "Введите идентификатор каталога";
    if (!/^[a-z0-9]+$/.test(id)) return "Только латиница и цифры";
    if (id.length < 20 || id.length > 25) return "Неверная длина идентификатора каталога";
    return "";
}

function scrollChat(chatBox) {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function enhanceCodeBlocks(container) {
    const blocks = container.querySelectorAll("pre");

    blocks.forEach((pre) => {
        const code = pre.querySelector("code");
        if (!code) return;

        let lang = "code";
        const match = code.className?.match(/language-(\w+)/);
        if (match) lang = match[1];

        const langLabel = document.createElement("div");
        langLabel.className = "code-lang";
        langLabel.textContent = lang;

        const btn = document.createElement("button");
        btn.className = "copy-btn";

        btn.onclick = async () => {
            await navigator.clipboard.writeText(code.innerText);
            btn.classList.add("copied");

            setTimeout(() => {
                btn.classList.remove("copied");
            }, 1200);
        };

        pre.style.position = "relative";
        pre.appendChild(langLabel);
        pre.appendChild(btn);
    });
}

function addMessage(chatBox, text, role) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement("div");

    const avatarType =
        role === "user"
            ? "user"
            : role === "system"
                ? "system"
                : role === "error"
                    ? "error"
                    : "assistant";

    avatar.className = `avatar ${avatarType}-avatar`;

    const content = document.createElement("div");
    content.className = "message-content";

    const rawHtml = marked.parse(text || "");
    const safeHtml = DOMPurify.sanitize(rawHtml);

    content.innerHTML = safeHtml;
    enhanceCodeBlocks(content);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatBox.appendChild(messageDiv);
    scrollChat(chatBox);
}

function addLoadingMessage(chatBox) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message assistant loading";
    messageDiv.id = "loading-msg";

    const avatar = document.createElement("div");
    avatar.className = "avatar assistant-avatar";

    const content = document.createElement("div");
    content.className = "message-content";

    content.innerHTML = `
        <div class="typing">
            <span></span><span></span><span></span>
        </div>
    `;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatBox.appendChild(messageDiv);
    scrollChat(chatBox);
}

function removeLoadingMessage() {
    const el = document.getElementById("loading-msg");
    if (el) el.remove();
}

async function loadHistory(chatBox, sessionId) {
    const data = await apiPost("/history", {
        session_id: sessionId
    });

    if (data.history && Array.isArray(data.history)) {
        data.history.forEach(msg => {
            addMessage(chatBox, msg.content, msg.role);
        });
    }

    return data;
}

async function sendChatMessage(sessionId, message) {
    return await apiPost("/ai-chat", {
        session_id: sessionId,
        message
    });
}

async function collectInfraData(sessionId) {
    return await apiPost("/collect", {
        session_id: sessionId
    });
}

async function saveTokenToBackend(sessionId, token, folderId) {
    return await apiPost("/set-token", {
        session_id: sessionId,
        token,
        folder_id: folderId
    });
}

async function clearAllData(sessionId) {
    return await apiPost("/clear-all", {
        session_id: sessionId
    });
}

function setupPasswordToggle() {
    document.addEventListener("click", (e) => {
        if (e.target.classList.contains("password-control")) {
            const input = document.getElementById("iam-token-input");

            if (!input) return;

            if (input.type === "password") {
                input.type = "text";
                e.target.classList.add("view");
            } else {
                input.type = "password";
                e.target.classList.remove("view");
            }
        }
    });
}