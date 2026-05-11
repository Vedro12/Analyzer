/* ========================= FRONTEND (frontend/app.js) ========================= */
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

let isCollected = false;
let oauthToken = localStorage.getItem("iamToken") || "";
let folderId = localStorage.getItem("folderId") || "";
const sessionId = getSessionId();

marked.setOptions({
    breaks: true,
    gfm: true
});

tokenInput.value = oauthToken;
folderInput.value = folderId;

function clearChatUI() {
    chatBox.innerHTML = `
        <div class="welcome-message">
            <div class="avatar assistant-avatar"></div>
            <div class="welcome-content">
                <h3>Привет! С чем я могу помочь сегодня?</h3>
                <p>Задайте вопрос или проведите диагностику ваших ресурсов в Yandex Cloud.</p>
            </div>
        </div>
    `;
}

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

async function sendMessage() {
    sendBtn.disabled = true;

    const message = userInput.value.trim();

    if (!message) {
        sendBtn.disabled = false;
        return;
    }

    userInput.value = "";

    addMessage(chatBox, message, "user");
    addLoadingMessage(chatBox);

    try {
        const data = await sendChatMessage(sessionId, message);

        if (data.status !== "ok") {
            addMessage(chatBox, data.message || "Ошибка при получении ответа", "error");
        } else {
            addMessage(chatBox, data.answer, "assistant");
        }

    } catch (e) {
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    } finally {
        removeLoadingMessage();
        sendBtn.disabled = false;
    }
}

collectBtn.onclick = async () => {
    if (!oauthToken || !folderId) {
        addMessage(chatBox, "Для сбора данных необходимо сначала ввести OAuth-токен и идентификатор каталога", "system");
        return;
    }

    try {
        const data = await collectInfraData(sessionId);

        if (data.status !== "ok") {
            addMessage(chatBox, data.message || "Ошибка сбора данных", "error");
            return;
        }

        isCollected = true;
        addMessage(chatBox, data.message || "Данные инфраструктуры собраны", "system");

    } catch (e) {
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    }
};

resetBtn.onclick = async () => {
    if (!confirm("Все собранные данные о ресурсах и история переписки будут удалены без возможности восстановления. Очистить чат?")) return;

    try {
        const data = await clearAllData(sessionId);

        if (data.status !== "cleared") {
            addMessage(chatBox, data.message || "Ошибка очистки", "error");
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
        addMessage(chatBox, data.message || "Сессия, токен, история и данные очищены", "system");

    } catch (e) {
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    }
};

saveTokenBtn.onclick = async () => {
    const tokenErr = validateToken(oauthToken);
    const folderErr = validateFolderId(folderId);

    tokenError.textContent = tokenErr;
    folderError.textContent = folderErr;

    if (tokenErr || folderErr) return;

    try {
        const data = await saveTokenToBackend(sessionId, oauthToken, folderId);

        if (data.status !== "ok") {
            addMessage(chatBox, data.message || "Ошибка сохранения токена", "error");
            return;
        }

        addMessage(chatBox, data.message || "Токен успешно установлен", "system");

    } catch (e) {
        addMessage(chatBox, "Ошибка соединения: " + e.message, "error");
    }
};

sendBtn.onclick = sendMessage;

userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

setupPasswordToggle();

window.addEventListener("load", async () => {
    clearChatUI();
    initOnboarding();

    try {
        await loadHistory(chatBox, sessionId);
    } catch (e) {
        console.error("Failed to load history:", e);
    }
});

/* =========================
   ONBOARDING
========================= */

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
        nextBtn.textContent = currentSlide === slides.length - 1 ? "Начать" : "Далее →";
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

document.getElementById("restart-onboarding-btn").onclick = restartOnboarding;

/* =========================
   MOBILE MENU
========================= */

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

/* =========================
   AUTO RESIZE INPUT
========================= */

userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = userInput.scrollHeight + "px";
});