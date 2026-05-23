import os
import json
import re
from typing import Dict, List
from openai import OpenAI


ollama_client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)


def _parse_json_response(text: str) -> List[str]:

    try:

        cleaned = re.sub(r'^```json\s*|\s*```$', '', text.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return []


def generate_llm_recommendations(profile: Dict, metrics: Dict, conflict: Dict = None) -> List[str]:
    system_prompt = """Ты AI-ассистент по оптимизации рабочих графиков и предотвращению выгорания.
Ты получаешь профиль сотрудника, метрики риска и (опционально) данные о конфликте.
Сформируй 2-3 конкретных, конструктивных совета на русском языке.
Верни ТОЛЬКО валидный JSON-массив строк. Пример: ["Совет 1", "Совет 2"]"""

    user_context = {
        "profile": profile,
        "metrics": metrics,
        "conflict": conflict
    }

    try:
        response = ollama_client.chat.completions.create(
            model="llama3.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_context, ensure_ascii=False)}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=400,
            timeout=15.0
        )

        raw_text = response.choices[0].message.content
        parsed = _parse_json_response(raw_text)

        if not parsed:
            return ["[LLM] Не удалось сформировать рекомендации. Используйте стандартные правила."]
        return parsed

    except Exception as e:
        print(f"️ Ollama Fallback triggered: {e}")
        return []