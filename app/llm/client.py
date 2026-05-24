import os
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Any
from openai import OpenAI
import zoneinfo

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
    cleaned = []
    for r in recs:
        r = re.sub(r'\b[A-Z]_i_[a-z_]+\b\s*=?\s*\d*\.?\d*', '', r)
        r = re.sub(r'\s+', ' ', r).strip()
        if r:
            cleaned.append(r)
    return cleaned if cleaned else ["Основные показатели в диапазоне нормы. График стабилен."]


def _meetings_local_summary(meetings: List[Dict], profile_tz: str) -> str:
    if not meetings:
        return "Встреч нет."

    try:
        tz = zoneinfo.ZoneInfo(profile_tz)
    except Exception:
        tz = timezone.utc

    lines = []
    for i, m in enumerate(meetings, 1):
        start_str = m.get("start", "")
        end_str = m.get("end", "")
        try:
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            if start_dt.tzinfo is not None:
                local_start = start_dt.astimezone(tz).strftime("%H:%M")
                local_end = end_dt.astimezone(tz).strftime("%H:%M")
                lines.append(f"  {i}. {local_start}–{local_end} (локальное время)")
            else:
                lines.append(f"  {i}. {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')} (без таймзоны)")
        except Exception:
            lines.append(f"  {i}. {start_str} – {end_str}")

    return "\n".join(lines)


def generate_llm_recommendations(
        profile: Dict,
        metrics: Dict,
        hr_data: Dict = None,
        meetings: List[Dict] = None,
        conflict: Dict = None
) -> List[str]:
    safe_profile = _make_json_safe(profile)
    safe_metrics = _make_json_safe(metrics)

    # 1. ПРОВЕРКА ОТПУСКА (берём из hr_data — отдельный параметр)
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
    profile_tz = safe_profile.get("timezone", "UTC")

    # Формируем описание встреч в локальном времени
    meetings_summary = _meetings_local_summary(meetings or [], profile_tz)

    # Данные HR
    on_vacation = (hr_data or {}).get('on_vacation', False)
    official_schedule = (hr_data or {}).get('official_schedule', 'не указан')

    system_prompt = """Ты — AI-аналитик рабочих графиков. Твоя задача: сформировать 2-3 персонализированные рекомендации на русском языке.

    ПРИОРИТЕТНЫЕ ПРАВИЛА (проверять строго в этом порядке):
    1. ЕСЛИ on_vacation == true → ВЕРНИ ТОЛЬКО: "Сотрудник официально в отпуске. Встречи в календаре требуют ручного подтверждения или отмены."
    2. ЕСЛИ employmentType == "PART_TIME" → сравни нагрузку с 4ч. Если задач >4 часов → пиши: "Нагрузка превышает лимит PART_TIME. Рекомендуется сократить задачи или перейти на FULL_TIME."
    3. Анализируй метрики и расписание встреч. Указывай РЕАЛЬНОЕ время встреч (из раздела «Встречи в локальном времени»), а не выдумывай направление («после 18:00» / «рано утром»).
    4. Давай советы ТОЛЬКО если значение метрики >0.3.
    5. Если ВСЕ метрики в норме (<0.3) И нет сработавших флагов выше → ВЕРНИ ТОЛЬКО: "Основные показатели в диапазоне нормы. График стабилен, рисков перегрузки или конфликтов не обнаружено. Рекомендуем поддерживать текущий режим работы."

    ОБЩИЕ ТРЕБОВАНИЯ:
    - Каждый совет: [Действие] + [Причина из данных] + [Польза/Риск].
    - Тон: профессиональный, конкретный, без воды.
    - ОБЯЗАТЕЛЬНО: указывай конкретное время встреч из раздела «Встречи в локальном времени» (например: «встречи в 05:00 и 02:00», а не «встречи после 18:00»).
    - ЗАПРЕЩЕНО: общие фразы, придумывание фактов, упоминание технических имён метрик (C_i_*, L_i_* и т.д.). Используй только человеческий язык: 'доля встреч', 'уровень загрузки', 'свежесть данных'.
    - ЗАПРЕЩЕНО: рекомендовать «увеличить нагрузку», «добавить задачи», «повысить продуктивность» при низкой загрузке. Низкая загрузка — НЕ проблема для риска выгорания.
    - Формат ответа: ТОЛЬКО валидный JSON: {"recommendations": ["Совет 1", "Совет 2"]}
    """

    user_prompt = f"""<data>
    Сотрудник: {full_name}
    Рабочие часы: {work_start}–{work_end}
    Часовой пояс: {profile_tz}
    Тип занятости: {safe_profile.get('employmentType', 'FULL_TIME')}
    В отпуске: {on_vacation}
    Официальный график HR: {official_schedule}
    Профиль обновлён: {safe_profile.get('last_updated', 'неизвестно')}
    Метрики риска: {json.dumps(safe_metrics, ensure_ascii=False)}
    </data>

<встречи_в_локальном_времени>
{meetings_summary}
</встречи_в_локальном_времени>

<examples>
Хорошо: "Алексей, 2 из 3 встреч проходят рано утром (05:00 и 02:00 по Москве). Перенесите их на рабочие часы 09:00–18:00, чтобы снизить риск выгорания."
Хорошо: "Данные профиля не обновлялись 45 дней. Актуализируйте график, иначе расчёты рисков будут неточными."
Плохо: "67% встреч проходят после 18:00" ← ЗАПРЕЩЕНО, если встречи реально рано утром
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
    conflict_type = safe_conflict.get('type', 'UNKNOWN')
    conflict_desc = safe_conflict.get('description', 'не указано')
    conflict_severity = safe_conflict.get('severity', 3)
    work_start = safe_profile.get('workStart', '09:00:00')[:5]
    work_end = safe_profile.get('workEnd', '18:00:00')[:5]
    specialization = safe_profile.get('specialization', 'не указана')
    employment = safe_profile.get('employmentType', 'FULL_TIME')

    # Fallback-шаблоны (если LLM недоступен)
    key = (conflict_type, action)
    FALLBACK_MAP = {
        ("OUTSIDE_WORK_HOURS", "RESCHEDULE"):
            f"{full_name}, перенос на {new_time} вернёт встречу в рабочий график ({work_start}–{work_end}).",
        ("OVERLAPPING_EVENTS", "RESCHEDULE"):
            f"{full_name}, перенос на {new_time} устранит наложение событий, освободив слот для приоритетных задач.",
        ("OVERLAPPING_EVENTS", "SPLIT"):
            f"{full_name}, разделение встречи на две части позволит уложиться в оба слота без наложения.",
        ("OVERLOAD", "DELEGATE"):
            f"{full_name}, делегирование задачи освободит календарь для ключевых активностей.",
        ("OVERLOAD", "RESCHEDULE"):
            f"{full_name}, перенос задачи на следующий спринт снизит текущую перегрузку.",
        ("WORKDAY_EXCEPTION_CONFLICT", "KEEP"):
            f"{full_name}, событие подтверждено HR — оставляем в календаре без изменений.",
        ("WORKDAY_EXCEPTION_CONFLICT", "CANCEL"):
            f"{full_name}, отмена события снимет конфликт и освободит время для текущих задач.",
    }
    fallback = FALLBACK_MAP.get(key,
        f"{full_name}, действие {action} разрешит конфликт (тип: {conflict_type})."
    )

    # LLM-генерация пояснения
    TYPE_LABELS = {
        "OUTSIDE_WORK_HOURS": "событие вне рабочих часов",
        "OVERLAPPING_EVENTS": "наложение событий в календаре",
        "OVERLOAD": "перегрузка по задачам",
        "WORKDAY_EXCEPTION_CONFLICT": "конфликт с рабочим исключением",
    }
    ACTION_LABELS = {
        "RESCHEDULE": "перенос",
        "SPLIT": "разделение",
        "DELEGATE": "делегирование",
        "KEEP": "оставить",
        "CANCEL": "отмена",
    }
    type_label = TYPE_LABELS.get(conflict_type, conflict_type)
    action_label = ACTION_LABELS.get(action, action)

    system_prompt = """Ты — AI-аналитик конфликтов рабочего календаря. Сформулируй одно персонализированное пояснение на русском языке.

ПРАВИЛА:
- Обращайся к сотруднику по имени.
- Укажи конкретное действие и причину из данных.
- Упомяни рабочие часы и новое время, если действие — перенос.
- Тон: профессиональный, конкретный, без воды.
- ЗАПРЕЩЕНО: выдумывать факты, которых нет в данных.
- ЗАПРЕЩЕНО: общие фразы вроде «следите за балансом» или «обратите внимание».
- Формат: ТОЛЬКО JSON {"explanation": "текст пояснения"}"""

    user_prompt = f"""<context>
Сотрудник: {full_name}
Специализация: {specialization}
Тип занятости: {employment}
Рабочие часы: {work_start}–{work_end}
</context>

<conflict>
Тип конфликта: {type_label}
Описание: {conflict_desc}
Критичность: {conflict_severity}/5
</conflict>

<action>
Действие: {action_label}
Новое время: {new_time}
</action>

Сформулируй пояснение для сотрудника. Верни ТОЛЬКО JSON."""

    try:
        response = ollama_client.chat.completions.create(
            model="qwen2.5:14b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=150,
            timeout=10.0
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        llm_text = data.get("explanation", "").strip()

        if llm_text and len(llm_text) > 20:
            print(f"[conflict LLM] OK: {llm_text[:80]}...")
            return llm_text

        print(f"[conflict LLM] Пустой/короткий ответ, fallback")
        return fallback

    except Exception as e:
        print(f"[conflict LLM] Ошибка: {e}, fallback")
        return fallback