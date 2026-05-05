/* =========================
   EXTENSION (extension/popup.js)
========================= */
const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const collectBtn = document.getElementById("collect-btn");
const resetBtn = document.getElementById("reset-btn");
const tokenInput = document.getElementById("iam-token-input");
const folderInput = document.getElementById("folder-id-input");
const saveTokenBtn = document.getElementById("save-token-btn");
const tokenError = document.getElementById("token-error");
const folderError = document.getElementById("folder-error");

/* =========================
   STATE (ONLY UI)
========================= */

let oauthToken = localStorage.getItem("iamToken") || "";
let folderId = localStorage.getItem("folderId") || "";

/* =========================
   INIT
========================= */

tokenInput.value = oauthToken;
folderInput.value = folderId;

/* =========================
   SessionControl
========================= */

function getSessionId() {
    let sessionId = localStorage.getItem("session_id");

    if (!sessionId) {
        sessionId = crypto.randomUUID();
        localStorage.setItem("session_id", sessionId);
    }

    return sessionId;
}

const sessionId = getSessionId();

/* =========================
   INPUT SYNC (localStorage only)
========================= */

tokenInput.addEventListener("input", () => {
    oauthToken = tokenInput.value.trim();
    localStorage.setItem("iamToken", oauthToken);
    tokenError.textContent = validateToken(oauthToken);
});

folderInput.addEventListener("input", () => {
    folderId = folderInput.value.trim();
    localStorage.setItem("folderId", folderId);
    folderError.textContent = validateFolderId(folderId);
});

/* =========================
   VALIDATION
========================= */

function validateToken(token) {
    if (!token) return "Введите токен";
    if (token.length < 50) return "Токен слишком короткий";
    if (/\s/.test(token)) return "Токен не должен содержать пробелы";
    return "";
}

function validateFolderId(id) {
    if (!id) return "Введите идентификатор каталога";
    if (!/^[a-z0-9]+$/.test(id)) return "Только латиница и цифры";
    if (id.length < 20 || id.length > 25) return "Неверная длина";
    return "";
}

/* =========================
   PASSWORD TOGGLE
========================= */

document.addEventListener("click", (e) => {
    if (e.target.classList.contains("password-control")) {
        const input = document.getElementById("iam-token-input");

        if (input.type === "password") {
            input.type = "text";
            e.target.classList.add("view");
        } else {
            input.type = "password";
            e.target.classList.remove("view");
        }
    }
});

/* =========================
   UI
========================= */

function scrollChat() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function clearChatUI() {
    chatBox.innerHTML = `
        <div class="welcome-message">
            <div class="avatar ai-avatar"></div>
            <div class="welcome-content">
                <h3>Привет! Я Cloud Assistant</h3>
                <p>Задайте вопрос или соберите данные.</p>
            </div>
        </div>
    `;
}

/* =========================
   ENHANCE CODE BLOCKS (как на сайте)
========================= */

function enhanceCodeBlocks(container) {
    const blocks = container.querySelectorAll("pre");
    
    blocks.forEach((pre) => {
        const code = pre.querySelector("code");
        if (!code) return;
        
        // Определяем язык из class="language-js"
        let lang = "code";
        const match = code.className?.match(/language-(\w+)/);
        if (match) lang = match[1];
        
        // Бейдж языка
        const langLabel = document.createElement("div");
        langLabel.className = "code-lang";
        langLabel.textContent = lang;
        
        // Кнопка копирования
        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.onclick = async () => {
            await navigator.clipboard.writeText(code.innerText);
            btn.classList.add("copied");
            setTimeout(() => btn.classList.remove("copied"), 1200);
        };
        
        pre.style.position = "relative";
        pre.appendChild(langLabel);
        pre.appendChild(btn);
    });
}

/* =========================
   MESSAGE
========================= */

marked.setOptions({
    breaks: true,     
    gfm: true       
});

function addMessage(text, role) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = `avatar ${role === "user" ? "user-avatar" : "ai-avatar"}`;

    const content = document.createElement("div");
    content.className = "message-content";

    const rawHtml = marked.parse(text);

    const safeHtml = DOMPurify.sanitize(rawHtml);

    content.innerHTML = safeHtml;
    enhanceCodeBlocks(content);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatBox.appendChild(messageDiv);
    scrollChat();
}


/* =========================
   SEND MESSAGE
========================= */

async function sendMessage() {
    sendBtn.disabled = true;

    const message = userInput.value.trim();

    if (!message) {
        sendBtn.disabled = false;
        return;
    }

    userInput.value = "";

    addMessage(message, "user");
    addLoadingMessage();

    try {
        const res = await fetch("http://127.0.0.1:8000/ai-chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                session_id: sessionId,
                message
            })
        });

        const data = await res.json();

        if (data.status !== "ok") {
            addMessage(data.message || "Ошибка при получении ответа", "ai");
        } else {
            addMessage(data.answer, "ai");
        }

    } catch (e) {
        addMessage("Ошибка: " + e.message, "ai");
    } finally {
        removeLoadingMessage();
        sendBtn.disabled = false;
    }
}

function addLoadingMessage() {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message ai loading";
    messageDiv.id = "loading-msg";

    const avatar = document.createElement("div");
    avatar.className = "avatar ai-avatar";

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
    scrollChat();
}

function removeLoadingMessage() {
    const el = document.getElementById("loading-msg");
    if (el) el.remove();
}



/* =========================
   COLLECT (NO LOCAL STATE)
========================= */

async function collectData() {
    if (!oauthToken || !folderId) {
        addMessage("Нужен токен и folder ID", "ai");
        return;
    }

    try {
        const res = await fetch("http://127.0.0.1:8000/collect", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        const data = await res.json();

        if (data.status !== "ok") {
            addMessage(data.message || "Ошибка сбора данных", "ai");
            return;
        }

        addMessage(data.message || "Данные собраны", "ai");

    } catch (e) {
        addMessage("Ошибка: " + e.message, "ai");
    }
}

/* =========================
   SAVE TOKEN
========================= */

async function saveToken() {
    const tokenErr = validateToken(oauthToken);
    const folderErr = validateFolderId(folderId);

    tokenError.textContent = tokenErr;
    folderError.textContent = folderErr;

    if (tokenErr || folderErr) return;

    try {
        const res = await fetch("http://127.0.0.1:8000/set-token", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                session_id: sessionId,
                token: oauthToken,
                folder_id: folderId
            })
        });

        const data = await res.json();

        if (data.status !== "ok") {
            addMessage(data.message || "Ошибка сохранения токена", "ai");
            return;
        }

        addMessage(data.message || "Токен сохранён", "ai");

    } catch (e) {
        addMessage("Ошибка: " + e.message, "ai");
    }
}

/* =========================
   RESET CHAT (OLD STYLE CONFIRM)
========================= */

let resetConfirm = false;

resetBtn.onclick = async () => {
    if (!resetConfirm) {
        resetConfirm = true;
        resetBtn.classList.add("confirm");

        setTimeout(() => {
            resetConfirm = false;
            resetBtn.classList.remove("confirm");
        }, 1500);

        return;
    }

    resetConfirm = false;
    resetBtn.classList.remove("confirm");

    await fetch("http://127.0.0.1:8000/clear-all", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            session_id: sessionId
        })
    });

    localStorage.removeItem("iamToken");
    localStorage.removeItem("folderId");

    oauthToken = "";
    folderId = "";

    tokenInput.value = "";
    folderInput.value = "";

    tokenError.textContent = "";
    folderError.textContent = "";

    clearChatUI();
    addMessage("История чата очищена", "ai");
};

/* =========================
   EVENTS
========================= */

sendBtn.onclick = sendMessage;
collectBtn.onclick = collectData;
saveTokenBtn.onclick = saveToken;


userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

/* =========================
   INIT
========================= */

window.addEventListener("load", async () => {
    clearChatUI();
    
    try {
        const res = await fetch("http://127.0.0.1:8000/history", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                session_id: sessionId
            })
        });
        const data = await res.json();

        // ожидаем: [{role: "user/ai", content: "..."}]
        if (data.history && Array.isArray(data.history)) {
            data.history.forEach(msg => {
                addMessage(msg.content, msg.role);
            });
        }

    } catch (e) {
        console.error("Failed to load history:", e);
    }
});
