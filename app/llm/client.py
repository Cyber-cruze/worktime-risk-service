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

MODEL = "qwen2.5:7b"



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
        print(f"[parse] Ошибка: {e}")
        return []


def _clean_recommendations(recs: List[str]) -> List[str]:
    """Убирает технические метрики, обрезает до 2 рекомендаций по 2 предложения."""
    cleaned = []
    for r in recs[:2]:
        r = re.sub(r'\b[A-Z]_i_[a-z_]+\b\s*=?\s*\d*\.?\d*', '', r)
        r = re.sub(r'\s+', ' ', r).strip()
        sentences = re.split(r'(?<=[.!?])\s+', r)
        r = ' '.join(sentences[:2])
        if r and not r.endswith(('.', '!', '?')):
            r += '.'
        if r:
            cleaned.append(r)
    return cleaned if cleaned else ["Показатели в норме. График стабилен."]


def _employment_label(emp_type: str) -> str:
    t = str(emp_type).upper().replace('-', '_').replace(' ', '_')
    if t == 'PART_TIME':
        return 'неполный рабочий день'
    if t == 'FULL_TIME':
        return 'полный рабочий день'
    if t == 'CONTRACT':
        return 'контракт'
    return 'полный рабочий день'


def _meetings_local_summary(meetings: List[Dict], profile_tz: str) -> str:
    if not meetings:
        return "Встреч нет."
    try:
        tz = zoneinfo.ZoneInfo(profile_tz)
    except Exception:
        tz = timezone.utc
    lines = []
    for i, m in enumerate(meetings, 1):
        start_str = m.get("start_time") or m.get("start", "")
        end_str = m.get("end_time") or m.get("end", "")
        try:
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            if start_dt.tzinfo is not None:
                local_start = start_dt.astimezone(tz).strftime("%H:%M")
                local_end = end_dt.astimezone(tz).strftime("%H:%M")
                lines.append(f"  {i}. {local_start}–{local_end}")
            else:
                lines.append(f"  {i}. {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}")
        except Exception:
            lines.append(f"  {i}. {start_str} – {end_str}")
    return "\n".join(lines)


def _count_outside_meetings(meetings: List[Dict], work_start: str, work_end: str, profile_tz: str):
    """Возвращает (кол-во вне-графиковых встреч, список их часов)."""
    if not meetings:
        return 0, []
    try:
        tz = zoneinfo.ZoneInfo(profile_tz)
    except Exception:
        tz = timezone.utc
    ws = int(work_start.split(":")[0])
    we = int(work_end.split(":")[0])
    count = 0
    hours_list = []
    for m in meetings:
        start_str = m.get("start_time") or m.get("start", "")
        try:
            start_dt = datetime.fromisoformat(start_str)
            local_h = start_dt.astimezone(tz).hour if start_dt.tzinfo is not None else start_dt.hour
            if local_h < ws or local_h >= we:
                count += 1
                hours_list.append(f"{local_h:02d}:00")
        except Exception:
            pass
    return count, hours_list


def generate_llm_recommendations(
        profile: Dict,
        metrics: Dict,
        hr_data: Dict = None,
        meetings: List[Dict] = None,
        conflict: Dict = None
) -> List[str]:
    safe_profile = _make_json_safe(profile)
    safe_metrics = _make_json_safe(metrics)

    # ── Guard: отпуск — ответ однозначный, LLM не нужна ──
    vac_flag = (hr_data or {}).get('on_vacation')
    is_vacation = vac_flag in [True, 'true', 1, '1']
    if is_vacation:
        n = len(meetings) if meetings else 0
        if n:
            return [f"Сотрудник в отпуске — отмените или перенесите {n} встреч в календаре."]
        return ["Сотрудник в отпуске — отмените или перенесите рабочие события."]

    #  Сбор данных
    name = safe_profile.get("name", "Коллега")
    surname = safe_profile.get("surname", "")
    full_name = f"{name} {surname}".strip() or "Коллега"
    work_start = safe_profile.get("work_hours", {}).get("start", "09:00")
    work_end = safe_profile.get("work_hours", {}).get("end", "18:00")
    profile_tz = safe_profile.get("timezone", "UTC")
    emp_raw = safe_profile.get('employmentType') or safe_profile.get('employment', 'FULL_TIME')
    emp_label = _employment_label(emp_raw)
    on_vacation = (hr_data or {}).get('on_vacation', False)
    official_schedule = (hr_data or {}).get('official_schedule', 'не указан')

    workload = safe_metrics.get('L_i_workload', 0)
    outside_ratio = safe_metrics.get('C_i_outside_hours', 0)
    hr_conflict = safe_metrics.get('H_i_hr_conflict', 0)
    freshness = safe_metrics.get('A_i_freshness', 1)

    outside_count, outside_hours_list = _count_outside_meetings(
        meetings or [], work_start, work_end, profile_tz
    )
    total_meetings = len(meetings) if meetings else 0
    meetings_summary = _meetings_local_summary(meetings or [], profile_tz)

    #  Факты для промпта
    facts = []
    if outside_count > 0:
        hours_str = ", ".join(outside_hours_list[:3])
        facts.append(f"{outside_count} из {total_meetings} встреч вне рабочих часов ({hours_str})")
    if workload > 0.5:
        facts.append(f"загрузка {int(workload * 100)}% (выше нормы)")
    elif workload < 0.2:
        facts.append(f"загрузка {int(workload * 100)}% (ниже нормы)")
    if hr_conflict > 0.4:
        facts.append("фактический график расходится с данными HR")
    if freshness < 0.5:
        facts.append("данные профиля устарели")
    if not facts:
        facts.append("показатели в норме")

    # ── Промпт ──
    system_prompt = """Ты — аналитик рабочих графиков. Дай 1-2 рекомендации.

Правила:
- 1-2 рекомендации, каждая 1 предложение.
- Формат: [факт] → [конкретное действие].
- Пиши повелительным наклонением: «Перенесите», «Сократите», «Отмените», «Обсудите».
- НЕ пиши страдательным залогом: «перенесено», «отменено», «рекомендуется».
- Каждое предложение с большой буквы.
- Обращайся по имени на «вы».
- Пиши человеческим языком: «неполный рабочий день», «вне рабочих часов», «загрузка».
- НЕ пиши: PART_TIME, FULL_TIME, C_i, L_i, метрики, индексы.
- НЕ пиши: «обратите внимание», «следите за балансом», «обращайтесь».
- НЕ пиши: «Здравствуйте» — сразу по имени.
- НЕ пиши: «я рекомендую».
- НЕ повторяй одну мысль дважды.

Формат: ТОЛЬКО JSON {"recommendations": ["Совет 1"]}"""

    user_prompt = f"""Сотрудник: {full_name}
График: {work_start}–{work_end}
Занятость: {emp_label}
В отпуске: {on_vacation}
Официальный график HR: {official_schedule}
Факты: {'; '.join(facts)}
Встречи:
{meetings_summary}

JSON:"""

    try:
        response = ollama_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.05,
            max_tokens=100,
            timeout=10.0
        )
        raw_recs = _parse_json_response(response.choices[0].message.content)
        return _clean_recommendations(raw_recs) if raw_recs else ["Показатели в норме. График стабилен."]

    except Exception as e:
        print(f"[analyze LLM] Ошибка: {e}")
        return ["Показатели в норме. График стабилен."]




def generate_conflict_explanation(
        conflict: Dict,
        profile: Dict,
        action: str,
        new_time: str,
        all_actions: str = "",
        context_hints: str = ""
) -> str:
    safe_conflict = _make_json_safe(conflict)
    safe_profile = _make_json_safe(profile)

    first_name = safe_profile.get('name', 'Коллега')
    full_name = f"{first_name} {safe_profile.get('surname', '')}".strip() or "Коллега"
    conflict_type = safe_conflict.get('type', 'UNKNOWN')
    conflict_desc = safe_conflict.get('description', 'не указано')
    conflict_severity = safe_conflict.get('severity', 3)
    work_start = safe_profile.get('workStart', '09:00:00')[:5]
    work_end = safe_profile.get('workEnd', '18:00:00')[:5]
    employment = safe_profile.get('employmentType', 'FULL_TIME')
    emp_label = _employment_label(employment)
    is_part_time = str(employment).upper().replace('-', '_') == "PART_TIME"

    # Fallback-шаблоны (только если LLM упала)
    fallback_map = {
        ("OUTSIDE_WORK_HOURS", "RESCHEDULE"):
            f"{first_name}, перенесите встречу с нерабочего времени ({work_start}–{work_end}) на {new_time}.",
        ("OUTSIDE_WORK_HOURS", "CANCEL"):
            f"{first_name}, отмените встречу вне рабочих часов.",
        ("OUTSIDE_WORK_HOURS", "KEEP"):
            f"{first_name}, проверьте необходимость встречи вне рабочих часов.",
        ("OVERLAPPING_EVENTS", "RESCHEDULE"):
            f"{first_name}, перенесите одну из пересекающихся встреч на {new_time}.",
        ("OVERLAPPING_EVENTS", "SPLIT"):
            f"{first_name}, разделите встречу на две части для устранения наложения.",
        ("OVERLAPPING_EVENTS", "CANCEL"):
            f"{first_name}, отмените одну из пересекающихся встреч.",
        ("OVERLAPPING_EVENTS", "KEEP"):
            f"{first_name}, проверьте календарь — есть наложение событий.",
        ("OVERLOAD", "DELEGATE"):
            f"{first_name}, делегируйте задачу для снижения перегрузки.",
        ("OVERLOAD", "RESCHEDULE"):
            f"{first_name}, перенесите задачу на {work_start} следующего рабочего дня.",
        ("OVERLOAD", "CANCEL"):
            f"{first_name}, отмените задачу из-за перегрузки.",
        ("WORKDAY_EXCEPTION_CONFLICT", "KEEP"):
            f"{first_name}, проверьте статус события в HR-системе.",
        ("WORKDAY_EXCEPTION_CONFLICT", "CANCEL"):
            f"{first_name}, отмените событие — оно конфликтует с отпуском.",
        ("WORKDAY_EXCEPTION_CONFLICT", "RESCHEDULE"):
            f"{first_name}, перенесите событие на {new_time} — после окончания отпуска.",
    }
    fallback = fallback_map.get(
        (conflict_type, action),
        f"{first_name}, разрешите конфликт: {action.lower()}."
    )

    #  Типы и действия на русском
    TYPE_LABELS = {
        "OUTSIDE_WORK_HOURS": "событие вне рабочих часов",
        "OVERLAPPING_EVENTS": "наложение событий",
        "OVERLOAD": "перегрузка по задачам",
        "WORKDAY_EXCEPTION_CONFLICT": "конфликт с отпуском или больничным",
    }
    ACTION_LABELS = {
        "RESCHEDULE": "перенос на " + new_time,
        "SPLIT": "разделение на части",
        "DELEGATE": "делегирование",
        "KEEP": "оставить без изменений",
        "CANCEL": "отмена",
    }
    type_label = TYPE_LABELS.get(conflict_type, conflict_type)
    action_label = ACTION_LABELS.get(action, action)

    #  Дополнительные правила по типу конфликта
    type_rules = ""
    if conflict_type == "WORKDAY_EXCEPTION_CONFLICT" and conflict_severity >= 4:
        type_rules = "Отпуск + высокая критичность = событие НЕЛЬЗЯ оставлять. Объясни отмену или перенос."
    elif conflict_type == "OUTSIDE_WORK_HOURS":
        type_rules = f"Укажи, что событие вне рабочих часов ({work_start}–{work_end})."
    elif conflict_type == "OVERLAPPING_EVENTS" and is_part_time:
        type_rules = f"У сотрудника неполный рабочий день ({work_start}–{work_end}), перенос в рамках этого окна."
    elif conflict_type == "OVERLOAD" and is_part_time:
        type_rules = f"У сотрудника неполный рабочий день, лимит 4 часа в день."

    # ── Промпт ──
    system_prompt = f"""Аналитик конфликтов календаря. Дай 1-2 предложения пояснения.

Правила:
- 1-2 предложения. ВСЕГДА начинай с имени: «{first_name}, ...»
- Суть в 1 фразе: что не так и что сделать.
- Пиши повелительным наклонением: «Перенесите», «Отмените», «Проверьте», «Делегируйте».
- НЕ пиши страдательным залогом: «перенесено», «отменено», «рекомендуется».
- Каждое предложение с большой буквы.
- Пиши человеческим языком: «вне рабочих часов», «перегрузка», «конфликт с отпуском».
- НЕ пиши стрелку «→» — это формат-подсказка, не для вывода.
- НЕ пиши: PART_TIME, FULL_TIME, OUTSIDE_WORK_HOURS, OVERLOAD и т.д.
- НЕ пиши воду: «чтобы избежать», «для снижения», «требует решения», «обратите внимание», «обращайтесь».
- НЕ пиши: «Здравствуйте», «я рекомендую».
- Обращайся на «вы», НЕ «у неё/него» — только «у вас».
{type_rules}

Формат: ТОЛЬКО JSON {{"explanation": "текст"}}"""

    hints_line = ""
    if context_hints and context_hints != "нет":
        hints_line = f"\nПодсказки: {context_hints}"

    user_prompt = f"""Сотрудник: {full_name}, занятость: {emp_label}, график: {work_start}–{work_end}
Конфликт: {type_label}, описание: {conflict_desc}, критичность: {conflict_severity}/5
Действие: {action_label}{hints_line}

JSON:"""

    try:
        response = ollama_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.05,
            max_tokens=80,
            timeout=10.0
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        llm_text = data.get("explanation", "").strip()

        # Обрезаем до 2 предложений
        sentences = re.split(r'(?<=[.!?])\s+', llm_text)
        llm_text = ' '.join(sentences[:2])
        if llm_text and not llm_text.endswith(('.', '!', '?')):
            llm_text += '.'

        if llm_text and len(llm_text) > 15:
            print(f"[conflict LLM] OK: {llm_text[:80]}...")
            return llm_text

        print(f"[conflict LLM] Короткий ответ, fallback")
        return fallback

    except Exception as e:
        print(f"[conflict LLM] Ошибка: {e}, fallback")
        return fallback