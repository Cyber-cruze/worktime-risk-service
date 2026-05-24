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
                        parts = [str(v) for v in item.values() if v]
                        results.append(". ".join(parts) + "." if len(parts) > 1 else "".join(parts))
                    elif isinstance(item, str):
                        results.append(item)
                return results if results else []
        return []
    except Exception as e:
        print(f"Parse error: {e}")
        return []

def generate_llm_recommendations(profile: Dict, metrics: Dict, conflict: Dict = None) -> List[str]:
    safe_metrics = _make_json_safe(metrics)
    safe_profile = _make_json_safe(profile)
    name = safe_profile.get("name", "Коллега")
    surname = safe_profile.get("surname", "")
    full_name = f"{name} {surname}".strip() or "Коллега"
    work_start = safe_profile.get("work_hours", {}).get("start", "09:00")
    work_end = safe_profile.get("work_hours", {}).get("end", "18:00")

    system_prompt = """Ты — AI-аналитик рабочих графиков. Твоя задача: сформировать 2-3 персонализированные рекомендации на русском языке.

ПРАВИЛА:
1. Фокусируйся ТОЛЬКО на метриках со значением >0.4 или ==0.
2. Каждый совет: [Действие] + [Причина из данных] + [Польза/Риск].
3. Тон: профессиональный, конкретный, без воды.
4. ЗАПРЕЩЕНО: общие фразы ("следите за балансом", "делайте перерывы"), придумывание фактов.
5. Верни ТОЛЬКО валидный JSON: {"recommendations": ["Совет 1", "Совет 2"]}.
"ЗАПРЕЩЕНО: упоминать технические имена метрик (C_i_*, L_i_*, H_i_*, A_i_*, Z_i_*). Говори только человеческим языком: 'доля встреч', 'уровень загрузки', 'свежесть данных'.
"Давай советы ТОЛЬКО если метрика > 0.3 или == 0. Если все метрики в норме — верни 1 позитивный пункт: 'Основные показатели в диапазоне нормы. График стабилен, рисков перегрузки или конфликтов не обнаружено. Рекомендуем поддерживать текущий режим работы.'"""

    user_prompt = f"""<data>
Сотрудник: {full_name}
Рабочие часы: {work_start}–{work_end}
Метрики риска: {json.dumps(safe_metrics, ensure_ascii=False)}
</data>

<examples>
Хорошо: "Алексей, 60% встреч проходят после 18:00. Перенесите их на утренние слоты, чтобы снизить риск выгорания."
Хорошо: "Данные профиля не обновлялись 45 дней. Актуализируйте график, иначе расчёты рисков будут неточными."
Плохо: "Следите за балансом работы и отдыха" ← ЗАПРЕЩЕНО
</examples>

Верни ТОЛЬКО JSON. Без пояснений."""

    try:
        response = ollama_client.chat.completions.create(
            model="qwen2.5:14b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
            timeout=15.0
        )
        return _parse_json_response(response.choices[0].message.content) or ["Не удалось сгенерировать рекомендации."]
    except Exception as e:
        print(f"Ollama error: {e}")

        return []


def generate_conflict_explanation(conflict: Dict, profile: Dict, action: str, new_time: str) -> str:

    safe_conflict = _make_json_safe(conflict)
    safe_profile = _make_json_safe(profile)

    full_name = f"{safe_profile.get('name', 'Коллега')} {safe_profile.get('surname', '')}".strip() or "Коллега"
    conflict_desc = safe_conflict.get('description', safe_conflict.get('type', 'конфликт'))
    conflict_type = safe_conflict.get('type', 'UNKNOWN')  # ← ДОБАВЬ ЭТУ СТРОКУ

    TEMPLATES = {
        "RESCHEDULE_OVERLAP": f"{full_name}, перенос на {new_time} устранит наложение событий, освободив слот для приоритетных задач.",
        "RESCHEDULE_OUTSIDE": f"{full_name}, перенос на {new_time} вернёт встречу в рабочий график (09:00–18:00).",
        "SPLIT_MEETING": f"{full_name}, разделение встречи на две части позволит уложиться в оба слота без наложения.",
        "DELEGATE_TASK": f"{full_name}, делегирование задачи освободит календарь для ключевых активностей.",
        "CANCEL_EVENT": f"{full_name}, отмена события снимет конфликт и освободит время для текущих задач.",
        "DEFAULT": f"{full_name}, действие {action} на {new_time} устранит {conflict_desc}."
    }

    system_prompt = "Ты — классификатор конфликтов календаря. Верни ТОЛЬКО JSON: {\"template_id\": \"ID\"}"

    user_prompt = f"""<context>
Сотрудник: {full_name}
ТИП КОНФЛИКТА: {conflict_type}
Действие: {action}
Время: {new_time}
Описание: {conflict_desc}
</context>
<rules>
- Если ТИП = OUTSIDE_WORK_HOURS → RESCHEDULE_OUTSIDE
- Если ТИП = OVERLAPPING_EVENTS → RESCHEDULE_OVERLAP
- Если SPLIT → SPLIT_MEETING
- Если DELEGATE → DELEGATE_TASK
- Если CANCEL → CANCEL_EVENT
- Иначе → DEFAULT
</rules>
Верни ТОЛЬКО JSON."""

    try:
        response = ollama_client.chat.completions.create(
            model="qwen2.5:14b",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"},
            temperature=0.0, max_tokens=20, timeout=5.0
        )
        raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        data = json.loads(raw)
        template_id = str(data.get("template_id", "DEFAULT")).upper()
        result = TEMPLATES.get(template_id, TEMPLATES["DEFAULT"])
        print(f"LLM ROUTER RESULT: {result}")
        return result
    except Exception as e:
        print(f"Router fallback: {e}")
        return TEMPLATES["DEFAULT"]