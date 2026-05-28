from typing import List, Dict
from datetime import datetime
import zoneinfo

from app.metrics.date_filter import filter_current_week


'''Рассчитывает Z_i: несоответствие часового пояса и активности
Возвращает 0.0 (полное совпадение) → 1.0 (полный рассинхрон)'''


def calculate_timezone_mismatch(
        profile_tz: str,
        meetings: List[Dict],
        profile: Dict
) -> float:

    # Фильтруем встречи — только текущая неделя
    current_week_meetings = filter_current_week(meetings, date_key="start")

    if not current_week_meetings:
        return 0.0

    try:
        tz = zoneinfo.ZoneInfo(profile_tz)
    except Exception:
        return 0.5  # Fallback при неверном поясе

    work_start = int(profile.get("work_hours", {}).get("start", "09:00").split(":")[0])
    work_end = int(profile.get("work_hours", {}).get("end", "18:00").split(":")[0])

    mismatch_count = 0
    for m in current_week_meetings:
        dt = datetime.fromisoformat(m["start"]).replace(tzinfo=tz)

        # Если встреча в поясе сотрудника выпадает на ночь/раннее утро (00:00-07:00)
        if dt.hour < 7 or dt.hour > 22:
            mismatch_count += 1

    Z_i = mismatch_count / len(current_week_meetings)
    return round(min(Z_i, 1.0), 3)