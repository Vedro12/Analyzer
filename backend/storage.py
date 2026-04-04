# backend/storage.py

import json
from pathlib import Path

def save_data(data, filename: str):
    """
    Сохраняет данные в JSON файл.
    Если файл существует, добавляет новые записи.
    """
    if isinstance(data, dict):
        data = [data] 

    file_path = Path(filename)

    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                old_data = json.load(f)
            except json.JSONDecodeError:
                old_data = []
        if isinstance(old_data, dict):
            old_data = [old_data]
        combined_data = old_data + data
    else:
        combined_data = data

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

def load_json_file(file_path):
    """Загружает JSON-файл, который содержит массив объектов."""
    if not Path(file_path).exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
