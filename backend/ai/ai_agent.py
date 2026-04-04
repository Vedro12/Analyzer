# backend/ai/ai_agent.py

import openai
import json
import os

client = openai.OpenAI(
    api_key="",
    base_url="https://ai.api.cloud.yandex.net/v1",
    project=""
)

def run_ai_chat(user_input, data, history=None):
    data = load_all_data()
    rules = load_rules()
    if history is None:
        history = []

    system_prompt = f"""
                    Ты — AI-ассистент по выявлению проблем в облачной инфраструктуры.
                    Вот текущие данные:
                    {json.dumps(data, indent=2, ensure_ascii=False)}
                    У тебя есть БАЗА ПРАВИЛ (используй её для подходящих случаев):
                    {json.dumps(rules, indent=2, ensure_ascii=False)}

                    Ты должен:
                    - прямо и лаконично отвечать на вопросы пользователя, анализируя его инфраструктуру
                    - при нехватке данных запрашивать у него дополнительную информацию
                    - давать четкую рекомендацию по исправлению проблемы
                    - использовать базу правил для составления рекомендаций (добавляй ссылку на документацию) при подходящих случаях. Редактировать ответ под пользователя
                    - при необходимости использовать искать ответ в интернете. В первую очередь https://yandex.cloud/ru и https://aistudio.yandex.ru/docs/ru/ 
                    - ответ не более 80 слов
                    """

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    for msg in history:
        messages.append(msg)

    messages.append({"role": "user", "content": user_input})
    qwen3 = f"gpt:///qwen3-235b-a22b-fp8/latest"

    response = client.responses.create(
        model= qwen3,
        input=messages,
        tools=[
            {
                "type": "web_search",
            },
        ],
        temperature=0.3,
        max_output_tokens=300
    )

    answer = response.output_text

    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": answer})

    return answer, history

def load_rules():
    with open("backend/ai/rules.json", "r", encoding="utf-8") as f:
        return json.load(f)
    
def load_all_data():
    base_path = "backend/data"

    def load_file(filename):
        path = os.path.join(base_path, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "compute": load_file("compute.json"),
        "vpc": load_file("vpc.json"),
        "s3": load_file("s3.json"),
    }