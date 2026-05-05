# backend/main.py
import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.ai.ai_agent import run_ai_chat
from backend.collectors.collector import (
    collect_all_compute_data,
    collect_all_s3_data,
    collect_all_vpc_data
)
import aiohttp
from fastapi.middleware.cors import CORSMiddleware
from backend.redis_client import get_auth, get_data, get_history, set_auth, set_data, add_message, clear_auth, clear_data, clear_history 
from backend.helpers import validate_token_request, get_iam_token, check_folder_exists


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SessionRequest(BaseModel):
    session_id: str

class TokenRequest(BaseModel):
    session_id: str
    token: str
    folder_id: str

class ChatMessage(BaseModel):
    session_id: str
    message: str

@app.get("/")
def home():
    return FileResponse("frontend/index.html")

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.post("/ai-chat")
def ai_chat(req: ChatMessage):
    session_id = (req.session_id or "").strip()
    user_message = (req.message or "").strip()

    if not session_id:
        return {
            "status": "error",
            "message": "Не найден ID сессии"
        }

    if not user_message:
        return {
            "status": "error",
            "message": "Сообщение не может быть пустым"
        }

    history = get_history(session_id)
    data = get_data(session_id)

    answer = run_ai_chat(
        user_input=user_message,
        data=data,
        history=history
    )

    add_message(session_id, "user", user_message)
    add_message(session_id, "assistant", answer)

    updated_history = get_history(session_id)

    return {
        "status": "ok",
        "answer": answer,
        "history": updated_history
    }

@app.post("/collect")
async def collect_info(req: SessionRequest):
    auth = get_auth(req.session_id)

    if not auth:
        return {
            "status": "error",
            "message": "Сначала укажите OAuth-токен и идентификатор каталога"
        }

    iam_token = auth["iam_token"]
    folder_id = auth["folder_id"]

    compute_task = collect_all_compute_data(iam_token, folder_id)
    s3_task = collect_all_s3_data(iam_token, folder_id)
    vpc_task = collect_all_vpc_data(iam_token, folder_id)

    compute, s3, vpc = await asyncio.gather(
        compute_task,
        s3_task,
        vpc_task
    )
    data = {
        "compute": compute,
        "s3": s3,
        "vpc": vpc
    }
    set_data(req.session_id, data)
    return {
        "status": "ok",
        "message": "Данные инфраструктуры собраны",
        "data": data
    }

@app.post("/set-token")
async def set_token(req: TokenRequest):
    try:
        token = (req.token or "").strip()
        folder_id = (req.folder_id or "").strip()
        session_id = (req.session_id or "").strip()

        error = validate_token_request(token, folder_id, session_id)
        if error:
            return {"status": "error", "message": error}

        iam_token = await get_iam_token(token)
        if not iam_token:
            return {
                "status": "error",
                "message": "Невалидный OAuth-токен"
            }

        folder_ok = await check_folder_exists(iam_token, folder_id)
        if not folder_ok:
            return {
                "status": "error",
                "message": "Каталог с указанным идентификатором не найден. Пожалуйста, проверьте корректность идентификатора"
            }

        set_auth(session_id, iam_token, folder_id)

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
    
@app.post("/clear-all")
def clear_all(req: SessionRequest):
    session_id = (req.session_id or "").strip()

    if not session_id:
        return {
            "status": "error",
            "message": "Не найден ID сессии"
        }

    clear_history(session_id)
    clear_data(session_id)
    clear_auth(session_id)

    return {
        "status": "cleared",
        "message": "Сессия, токен, история и данные очищены"
    }

@app.post("/history")
def get_history_endpoint(req: SessionRequest):
    session_id = (req.session_id or "").strip()

    if not session_id:
        return {
            "status": "error",
            "message": "Не найден ID сессии"
        }

    history = get_history(session_id)

    return {
        "status": "ok",
        "history": history
    }