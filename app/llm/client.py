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

        # 1. Прямой список строк
        if isinstance(data, list):
            return [str(item) for item in data if isinstance(item, str)]

        # 2. Объект с ключом recommendations
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
        print(f"🔍 Parse error: {e}")
        return []

def generate_llm_recommendations(profile: Dict, metrics: Dict, conflict: Dict = None) -> List[str]:
    prompt = f"""Ты AI-аналитик рабочих графиков. Проанализируй метрики и профиль, дай 2-3 совета.

ВАЖНЫЕ ПРАВИЛА:
1. Фокусируйся на метриках > 0.4 или == 0.
2. ЗАПРЕЩЕНЫ общие фразы. Пиши конкретно: "Перенести встречи", "Обновить профиль".
3. Если `C_i_outside_hours` > 0.4 → говори про перенос встреч с 09:00–18:00.
4. Если `A_i_freshness` == 0 → говори про срочное обновление профиля.
5. Если `L_i_workload` > 0.5 → говори про снижение загрузки.
6. Верни ТОЛЬКО JSON: {{"recommendations": ["Совет 1", "Совет 2"]}}

ДАННЫЕ:
Метрики: {json.dumps(metrics, ensure_ascii=False)}
Профиль: {json.dumps(profile, ensure_ascii=False)}
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
        print(f"🔍 LLM raw response: {raw_text[:200]}...")

        parsed = _parse_json_response(raw_text)
        if not parsed:
            print("LLM returned empty or unparseable response")
            return []
        return parsed

    except Exception as e:
        print(f"Ollama error: {e}")
        return []