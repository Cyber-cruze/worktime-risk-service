from typing import List, Dict
from datetime import datetime, timezone
import zoneinfo


'''Возвращает:
- L_i: уровень загрузки (задачи + встречи / capacity)
- C_i: доля встреч вне рабочего времени'''


def _to_local_hour(dt_str: str, profile_tz: str) -> int:
    """Конвертирует ISO-строку (UTC / с таймзоной) в локальный час сотрудника."""
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


def _parse_meeting_hours(m: Dict) -> float:
    """Считает длительность встречи в часах (корректно для UTC и наивных строк)."""
    start = datetime.fromisoformat(m["start"])
    end = datetime.fromisoformat(m["end"])
    # Если оба наивные или оба aware — просто разница
    return (end - start).total_seconds() / 3600


def calculate_workload_metrics(
        tasks: List[Dict],
        meetings: List[Dict],
        profile: Dict,
        weekly_capacity: float = 40.0
) -> Dict[str, float]:

    profile_tz = profile.get("timezone", "UTC")

    # 1. L_i: Загрузка
    task_hours = sum(t.get("hours", 0) for t in tasks)
    meeting_hours = sum(_parse_meeting_hours(m) for m in meetings)

    raw_load = (task_hours + meeting_hours) / weekly_capacity if weekly_capacity > 0 else 0
    L_i = min(raw_load, 1.0)

    # 2. C_i: Встречи вне графика (в ЛОКАЛЬНОМ времени сотрудника)
    work_start = int(profile.get("work_hours", {}).get("start", "09:00").split(":")[0])
    work_end = int(profile.get("work_hours", {}).get("end", "18:00").split(":")[0])

    outside_count = 0
    for m in meetings:
        local_hour = _to_local_hour(m["start"], profile_tz)
        if local_hour < work_start or local_hour >= work_end:
            outside_count += 1

    C_i = (outside_count / len(meetings)) if meetings else 0.0

    return {"L_i": round(L_i, 3), "C_i": round(min(C_i, 1.0), 3)}
