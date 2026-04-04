const chatBox = document.getElementById("chat-box");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const collectBtn = document.getElementById("collect-btn");
const resetBtn = document.getElementById("reset-btn");
const tokenInput = document.getElementById("iam-token-input");
const folderInput = document.getElementById("folder-id-input");
const saveTokenBtn = document.getElementById("save-token-btn");

let chatHistory = [];
let isCollected = false;
let iamToken = null;
let folderId = null;



async function saveState() {
    await chrome.storage.local.set({ chatHistory, isCollected });
}

function scrollChat() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendTokenToBackend() {
    try {
        await fetch("http://127.0.0.1:8000/set-token", {
            method: "POST",
            body: JSON.stringify({ token: iamToken, folder_id: folderId })
        });

        chatBox.innerHTML += `<div><i>Токен сохранён</i></div>`;
        scrollChat();
    } catch (err) {
        chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> Ошибка отправки токена: ${err}</div>`;
        scrollChat();
    }
}

function addMessage(text, role) {
    const msg = document.createElement("div");
    msg.classList.add("message");
    msg.classList.add(role === "user" ? "user-message" : "ai-message");

    msg.innerHTML = renderMarkdown(text);

    chatBox.appendChild(msg);
    scrollChat();
}

window.addEventListener("load", async () => {
    const data = await chrome.storage.local.get(["chatHistory", "isCollected", "iamToken", "folderId"]);
    chatHistory = data.chatHistory || [];
    isCollected = data.isCollected || false;
    iamToken = data.iamToken || "";
    folderId = data.folderId || "";

    tokenInput.value = iamToken;
    folderInput.value = folderId;
    
    chatHistory.forEach(msg => {
        chatBox.innerHTML += `<div><b>${msg.role === "user" ? "Вы" : "AI"}:</b> ${msg.content}</div>`;
    });
    scrollChat();
});

async function sendMessage() {
    const message = input.value.trim();
    if (!message) return;
    chatBox.innerHTML += `<div><b>Вы:</b> ${message}</div>`;
    input.value = "";
    scrollChat();

    if (!isCollected) {
        if (iamToken && folderId) {
            // Токен есть — собираем данные
            chatBox.innerHTML += `<div><b>AI:</b> <i>Собираю данные для анализа. Пожалуйста, подождите...</i></div>`;
            scrollChat();

            try {
                await fetch("http://127.0.0.1:8000/collect", { method: "POST" });
                isCollected = true;
                await saveState();
                chatBox.innerHTML += `<div><b>AI:</b> <i>Данные собраны</i></div>`;
                scrollChat();
            } catch (err) {
                chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> Ошибка сбора данных: ${err}</div>`;
                scrollChat();
            }
        } else {
            chatBox.innerHTML += `<div style="color:orange;"><b>AI:</b>Для анализа инфраструктуры нужны IAM токен и folder ID. Общение возможно, но рекомендации будут ограничены.</div>`;
            scrollChat();
        }
    }

    try {
        const response = await fetch("http://127.0.0.1:8000/ai-chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, history: chatHistory })
        });
        const data = await response.json();
        chatHistory = data.history;
        chatBox.innerHTML += `<div><b>AI:</b> ${data.answer}</div>`;
        scrollChat();
        await saveState();
    } catch (err) {
        chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> Ошибка: ${err}</div>`;
        scrollChat();
    }
}

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendMessage();
        e.preventDefault();
    }
});

collectBtn.addEventListener("click", async () => {
    if (!iamToken || !folderId) {
        chatBox.innerHTML += `<div style="color:orange;"><b>AI:</b> Для сбора данных нужен Oauth-токен и ID каталога. Пожалуйста, введите их выше.</div>`;
        scrollChat();
        return;
    }

    chatBox.innerHTML += `<div><b>AI:</b> <i>Собираю данные для анализа. Пожалуйста, подождите...</i></div>`;
    scrollChat();

    if (isCollected) {
        try {
            await fetch("http://127.0.0.1:8000/clear-data", { method: "POST" });  
            isCollected = false;
            await saveState();
            chatBox.innerHTML += `<div><i>Старые данные очищены</i></div>`;
            scrollChat();
        } catch (err) {
            chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> Ошибка очистки старых данных: ${err}</div>`;
            scrollChat();
            return;
        }
    }

    try {
        await fetch("http://127.0.0.1:8000/collect", { method: "POST" });
        isCollected = true;
        await saveState();
        chatBox.innerHTML += `<div><b>AI:</b> <i>Данные собраны</i></div>`;
        scrollChat();
    } catch (err) {
        chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> Ошибка сбора данных: ${err}</div>`;
        scrollChat();
    }
});

resetBtn.addEventListener("click", async () => {
    try {
        await fetch("http://127.0.0.1:8000/clear-data", { method: "POST" });
    } catch (err) {
        chatBox.innerHTML += `<div style="color:red;"><b>AI:</b> <i>Ошибка обновления чата: ${err}</i></div>`;
        scrollChat();
    }

    chatHistory = [];
    chatBox.innerHTML = "";
    isCollected = false;
    await chrome.storage.local.clear();

    chatBox.innerHTML += `<div><i>Чат обновлён</i></div>`;
    scrollChat();
});

saveTokenBtn.addEventListener("click", async () => {
    iamToken = tokenInput.value.trim();
    folderId = folderInput.value.trim();

    if (!iamToken || !folderId) {
        alert("Введите токен и folder ID!");
        return;
    }

    await chrome.storage.local.set({ iamToken, folderId });
    sendTokenToBackend();
    scrollChat();
});

document.addEventListener("click", function (e) {
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