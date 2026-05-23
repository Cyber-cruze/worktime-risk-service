from typing import List, Dict


'''Рассчитывает H_i: расхождение HR-данных и календаря
Учитывает: отпуск vs встречи, официальный график vs факт'''


def calculate_hr_conflict_score(
        hr_data: Dict,
        meetings: List[Dict],
        conflicts: List[Dict]
) -> float:

    penalty = 0.0
    total_signals = len(meetings) + len(conflicts)

    # 1. Конфликт "Отпуск vs Встречи"
    if hr_data.get("on_vacation", False) and meetings:
        penalty += 0.8  # Высокий штраф за встречи в отпуске

    # 2. Конфликт "Официальный график vs Факт"
    official_start = int(hr_data.get("official_schedule", "09:00").split(":")[0])
    official_end = int(hr_data.get("official_schedule", "18:00").split(":")[0])

    for m in meetings:
        start_h = int(m["start"].split("T")[1].split(":")[0])
        if start_h < official_start or start_h >= official_end:
            penalty += 0.1

    # 3. Явные конфликты из Conflict Service
    for c in conflicts:
        severity = c.get("severity", "low")
        if severity == "critical":
            penalty += 0.3
        elif severity == "high":
            penalty += 0.2
        elif severity == "medium":
            penalty += 0.1

    # Нормализация до 0-1
    H_i = min(penalty / max(total_signals, 1), 1.0)
    return round(H_i, 3)