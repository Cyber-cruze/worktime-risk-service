from typing import List, Dict
from datetime import datetime, timezone
import zoneinfo


'''Рассчитывает H_i: расхождение HR-данных и календаря
Учитывает: отпуск vs встречи, официальный график vs факт'''


def _get_start(m: Dict) -> str:
    return m.get("start_time") or m.get("start", "")


def _to_local_hour(dt_str: str, tz_name: str = "UTC") -> int:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        return dt.hour
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return dt.astimezone(tz).hour


def calculate_hr_conflict_score(
        hr_data: Dict,
        meetings: List[Dict],
        conflicts: List[Dict],
        profile_tz: str = "UTC"
) -> float:

    penalty = 0.0

    # 1. Конфликт "Отпуск vs Встречи" — КРИТИЧЕСКИЙ сигнал
    if hr_data.get("on_vacation", False) and meetings:
        penalty += 0.6

    # 2. Конфликт "Официальный график vs Факт"
    official_start = int(hr_data.get("official_schedule", "09:00").split(":")[0])
    official_end = int(hr_data.get("official_schedule", "18:00").split(":")[0])

    outside_schedule_count = 0
    for m in meetings:
        start_str = _get_start(m)
        if not start_str:
            continue
        local_h = _to_local_hour(start_str, profile_tz)
        if local_h < official_start or local_h >= official_end:
            outside_schedule_count += 1

    if meetings:
        outside_ratio = outside_schedule_count / len(meetings)
        penalty += outside_ratio * 0.3

    # 3. Явные конфликты из Conflict Service
    for c in conflicts:
        severity = c.get("severity", "low")
        if severity == "critical":
            penalty += 0.3
        elif severity == "high":
            penalty += 0.2
        elif severity == "medium":
            penalty += 0.1

    H_i = min(penalty, 1.0)
    return round(H_i, 3)