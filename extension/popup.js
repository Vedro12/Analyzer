/* ========================= EXTENSION (extension/popup.js) ========================= */
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
const openSiteBtn = document.getElementById("open-site-btn");

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

async function collectData() {
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

        addMessage(chatBox, data.message || "Данные инфраструктуры собраны", "system");

    } catch (e) {
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    }
}

async function saveToken() {
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
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    }
}

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

        clearChatUI();
        addMessage(chatBox, data.message || "Сессия, токен, история и данные очищены", "system");

    } catch (e) {
        addMessage(chatBox, "Ошибка: " + e.message, "error");
    }
};

sendBtn.onclick = sendMessage;
collectBtn.onclick = collectData;
saveTokenBtn.onclick = saveToken;

openSiteBtn.onclick = () => {
    chrome.tabs.create({
        url: "http://84.252.135.249"
    });
};

userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

setupPasswordToggle();

window.addEventListener("load", async () => {
    clearChatUI();

    try {
        await loadHistory(chatBox, sessionId);
    } catch (e) {
        console.error("Failed to load history:", e);
    }
});