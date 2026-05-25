from typing import Dict, List
from app.metrics import (
    calculate_freshness_score,
    calculate_workload_metrics,
    calculate_timezone_mismatch,
    calculate_hr_conflict_score
)

# Веса по умолчанию (сумма = 1.0)
# w1: Актуальность (наоборот), w2: Встречи вне часов, w3: Загрузка, w4: Часовой пояс, w5: HR конфликты
DEFAULT_WEIGHTS = {
    "w1": 0.25,  # Риск от старых данных
    "w2": 0.25,  # Риск от встреч ночью/в выходные
    "w3": 0.20,  # Риск от перегрузки
    "w4": 0.10,  # Риск от смены пояса
    "w5": 0.20  # Риск от рассинхрона с HR
}

def calculate_risk_score(
        payload: Dict,
        weights: Dict = None
) -> Dict:

    weights = weights or DEFAULT_WEIGHTS

    # 1. Извлекаем данные из payload
    profile = payload.get("profile", {})
    meetings = payload.get("meetings", [])
    tasks = payload.get("tasks", [])
    conflicts = payload.get("conflicts", [])
    hr_data = payload.get("hr_data", {})

    # 2. Считаем метрики (используем код из Шага 2)

    # A_i: Актуальность (Freshness)
    a_i = calculate_freshness_score(profile.get("last_updated"))

    # L_i: Загрузка и C_i: Встречи вне часов
    employment = str(profile.get("employment", profile.get("employmentType", "FULL_TIME"))).upper().replace("-", "_")
    if employment in ("PART_TIME", "PART_TIME"):
        weekly_cap = 20.0
    elif employment == "CONTRACT":
        weekly_cap = 40.0
    else:
        weekly_cap = 40.0

    workload_metrics = calculate_workload_metrics(
        tasks=tasks,
        meetings=meetings,
        profile=profile,
        weekly_capacity=weekly_cap
    )
    l_i = workload_metrics["L_i"]
    c_i = workload_metrics["C_i"]

    # Z_i: Часовой пояс
    z_i = calculate_timezone_mismatch(
        profile_tz=profile.get("timezone", "UTC"),
        meetings=meetings,
        profile=profile
    )

    # H_i: HR конфликты
    h_i = calculate_hr_conflict_score(
        hr_data=hr_data,
        meetings=meetings,
        conflicts=conflicts
    )

    # 3. Применяем формулу Ri
    # Ri = w1(1-Ai) + w2Ci + w3Li + w4Zi + w5Hi
    risk_score = (
            weights["w1"] * (1 - a_i) +
            weights["w2"] * c_i +
            weights["w3"] * l_i +
            weights["w4"] * z_i +
            weights["w5"] * h_i
    )

    # Ограничиваем диапазон 0.0 - 1.0
    risk_score = min(max(risk_score, 0.0), 1.0)

    return {
        "risk_score": round(risk_score, 3),
        "metrics": {
            "A_i_freshness": round(a_i, 3),
            "L_i_workload": round(l_i, 3),
            "C_i_outside_hours": round(c_i, 3),
            "Z_i_timezone": round(z_i, 3),
            "H_i_hr_conflict": round(h_i, 3),
            "total_task_hours": workload_metrics.get("total_task_hours", 0),
            "total_meeting_hours": workload_metrics.get("total_meeting_hours", 0)

        }
    }