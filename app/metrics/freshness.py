from datetime import datetime, date
from typing import Union

'''Рассчитывает актуальность данных (A_i)
Возвращает 1.0, если обновлено сегодня, 0.0, если старше decay_days'''

def calculate_freshness_score(last_updated: Union[str, date, datetime], decay_days: int = 30) -> float:

    if isinstance(last_updated, str):
        last_date = datetime.fromisoformat(last_updated).date()
    elif hasattr(last_updated, "date"):
        last_date = last_updated.date()
    else:
        last_date = last_updated

    days_diff = (date.today() - last_date).days
    if days_diff <= 0:
        return 1.0

    # Линейное затухание
    score = max(0.0, 1.0 - (days_diff / decay_days))
    return round(score, 3)