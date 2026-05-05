/* =========================
   FRONTEND (frontend/app.js)
========================= */
const chatBox = document.getElementById("chat-box");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const collectBtn = document.getElementById("collect-btn");
const resetBtn = document.getElementById("reset-btn");
const tokenInput = document.getElementById("iam-token-input");
const folderInput = document.getElementById("folder-id-input");
const saveTokenBtn = document.getElementById("save-token-btn");

let isCollected = false;
let oauthToken = localStorage.getItem("iamToken") || "";
let folderId = localStorage.getItem("folderId") || "";

const tokenError = document.getElementById("token-error");
const folderError = document.getElementById("folder-error");

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
   INIT INPUTS
========================= */

tokenInput.value = oauthToken;
folderInput.value = folderId;

tokenInput.addEventListener("input", () => {
    oauthToken = tokenInput.value.trim();
    localStorage.setItem("iamToken", oauthToken);
});

folderInput.addEventListener("input", () => {
    folderId = folderInput.value.trim();
    localStorage.setItem("folderId", folderId);
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
    if (id.length < 20 || id.length > 25) return "Неверная длина идентификатора каталога";
    return "";
}

tokenInput.addEventListener("input", () => {
    tokenError.textContent = validateToken(tokenInput.value.trim());
});

folderInput.addEventListener("input", () => {
    folderError.textContent = validateFolderId(folderInput.value.trim());
});

/* =========================
   UI HELPERS
========================= */

function scrollChat() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function clearChatUI() {
    chatBox.innerHTML = `
        <div class="welcome-message">
            <div class="avatar ai-avatar"></div>
            <div class="welcome-content">
                <h3>Привет! Я ваш AI-ассистент</h3>
                <p>Задайте мне любой вопрос или попросите о помощи — я с радостью отвечу.</p>
            </div>
        </div>
    `;
}

/* =========================
   MESSAGE RENDER (NO HISTORY LOGIC HERE)
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

function enhanceCodeBlocks(container) {
    const blocks = container.querySelectorAll("pre");

    blocks.forEach((pre) => {
        const code = pre.querySelector("code");

        // язык из class="language-js"
        let lang = "code";
        const match = code?.className?.match(/language-(\w+)/);
        if (match) lang = match[1];

        // бейдж языка
        const langLabel = document.createElement("div");
        langLabel.className = "code-lang";
        langLabel.textContent = lang;

        // кнопка копирования
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

window.addEventListener("load", async () => {
    clearChatUI();
    initOnboarding(); 
    
    try {
        const res = await fetch("http://127.0.0.1:8000/history", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
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

function removeLoadingMessage() {
    const el = document.getElementById("loading-msg");
    if (el) el.remove();
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

/* =========================
   SEND MESSAGE (BACKEND OWNS HISTORY)
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
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                message
            })
        });
        const data = await res.json();

        if (data.status !== "ok") {
            addMessage(data.message || "Ошибка при получении ответа", "ai");
            return;
        }
        // backend возвращает полный ответ + (опционально) историю
        addMessage(data.answer, "ai");

    } catch (e) {
        addMessage("Ошибка: " + e, "ai");
    }
    removeLoadingMessage();
    sendBtn.disabled = false;
}

sendBtn.onclick = sendMessage;

userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

/* =========================
   COLLECT DATA
========================= */

collectBtn.onclick = async () => {
    if (!oauthToken || !folderId) {
        addMessage("Нужны токен и folder ID", "ai");
        return;
    }

    try {
        const res = await fetch("http://127.0.0.1:8000/collect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId
            })
        });

        const data = await res.json();

        if (data.status !== "ok") {
            addMessage(data.message || "Ошибка сбора данных", "ai");
            return;
        }

        isCollected = true;
        addMessage(data.message || "Данные инфраструктуры собраны", "ai");

    } catch (e) {
        addMessage("Ошибка: " + e, "ai");
    }
};

/* =========================
   RESET CHAT (SERVER OWNS HISTORY)
========================= */

resetBtn.onclick = async () => {
    if (!confirm("Все собранные данные о ресурсах и история переписки будут удалены без возможности воостановления. Очистить чат?")) return;

    const res = await fetch("http://127.0.0.1:8000/clear-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            session_id: sessionId
        })
    });

    const data = await res.json();

    if (data.status !== "cleared") {
        addMessage(data.message || "Ошибка очистки", "ai");
        return;
    }
    

    localStorage.removeItem("iamToken");
    localStorage.removeItem("folderId");

    oauthToken = "";
    folderId = "";

    tokenInput.value = "";
    folderInput.value = "";

    tokenError.textContent = "";
    folderError.textContent = "";
    
    isCollected = false;
    clearChatUI();
    addMessage("История чата очищена", "ai");
};

/* =========================
   SAVE TOKEN
========================= */

saveTokenBtn.onclick = async () => {
    const tokenErr = validateToken(oauthToken);
    const folderErr = validateFolderId(folderId);

    tokenError.textContent = tokenErr;
    folderError.textContent = folderErr;

    if (tokenErr || folderErr) return;

    try {
        const res = await fetch("http://127.0.0.1:8000/set-token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
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

        addMessage("Токен успешно сохранён", "ai");

    } catch (e) {
        addMessage("Ошибка соединения: " + e, "ai");
    }
};

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

let modal;
let slides;
let nextBtn;
let prevBtn;

let currentSlide = 0;

function initOnboarding(force = false) {
    modal = document.getElementById("onboarding-modal");
    slides = document.querySelectorAll(".onboarding-slide");
    nextBtn = document.getElementById("next-slide");
    prevBtn = document.getElementById("prev-slide");

    if (!modal || !nextBtn || !prevBtn || slides.length === 0) return;

    const done = localStorage.getItem("onboardingDone");

    if (done && !force) {
        modal.classList.add("hidden");
        return;
    }

    currentSlide = 0;
    modal.classList.remove("hidden");

    renderDots();
    render();

    // важно: НЕ копим обработчики
    nextBtn.onclick = handleNext;
    prevBtn.onclick = handlePrev;
}

function handleNext() {
    if (currentSlide < slides.length - 1) {
        currentSlide++;
        render();
    } else {
        closeOnboarding();
    }
}

function handlePrev() {
    if (currentSlide > 0) {
        currentSlide--;
        render();
    }
}

function render() {
    slides.forEach((s, i) => {
        s.classList.toggle("active", i === currentSlide);
    });

    if (prevBtn) {
        prevBtn.style.visibility = currentSlide === 0 ? "hidden" : "visible";
    }

    if (nextBtn) {
        nextBtn.textContent =
            currentSlide === slides.length - 1 ? "Начать" : "Далее →";
    }

    updateDots();
}

function renderDots() {
    const container = document.querySelector(".onboarding-progress");
    if (!container) return;

    container.innerHTML = "";

    for (let i = 0; i < slides.length; i++) {
        const dot = document.createElement("div");
        dot.className = "dot";
        container.appendChild(dot);
    }

    updateDots();
}

function updateDots() {
    const dots = document.querySelectorAll(".onboarding-progress .dot");

    dots.forEach((dot, i) => {
        dot.classList.toggle("active", i === currentSlide);
    });
}

function closeOnboarding() {
    modal.classList.add("hidden");
    localStorage.setItem("onboardingDone", "true");
}

function restartOnboarding() {
    localStorage.removeItem("onboardingDone");

    const modal = document.getElementById("onboarding-modal");
    if (!modal) return;

    modal.classList.remove("hidden");

    currentSlide = 0;
    initOnboarding(true);
}

document.getElementById("restart-onboarding-btn")
    .onclick = restartOnboarding;


const menuBtn = document.getElementById("menu-btn");
const sidebar = document.querySelector(".sidebar");
const overlay = document.getElementById("overlay");

menuBtn.onclick = () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("active");
};

overlay.onclick = () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("active");
};

const input = document.getElementById("user-input");

input.addEventListener("input", () => {
    input.style.height = "auto";                 // сброс
    input.style.height = input.scrollHeight + "px"; // рост
});