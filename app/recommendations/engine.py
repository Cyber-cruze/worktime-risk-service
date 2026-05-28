import os
from typing import List, Dict
from app.roles import normalize_role
from app.metrics.date_filter import filter_current_week



# PM-рекомендации (fallback)

_PM_RECOMMENDATIONS = {
    2: [
        "Данные сотрудника устарели. Запросите обновление профиля через HR-систему.",
        "Свяжитесь с сотрудником для подтверждения актуального графика и часового пояса.",
    ],
    3: [
        "У сотрудника есть встречи в нерабочее время. Пересмотрите расписание команды и перенесите встречи на рабочие часы.",
        "Установите правило Team Overlap для командных встреч — это снизит ночные встречи для сотрудников в других поясах.",
    ],
    4: [
        "Загрузка сотрудника превышает 90%. Перераспределите задачи между членами команды.",
        "Рассмотрите возможность делегирования или переноса задач на следующий спринт.",
    ],
    5: [
        "Сотрудник в статусе отпуска/больничного, но данные в системе не обновлены. Проверьте корректность статуса.",
    ],
    6: [
        "Обнаружено расхождение между официальным графиком HR и календарём сотрудника. Инициируйте синхронизацию статусов.",
        "Отмените или перенесите встречи, конфликтующие с отпуском/больничным сотрудника.",
    ],
    8: [
        "График сотрудника требует пересмотра. Назначьте встречу 1-на-1 для оптимизации рабочей нагрузки.",
        "Рассмотрите перераспределение проектов — текущий график ведёт к высокому риску выгорания.",
    ],
}

_PM_METRIC_SIGNALS = {
    "C_i_outside_hours": (
        0.5,
        "Более 50% встреч сотрудника проходят вне рабочего графика. Пересмотрите расписание команды."
    ),
    "L_i_workload": (
        0.9,
        "Загрузка сотрудника критически высока. Необходима балансировка нагрузки в команде."
    ),
    "A_i_freshness": (
        0.5,
        "Данные профиля сотрудника устарели. Запросите обновление через HR-систему."
    ),
}


def generate_recommendations(
        classification: Dict,
        metrics: Dict,
        profile: Dict = None,
        hr_data: Dict = None,
        meetings: List[Dict] = None,
        conflict: Dict = None,
        role: str = "EMPLOYEE",
) -> Dict[str, List[str]]:
    """Генерирует рекомендации для сотрудника и/или PM.

    Args:
        role: "EMPLOYEE" — только для сотрудника,
              "PROJECT_MANAGER" — только для PM,
              "BOTH" — для обоих.
              Также принимаются короткие формы: employee, pm, both.

    Returns:
        {"employee": [...], "pm": [...]}
    """
    role = normalize_role(role)

    # Фильтруем встречи — только текущая неделя (LLM не должна видеть старые)
    if meetings:
        meetings = filter_current_week(meetings, date_key="start")

    use_llm = os.getenv("USE_LLM_RECOMMENDATIONS", "false").lower() == "true"

    print(f"DEBUG: use_llm={use_llm}, profile={profile is not None}, role={role}")

    if use_llm and profile:
        from app.llm.client import generate_llm_recommendations

        print("DEBUG: Вызываем LLM...")
        llm_recs = generate_llm_recommendations(
            profile=profile,
            metrics=metrics,
            hr_data=hr_data,
            meetings=meetings,
            conflict=conflict,
            role=role,
        )
        if llm_recs:
            print(f"DEBUG: LLM вернула: {llm_recs}")
            # LLM может вернуть {"employee": [...], "pm": [...]} или просто список
            if isinstance(llm_recs, dict):
                return llm_recs
            # Совместимость: если вернулся список — это для запрошенной роли
            result = {"employee": [], "pm": []}
            if role in ("employee", "both"):
                result["employee"] = llm_recs
            if role in ("pm", "both"):
                result["pm"] = llm_recs
            return result
        else:
            print("DEBUG: LLM вернула пустой список")

    print("DEBUG: Используем fallback (правила)")

    return _fallback_recommendations(classification, metrics, role)


def _fallback_recommendations(
        classification: Dict,
        metrics: Dict,
        role: str = "EMPLOYEE",
) -> Dict[str, List[str]]:
    """Fallback-рекомендации по правилам.

    Возвращает словарь с двумя списками: employee и pm.
    Заполняются только те роли, которые запрошены через параметр role.
    """
    role = normalize_role(role)
    group_id = classification.get("group_id") or classification.get("groupId")

    result = {"employee": [], "pm": []}

    # Рекомендации для сотрудника
    if role in ("employee", "both"):
        recs = []

        if group_id == 2:
            recs.append("Обновите данные профиля: укажите актуальные рабочие часы.")
            recs.append("Подтвердите ваш часовой пояс в настройках.")
        if group_id == 3:
            recs.append("У вас есть встречи в нерабочее время. Попробуйте перенести их на рабочий график.")
            recs.append("Предложите коллегам найти общее время для командных встреч (Team Overlap).")
        if group_id == 4:
            recs.append("Загрузка превышает 90%. Не планируйте новых задач на эту неделю.")
            recs.append("Рассмотрите возможность делегирования части задач.")
        if group_id == 5:
            recs.append("Обнаружен статус отпуска или больничного. Проверьте корректность статуса в системе.")
        if group_id == 6:
            recs.append("Обнаружено расхождение с официальным графиком (отпуск/больничный).")
            recs.append("Свяжитесь с HR для синхронизации статусов и отмены конфликтующих встреч.")
        if group_id == 8:
            recs.append("Текущий график неэффективен. Рекомендуется встреча с тимлидом для оптимизации.")

        # Дополнительные сигналы
        if metrics.get("C_i_outside_hours", 0) > 0.5:
            recs.append("Более 50% встреч проходят вне рабочего графика. Это критично для баланса.")
        if metrics.get("L_i_workload", 0) > 0.9:
            recs.append("Ваша загрузка задач слишком высока.")
        if metrics.get("A_i_freshness", 1.0) < 0.5:
            recs.append("Данные профиля устарели более 15 дней назад.")

        result["employee"] = recs if recs else ["Ваш график оптимален. Продолжайте в том же духе."]

    # Рекомендации для PM
    if role in ("pm", "both"):
        pm_recs = list(_PM_RECOMMENDATIONS.get(group_id, []))

        # Дополнительные сигналы для PM
        for metric_key, (threshold, text) in _PM_METRIC_SIGNALS.items():
            # A_i_freshness — тревога при НИЗКОМ значении (< порога)
            if metric_key == "A_i_freshness":
                if metrics.get(metric_key, 1.0) < threshold:
                    pm_recs.append(text)
            else:
                if metrics.get(metric_key, 0) > threshold:
                    pm_recs.append(text)

        if group_id == 1 and not pm_recs:
            pm_recs.append("График сотрудника в норме. Продолжайте мониторинг.")

        result["pm"] = pm_recs if pm_recs else ["График сотрудника в норме. Дополнительных действий не требуется."]

    return result
