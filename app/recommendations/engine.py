import os
from typing import List, Dict


def generate_recommendations(
        classification: Dict,
        metrics: Dict,
        profile: Dict = None,
        hr_data: Dict = None,
        meetings: List[Dict] = None,
        conflict: Dict = None
) -> List[str]:
    use_llm = os.getenv("USE_LLM_RECOMMENDATIONS", "false").lower() == "true"

    print(f"DEBUG: use_llm={use_llm}, profile={profile is not None}")

    if use_llm and profile:
        # Ленивый импорт — избегаем circular import на старте
        from app.llm.client import generate_llm_recommendations

        print("DEBUG: Вызываем LLM...")
        llm_recs = generate_llm_recommendations(
            profile=profile,
            metrics=metrics,
            hr_data=hr_data,
            meetings=meetings,
            conflict=conflict
        )
        if llm_recs:
            print(f"DEBUG: LLM вернула: {llm_recs}")
            return llm_recs
        else:
            print("DEBUG: LLM вернула пустой список")

    print("DEBUG: Используем fallback (правила)")

    return _fallback_recommendations(classification, metrics)


def _fallback_recommendations(classification: Dict, metrics: Dict) -> List[str]:
    group_id = classification.get("groupId")
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

    # Дополнительные сигналы (без вредных советов про «увеличьте нагрузку»)
    if metrics.get("C_i_outside_hours", 0) > 0.5:
        recs.append("Более 50% встреч проходят вне рабочего графика. Это критично для баланса.")
    if metrics.get("L_i_workload", 0) > 0.9:
        recs.append("Ваша загрузка задач слишком высока.")
    if metrics.get("A_i_freshness", 1.0) < 0.5:
        recs.append("Данные профиля устарели более 15 дней назад.")

    return recs if recs else ["Ваш график оптимален. Продолжайте в том же духе."]