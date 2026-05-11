# backend/redis_client.py
import redis
import json

r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

def safe_load(data):
    try:
        return json.loads(data)
    except:
        return None

# ---------- CHAT ----------
MAX_MESSAGES = 50
def add_message(session_id: str, role: str, content: str):
    key = f"chat:{session_id}"
    r.rpush(key, json.dumps({
        "role": role,
        "content": content
    }))
    # оставить только последние N сообщений (чтобы агент не сошел с ума) + TTL сутки
    r.ltrim(key, -MAX_MESSAGES, -1)
    r.expire(key, 86400) 

def get_history_by_session(session_id: str):
    key = f"chat:{session_id}"
    data = r.lrange(key, 0, -1)
    return [safe_load(x) for x in data if x]

def clear_history(session_id: str):
    r.delete(f"chat:{session_id}")

# ---------- AUTH (token/folder) ----------
def set_auth(session_id: str, iam_token: str, folder_id: str):
    r.set(f"auth:{session_id}", json.dumps({
        "iam_token": iam_token,
        "folder_id": folder_id
    }),
    ex=86400  
    )

def get_auth(session_id: str):
    data = r.get(f"auth:{session_id}")
    return safe_load(data) if data else None

def clear_auth(session_id: str):
    r.delete(f"auth:{session_id}")

# ---------- DATA (compute/vpc/s3) ----------
def set_data(session_id: str, data: dict):
    r.set(f"data:{session_id}", json.dumps(data), ex=86400)  

def get_data(session_id: str):
    data = r.get(f"data:{session_id}")
    return safe_load(data) if data else {}

def clear_data(session_id: str):
    r.delete(f"data:{session_id}")

