import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any
from openai import OpenAI

ollama_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)


def _make_json_safe(obj: Any) -> Any:
    """Рекурсивно преобразует datetime и нестандартные типы в строки"""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(i) for i in obj]
    if isinstance(obj, datetime) or hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj if isinstance(obj, (str, int, float, bool, type(None))) else str(obj)


def _parse_json_response(text: str) -> List[str]:
    try:
        cleaned = re.sub(r'^```json\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)

        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str)]

        if isinstance(data, dict) and "recommendations" in data:
            recs = data["recommendations"]
            if isinstance(recs, list):
                results = []
                for item in recs:
                    if isinstance(item, dict):
                        parts = []
                        if "action" in item: parts.append(str(item["action"]))
                        if "reason" in item: parts.append(str(item["reason"]))
                        results.append(". ".join(parts) + "." if len(parts) > 1 else "".join(parts))
                    elif isinstance(item, str):
                        results.append(item)
                return results if results else []
        return []
    except Exception as e:
        print(f"Parse error: {e}")
        return []


def generate_llm_recommendations(profile: Dict, metrics: Dict, conflict: Dict = None) -> List[str]:
    safe_profile = _make_json_safe(profile)
    safe_metrics = _make_json_safe(metrics)

    prompt = f"""Ты AI-аналитик рабочих графиков. Проанализируй метрики и профиль, дай 2-3 совета.
ВАЖНЫЕ ПРАВИЛА:
1. Фокусируйся на метриках > 0.4 или == 0.
2. ЗАПРЕЩЕНЫ общие фразы. Пиши конкретно.
3. Верни ТОЛЬКО JSON: {{"recommendations": ["Совет 1", "Совет 2"]}}
ДАННЫЕ:
Метрики: {json.dumps(safe_metrics, ensure_ascii=False)}
Профиль: {json.dumps(safe_profile, ensure_ascii=False)}
"""
    try:
        response = ollama_client.chat.completions.create(
            model="llama3.1",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=300,
            timeout=15.0
        )
        raw_text = response.choices[0].message.content
        return _parse_json_response(raw_text) or ["Не удалось сгенерировать рекомендации."]
    except Exception as e:
        print(f"Ollama error: {e}")
        return []


def generate_conflict_explanation(conflict: Dict, profile: Dict, action: str, new_time: str) -> str:
    safe_conflict = _make_json_safe(conflict)
    safe_profile = _make_json_safe(profile)
    if not new_time: new_time = "ближайшее свободное время"

    prompt = f"""Ты — персональный AI-ассистент по управлению рабочим графиком. Помоги сотруднику быстро решить проблему в календаре.

    ДАННЫЕ:
    - Сотрудник: {profile.get('name', 'Коллега')} {profile.get('surname', '')}
    - Конфликт: {conflict.get('type', 'Пересечение')} ({conflict.get('description', 'Наложение задач')})
    - Решение: {action} на {new_time}

    ЗАДАЧА:
    Объясни причину решения в 1-2 предложениях. Будь вежлив, конкретен и фокусируйся на пользе для сотрудника.

    ПРАВИЛА (СТРОГО):
    1. Только чистый текст. Никаких кавычек, markdown, заголовков или приветствий.
    2. Начни сразу с обращения по имени или сути решения.
    3. Чётко свяжи тип конфликта с предлагаемым действием.
    4. Запрещены общие фразы, извинения или лишние рекомендации.

    ПРИМЕРЫ:
    Хорошо: Иван, чтобы избежать наложения задач, предлагаю перенести встречу на 11:00 — это ближайшее свободное время.
    Плохо: "Вот решение: ..." / Надеюсь, подойдёт... / Текст в кавычках или с лишними словами.

    Верни ТОЛЬКО готовое сообщение.
    """

    try:
        response = ollama_client.chat.completions.create(
            model="llama3.1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100,
            timeout=10.0
        )
        text = response.choices[0].message.content.strip()
        return text.replace('"', '').replace("'", "")
    except Exception as e:
        print(f"LLM Explanation Error: {e}")
        return ""