from typing import Dict

# Константы групп
GROUPS = {
    1: "Актуальный график",
    2: "Устаревший график",
    3: "Встречи вне рабочего времени",
    4: "Высокая нагрузка",
    5: "Временные исключения",
    6: "Конфликт HR и календаря",
    7: "Требуется подтверждение данных",
    8: "Требуется пересмотр графика",
    9: "Команда с низкой доступностью"
}

# Определяет группу сотрудника (1-9)
def classify_employee(payload: Dict, risk_data: Dict) -> Dict:

    metrics = risk_data["metrics"]
    risk_score = risk_data["risk_score"]

    profile = payload.get("profile", {})
    hr_data = payload.get("hr_data", {})
    meetings = payload.get("meetings", [])

    # Логика классификаци:

    # 6. Конфликт HR (самый критичный: отпуск/больничный vs встречи)
    if metrics["H_i_hr_conflict"] > 0.4:
        return {"group_id": 6, "group_name": GROUPS[6]}

    # 4. Высокая нагрузка (L_i > 1.0 значит переработка > 100%)
    if metrics["L_i_workload"] > 0.9:
        return {"group_id": 4, "group_name": GROUPS[4]}

    # 3. Встречи вне рабочего времени
    if metrics["C_i_outside_hours"] > 0.2:
        return {"group_id": 3, "group_name": GROUPS[3]}

    # 5. Исключения (если в профиле или HR есть флаг отпуска/больничного)
    if hr_data.get("on_vacation") or profile.get("employment") == "leave":
        return {"group_id": 5, "group_name": GROUPS[5]}

    # 8. Пересмотр графика (Очень высокий общий риск)
    if risk_score > 0.7:
        return {"group_id": 8, "group_name": GROUPS[8]}

    # 2. Устаревший график (Низкая актуальность)
    if metrics["A_i_freshness"] < 0.5:
        return {"group_id": 2, "group_name": GROUPS[2]}

    # 7. Требуется подтверждение (Средняя актуальность + средний риск)
    if metrics["A_i_freshness"] < 0.8 and risk_score > 0.3:
        return {"group_id": 7, "group_name": GROUPS[7]}

    # 1. Актуальный график (Всё хорошо)
    return {"group_id": 1, "group_name": GROUPS[1]}