from datetime import datetime, timedelta
from typing import List, Dict


def _week_bounds(reference_date: datetime = None):
    # Возвращает (понедельник_00:00, воскресенье_23:59:59) для недели, содержащей reference_date
    ref = reference_date or datetime.now()
    monday = ref - timedelta(days=ref.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def filter_current_week(items: List[Dict], date_key: str = "start") -> List[Dict]:
    """Фильтрует список словарей, оставляя только записи текущей недели.

    Args:
        items: список словарей с полем даты
        date_key: ключ, по которому берём дату (по умолчанию "start")

    Returns:
        Отфильтрованный список — только записи, попадающие в текущую неделю.
        Если поле даты отсутствует или не парсится — запись включается
        (безопасное поведение: лучше учесть, чем потерять).
    """
    if not items:
        return []

    week_start, week_end = _week_bounds()
    result = []

    for item in items:
        date_str = item.get(date_key)
        if not date_str:
            # Нет даты — включаем
            result.append(item)
            continue

        try:
            dt = datetime.fromisoformat(str(date_str))
            # Убираем timezone для сравнения
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            if week_start <= dt <= week_end:
                result.append(item)
        except (ValueError, TypeError):
            # Не парсится — включаем
            result.append(item)

    return result