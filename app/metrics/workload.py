from typing import List, Dict
from datetime import datetime


'''Возвращает:
- L_i: уровень загрузки (задачи + встречи /capacity)
- C_i: доля встреч вне рабочего времени'''


def calculate_workload_metrics(
        tasks: List[Dict],
        meetings: List[Dict],
        profile: Dict,
        weekly_capacity: float = 40.0
) -> Dict[str, float]:

    # 1. L_i: Загрузка
    task_hours = sum(t.get("hours", 0) for t in tasks)
    meeting_hours = sum(
        (datetime.fromisoformat(m["end"]) - datetime.fromisoformat(m["start"])).total_seconds() / 3600
        for m in meetings
    )

    raw_load = (task_hours + meeting_hours) / weekly_capacity if weekly_capacity > 0 else 0
    L_i = min(raw_load, 1.0)

    # 2. C_i: Встречи вне графика
    work_start = int(profile.get("work_hours", {}).get("start", "09:00").split(":")[0])
    work_end = int(profile.get("work_hours", {}).get("end", "18:00").split(":")[0])

    outside_count = 0
    for m in meetings:
        start_hour = datetime.fromisoformat(m["start"]).hour
        if start_hour < work_start or start_hour >= work_end:
            outside_count += 1

    C_i = (outside_count / len(meetings)) if meetings else 0.0

    return {"L_i": round(L_i, 3), "C_i": round(min(C_i, 1.0), 3)}