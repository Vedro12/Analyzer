import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from backend.ai.ai_agent import run_ai_chat
from backend.storage import load_json_file, save_data
from backend.collectors.collector import (
    collect_all_compute_data,
    collect_all_s3_data,
    collect_all_vpc_data
)
from backend import config
import aiohttp
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str

chat_history = []

@app.get("/")
def home():
    return FileResponse("frontend/index.html")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.post("/ai-chat")
def ai_chat(msg: ChatMessage):
    global chat_history

    data = {
        "compute": load_json_file("backend/data/compute.json"),
        "s3": load_json_file("backend/data/s3.json"),
        "vpc": load_json_file("backend/data/vpc.json")
    }

    answer, updated_history = run_ai_chat(
        msg.message,
        data,
        chat_history
    )

    chat_history = updated_history

    return {
        "answer": answer,
        "history": chat_history
    }

@app.post("/collect")
async def collect_info():
    compute_task = collect_all_compute_data()
    s3_task = collect_all_s3_data()
    vpc_task = collect_all_vpc_data()
    await asyncio.gather(compute_task, s3_task, vpc_task)
    return {"status": "ok"}

@app.post("/set-token")
async def set_token(request: Request):
    try:
        data = await request.json()
        token = (data.get("token") or "").strip()
        folder_id = (data.get("folder_id") or "").strip()
        if not token or not folder_id:
            return {
                "status": "error",
                "message": "Не заполнены поля с OAuth-токеном и идентификатором каталога. Без их указания рекомендации будут общими, без учёта ваших ресурсов"
            }
        if len(token) < 50 or " " in token:
            return {
                "status": "error",
                "message": "Некорректная длина OAuth-токена"
            }
        if not folder_id.isalnum() or not folder_id.islower():
            return {
                "status": "error",
                "message": "Идентификатор каталога должен содержать только строчные латинские буквы и цифры"
            }

        if not (20 <= len(folder_id) <= 25):
            return {
                "status": "error",
                "message": "Некорректная длина идентификатора каталога"
            }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://iam.api.cloud.yandex.net/iam/v1/tokens",
                json={"yandexPassportOauthToken": token},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    return {
                        "status": "error",
                        "message": "Невалидный OAuth-токен"
                    }
                resp_data = await response.json()

        iam_token = resp_data.get("iamToken")
        if not iam_token:
            return {
                "status": "error",
                "message": "Не удалось получить IAM токен"
            }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders/{folder_id}",
                headers={"Authorization": f"Bearer {iam_token}"}
            ) as response:

                if response.status != 200:
                    return {
                        "status": "error",
                        "message": "Каталог с указанным идентификатором не найден. Пожалуйста, проверьте корректность идентификатора"
                    }

        # ===== 6. Сохраняем =====
        config.iam_token = iam_token
        config.folder_id = folder_id

        return {
            "status": "ok",
            "message": "Токен успешно установлен"
        }

    except asyncio.TimeoutError:
        return {
            "status": "error",
            "message": "Таймаут при установке токена"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }

@app.post("/clear-data")
def clear_data():
    global chat_history

    chat_history = []

    data_dir = Path("backend/data")
    for file in data_dir.glob("*.json"):
        try:
            file.unlink()
        except Exception:
            pass

    return {"status": "cleared"}

@app.get("/history")
def get_history():
    return {"history": chat_history}