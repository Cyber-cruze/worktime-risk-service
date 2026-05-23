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
        data = json.loads(cleaned)

        if isinstance(data, dict) and "recommendations" in data:
            return [str(item) for item in data["recommendations"] if isinstance(item, str)]

        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str)]

        return []
    except Exception:
        return []


def generate_llm_recommendations(profile: Dict, metrics: Dict, conflict: Dict = None) -> List[str]:
    prompt = f"""Ты AI-ассистент по анализу рабочих графиков.
Проанализируй данные: {json.dumps({"profile": profile, "metrics": metrics}, ensure_ascii=False)}

ЗАДАЧА: Сформируй 2-3 конкретных совета на русском языке.
ФОРМАТ: Верни ТОЛЬКО валидный JSON-объект с ключом "recommendations".
ПРИМЕР: {{"recommendations": ["Совет 1", "Совет 2"]}}
НЕ ПОВТОРЯЙ ВХОДНЫЕ ДАННЫЕ. НЕ ДОБАВЛЯЙ ЛИШНИХ ПОЛЕЙ."""

    try:
        response = ollama_client.chat.completions.create(
            model="llama3.1",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,  
            max_tokens=300,
            timeout=15.0
        )

        raw_text = response.choices[0].message.content
        print(f"🔍 LLM raw response: {raw_text[:150]}...")

        parsed = _parse_json_response(raw_text)
        if not parsed:
            print("️ LLM returned empty or unparseable response")
            return []
        return parsed

    except Exception as e:
        print(f"️ Ollama error: {e}")
        return []