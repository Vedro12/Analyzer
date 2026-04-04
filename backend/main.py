# backend/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
from backend.ai.ai_agent import run_ai_chat
from backend.storage import  load_json_file, save_data
from backend.collectors.collector import yc_get_s3_info, yc_get_vpc_info, call_compute, call_api_safely
from backend import config
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request

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
    history: list = []

@app.post("/ai-chat")
def ai_chat(msg: ChatMessage):

    data = {
        "compute": load_json_file("backend/data/compute.json"),
        "s3": load_json_file("backend/data/s3.json"),
        "vpc": load_json_file("backend/data/vpc.json")
    }

    answer, history = run_ai_chat(msg.message, data, msg.history)

    return {
        "answer": answer,
        "history": history
    }

@app.post("/collect")
def collect_info():
    # --------------- COMPUTE ----------------
    call_compute("instances", "instance_id")
    call_compute("disks", "disk_id")
    call_compute("images", "image_id")
    call_compute("snapshots", "snapshot_id")

    # ------------------ S3 ------------------
    s3_resp = call_api_safely(yc_get_s3_info)
    buckets = s3_resp.get("buckets", []) if isinstance(s3_resp, dict) else []

    result_s3 = []

    for bucket in buckets:
        name = bucket.get("name")

        result_s3.append({
            "bucket": bucket,
            "stats": call_api_safely(yc_get_s3_info, endpoint=f"/{name}:getStats", use_folder=False),
            "https": call_api_safely(yc_get_s3_info, endpoint=f"/{name}:getHttpsConfig", use_folder=False),
            "bindings": call_api_safely(yc_get_s3_info, endpoint=f"/{name}:listAccessBindings", use_folder=False),
            "inventory": call_api_safely(yc_get_s3_info, endpoint=f"/{name}:listInventoryConfiguration", use_folder=False)
        })

    save_data(result_s3, "backend/data/s3.json")

    # ------------------ VPC ------------------
    vpc_data = [{
        "addresses": call_api_safely(yc_get_vpc_info, endpoint="addresses"),
        "gateways": call_api_safely(yc_get_vpc_info, endpoint="gateways"),
        "networks": call_api_safely(yc_get_vpc_info, endpoint="networks"),
        "routeTables": call_api_safely(yc_get_vpc_info, endpoint="routeTables"),
        "securityGroups": call_api_safely(yc_get_vpc_info, endpoint="securityGroups"),
        "subnets": call_api_safely(yc_get_vpc_info, endpoint="subnets"),
    }]

    save_data(vpc_data, "backend/data/vpc.json")
    return {"status": "ok"}

@app.post("/set-token")
async def set_token(request: Request):
    try:
        # Получаем JSON данные из запроса
        data = await request.json()
        
        token = data.get("token")
        folder_id = data.get("folder_id")
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        
        response = requests.post(
            url,
            json={"yandexPassportOauthToken": token}
        )
        response.raise_for_status()
        
        iam_token = response.json()["iamToken"]
        
        # Сохраняем в конфиг
        config.iam_token = iam_token
        config.folder_id = folder_id
        
        return {
            "status": "ok", 
            "message": "Токен успешно установлен"
        }
        
    except requests.exceptions.HTTPError:
        return {
            "status": "error", 
            "message": "Токен не установлен"
        }

@app.post("/clear-data")
def clear_data():
    data_dir = Path("backend/data")

    for file in data_dir.glob("*.json"):
        try:
            file.unlink()
        except Exception:
            pass

    return {"status": "cleared"}

if __name__ == "__main__":
    app()