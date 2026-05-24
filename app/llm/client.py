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

def _clean_recommendations(recs: List[str]) -> List[str]:
    """Вырезает технические имена метрик из рекомендаций"""
    cleaned = []
    for r in recs:
        # Убираем паттерны вида "H_i_hr_conflict = 0.5" или "(L_i_workload)"
        r = re.sub(r'\b[A-Z]_i_[a-z_]+\b\s*=?\s*\d*\.?\d*', '', r)
        r = re.sub(r'\s+', ' ', r).strip()
        if r:
            cleaned.append(r)
    return cleaned if cleaned else ["Основные показатели в диапазоне нормы. График стабилен."]


# Замени сигнатуру функции:
def generate_llm_recommendations(profile: Dict, metrics: Dict, hr_data: Dict = None, conflict: Dict = None) -> List[
    str]:
    safe_profile = _make_json_safe(profile)
    safe_metrics = _make_json_safe(metrics)

    # 🔒 PYTHON GUARD
    # 1. ПРОВЕРКА ОТПУСКА (теперь берём из отдельного параметра)
    vac_flag = (hr_data or {}).get('on_vacation')
    if vac_flag in [True, 'true', 1, '1']:
        return ["Сотрудник официально в отпуске. Встречи в календаре требуют ручного подтверждения или отмены."]

    # 2. ПРОВЕРКА PART-TIME
    emp_raw = safe_profile.get('employmentType') or safe_profile.get('employment', 'FULL_TIME')
    emp_type = str(emp_raw).upper().replace('-', '_')
    workload = safe_metrics.get('L_i_workload', 0)
    total_hours = safe_metrics.get('total_task_hours', 0) or safe_metrics.get('hours', 0)

    if emp_type == 'PART_TIME' and (workload > 0.3 or total_hours > 4):
        return ["Нагрузка превышает лимит для PART_TIME. Рекомендуется сократить задачи или пересмотреть контракт."]


    name = safe_profile.get("name", "Коллега")
    surname = safe_profile.get("surname", "")
    full_name = f"{name} {surname}".strip() or "Коллега"
    work_start = safe_profile.get("work_hours", {}).get("start", "09:00")
    work_end = safe_profile.get("work_hours", {}).get("end", "18:00")

    system_prompt = """Ты — AI-аналитик рабочих графиков. Твоя задача: сформировать 2-3 персонализированные рекомендации на русском языке.

    ПРИОРИТЕТНЫЕ ПРАВИЛА (проверять строго в этом порядке):
    1. ЕСЛИ on_vacation == true → ВЕРНИ ТОЛЬКО: "Сотрудник официально в отпуске. Встречи в календаре требуют ручного подтверждения или отмены."
    2. ЕСЛИ employmentType == "PART_TIME" → сравни нагрузку с 4ч. Если задач >4 часов → пиши: "Нагрузка превышает лимит PART_TIME. Рекомендуется сократить задачи или перейти на FULL_TIME."
    3. Анализируй метрики. Давай советы ТОЛЬКО если значение >0.3.
    4. Если ВСЕ метрики в норме (<0.3) И нет сработавших флагов выше → ВЕРНИ ТОЛЬКО: "Основные показатели в диапазоне нормы. График стабилен, рисков перегрузки или конфликтов не обнаружено. Рекомендуем поддерживать текущий режим работы."

    ОБЩИЕ ТРЕБОВАНИЯ:
    - Каждый совет: [Действие] + [Причина из данных] + [Польза/Риск].
    - Тон: профессиональный, конкретный, без воды.
    - ЗАПРЕЩЕНО: общие фразы, придумывание фактов, упоминание технических имён метрик (C_i_*, L_i_* и т.д.). Используй только человеческий язык: 'доля встреч', 'уровень загрузки', 'свежесть данных'.
    - ЗАПРЕЩЕНО: рекомендовать «увеличить нагрузку», «добавить задачи», «повысить продуктивность» при низкой загрузке. Низкая загрузка — НЕ проблема для риска выгорания.
    - Формат ответа: ТОЛЬКО валидный JSON: {"recommendations": ["Совет 1", "Совет 2"]}
    """

    user_prompt = f"""<data>
    Сотрудник: {full_name}
    Рабочие часы: {work_start}–{work_end}
    Тип занятости: {safe_profile.get('employmentType', 'FULL_TIME')} 
    В отпуске: {safe_profile.get('hr_data', {}).get('on_vacation', False)}  
    Профиль обновлён: {safe_profile.get('last_updated', 'неизвестно')}  
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
        raw_recs = _parse_json_response(response.choices[0].message.content)
        return _clean_recommendations(raw_recs) if raw_recs else ["Не удалось сгенерировать рекомендации."]

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
