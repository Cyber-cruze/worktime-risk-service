from typing import List, Dict
from datetime import datetime, timezone
import zoneinfo


'''Возвращает:
- L_i: уровень загрузки (задачи + встречи / capacity)
- C_i: доля встреч вне рабочего времени'''


def _to_local_hour(dt_str: str, profile_tz: str) -> int:
    dt = datetime.fromisoformat(dt_str)
    # Если datetime наивный — считаем что уже в локальном времени
    if dt.tzinfo is None:
        return dt.hour
    # Конвертируем в часовой пояс сотрудника
    try:
        tz = zoneinfo.ZoneInfo(profile_tz)
    except Exception:
        tz = timezone.utc
    local_dt = dt.astimezone(tz)
    return local_dt.hour


# Берёт start_time или start из встречи/задачи
def _get_start(m: Dict) -> str:
    return m.get("start_time") or m.get("start", "")


# Берёт end_time или end из встречи/задачи
def _get_end(m: Dict) -> str:
    return m.get("end_time") or m.get("end", "")


def _parse_hours(m: Dict) -> float:
    start_str = _get_start(m)
    end_str = _get_end(m)
    if not start_str or not end_str:
        return m.get("hours", 0)
    start = datetime.fromisoformat(start_str)
    end = datetime.fromisoformat(end_str)
    return (end - start).total_seconds() / 3600


def calculate_workload_metrics(
        tasks: List[Dict],
        meetings: List[Dict],
        profile: Dict,
        weekly_capacity: float = 40.0
) -> Dict[str, float]:

    profile_tz = profile.get("timezone", "UTC")

    # 1. L_i: Загрузка
    task_hours = sum(_parse_hours(t) for t in tasks)
    meeting_hours = sum(_parse_hours(m) for m in meetings)

    raw_load = (task_hours + meeting_hours) / weekly_capacity if weekly_capacity > 0 else 0
    L_i = min(raw_load, 1.0)

    # 2. C_i: Встречи вне графика (в ЛОКАЛЬНОМ времени сотрудника)
    work_start = int(profile.get("work_hours", {}).get("start", "09:00").split(":")[0])
    work_end = int(profile.get("work_hours", {}).get("end", "18:00").split(":")[0])

    outside_count = 0
    for m in meetings:
        local_hour = _to_local_hour(_get_start(m), profile_tz)
        if local_hour < work_start or local_hour >= work_end:
            outside_count += 1

    C_i = (outside_count / len(meetings)) if meetings else 0.0

    return {
        "L_i": round(L_i, 3),
        "C_i": round(min(C_i, 1.0), 3),
        "total_task_hours": round(task_hours, 2),
        "total_meeting_hours": round(meeting_hours, 2)
    }