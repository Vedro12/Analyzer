# backend/ai/ai_agent.py
import openai
import json

client = openai.OpenAI(
    api_key="",
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=""
)

def run_ai_chat(user_input: str, data: dict, history: list | None = None):
    rules = load_rules()
    history = history or []

    system_prompt = f"""
                    Ты — AI-ассистент по выявлению проблем в облачной инфраструктуры.
                    """


    messages = [{"role": "system", "content": system_prompt}]

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": user_input
    })
    qwen3 = "gpt://***************/qwen3-235b-a22b-fp8/latest"
    response = client.responses.create(
        model=qwen3,
        input=messages,
        tools=[
            {
                "type": "web_search"
            }
        ],
        temperature=0.3,
        max_output_tokens=300
    )
    return response.output_text

def load_rules():
    with open("backend/ai/rules.json", "r", encoding="utf-8") as f:
        return json.load(f)
    