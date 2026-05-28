import os
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.chat.schemas import ChatRequest, ChatResponse, ChatMessage, ToolResult
from app.chat.tools import TOOL_REGISTRY
from app.roles import normalize_role


# 1. ОПРЕДЕЛЕНИЕ НАМЕРЕНИЯ
INTENT_KEYWORDS: Dict[str, list] = {
    "analyze": [
        "риск", "выгоран", "анализ", "перегружен", "перегруз",
        "насколько я", "какой риск", "оцени мой", "оценка риска",
        "риск выгорания", "насколько перегружен", "мой график",
        "проблемы с графиком", "свежесть данных", "актуальность",
        "встречи вне", "вне рабочих", "не рабочих часов",
        "рекомендац", "что делать с графиком", "насколько плох",
        "группа риска", "классификац",
    ],
    "conflicts": [
        "конфликт", "пересечени", "накладк", "наложени",
        "разреши конфликт", "разрешить конфликт", "решить конфликт",
        "что с конфликтом", "как разрешить", "что делать с конфликтом",
        "устранить", "помоги разрешить",
    ],
    "predict": [
        "предскажи", "прогноз", "вероятность конфликт",
        "предсказани", "будущ", "ожидается ли конфликт",
        "шанс конфликт", "какая вероятность", "будет ли конфликт",
        "предскажи конфликт", "прогноз конфликт",
    ],
    "score": [
        "оценка графика", "качество расписания", "оценка расписания",
        "рейтинг графика", "какая оценка", "буква", "град",
        "качество моего графика", "насколько хорош график",
        "балл за график", "оцени расписание",
        "оценка моего расписания", "оцени график", "оцени мой график",
        "какое качество расписания", "какой балл",
        "оцени качество", "качество моего расписания",
        "оцени моё расписание", "оцени мое расписание",
    ],
    "anomalies": [
        "аномали", "странност", "отклонени", "необычн",
        "аномальн", "что-то не так", "подозрительн",
        "нетипичн", "выбивает", "аномалии в графике",
    ],
    "navigation": [
        "как добавить", "где найти", "как найти", "как открыть",
        "где находится", "как зайти", "как перейти",
        "где посмотреть", "как посмотреть", "где увидеть",
        "как изменить", "где изменить", "как настроить",
        "как удалить", "где удалить", "как создать",
        "как обновить", "как обновить данные",
        "исключени", "настройк", "профиль", "календар",
        "расписание", "график работы", "команд",
        "отпуск", "больничн", "страниц",
        "раздел", "вкладк", "меню", "панель",
        "дашборд", "панель управлен",
    ],
}

# справочник разделов сайта для навигации
SITE_SECTIONS: Dict[str, Dict[str, str]] = {
    "исключение": {
        "employee": "Откройте раздел «Исключения» в боковом меню → нажмите «Добавить исключение». Выберите тип: отпуск, больничный, личное время или командировка, укажите даты и причину.",
        "team_lead": "Откройте раздел «Проблемы» в боковом меню — там отображаются конфликты сотрудников.",
        "hr": "Откройте раздел «Исключения» в боковом меню — список всех исключений сотрудников с возможностью одобрить или отклонить.",
        "pm": "Откройте раздел «Планирование» в боковом меню — на календаре видны события команды.",
        "admin": "Откройте раздел «Обзор» в боковом меню — общая аналитика по системе.",
    },
    "профиль": {
        "employee": "Откройте «Настройки» в боковом меню (шестерёнка внизу). Там можно изменить имя, фамилию, специализацию, тип занятости, часовой пояс и рабочие часы.",
        "team_lead": "Откройте «Настройки» в боковом меню — редактирование вашего профиля.",
        "hr": "Откройте «Настройки» в боковом меню — редактирование вашего профиля. Список сотрудников — в разделе «Сотрудники».",
        "pm": "Откройте «Настройки» в боковом меню — редактирование вашего профиля. Команды — в разделе «Команды».",
        "admin": "Откройте «Настройки» в боковом меню — редактирование профиля. Управление пользователями — в разделе «Пользователи».",
    },
    "календарь": {
        "employee": "Откройте раздел «Календарь» в боковом меню — ваш календарь встреч и задач.",
        "team_lead": "Откройте раздел «Обзор» в боковом меню — дашборд рисков команды.",
        "hr": "Откройте раздел «Аналитика» в боковом меню — аналитика рисков всех сотрудников.",
        "pm": "Откройте раздел «Планирование» в боковом меню — общий календарь команды с возможностью создавать события.",
        "admin": "Откройте раздел «Обзор» в боковом меню — мониторинг системы.",
    },
    "расписание": {
        "employee": "Откройте раздел «Календарь» в боковом меню — ваш календарь встреч и задач.",
        "team_lead": "Откройте раздел «Обзор» в боковом меню — дашборд рисков и рекомендаций команды.",
        "hr": "Откройте раздел «Аналитика» в боковом меню — обзор рисков и рекомендаций.",
        "pm": "Откройте раздел «Планирование» в боковом меню — общий календарь команды.",
        "admin": "Откройте раздел «Обзор» в боковом меню — мониторинг системы.",
    },
    "риск": {
        "employee": "Откройте раздел «Обзор» в боковом меню — ваш уровень риска выгорания, метрики и рекомендации.",
        "team_lead": "Откройте раздел «Обзор» в боковом меню — дашборд рисков команды по группам.",
        "hr": "Откройте раздел «Аналитика» в боковом меню — риски всех сотрудников по группам: перегрузка, устаревший профиль, вне рабочих часов и т.д.",
        "pm": "Откройте раздел «Конфликты» в боковом меню — проблемы расписания команды.",
        "admin": "Откройте раздел «Обзор» в боковом меню — мониторинг рисков по всей системе.",
    },
    "конфликт": {
        "employee": "Ваши конфликты отображаются на странице «Обзор» в блоке «Мои конфликты». Также можно разрешить конфликт через карточку конфликта.",
        "team_lead": "Откройте раздел «Проблемы» в боковом меню — список конфликтов команды с возможностью разрешения.",
        "hr": "Откройте раздел «Аналитика» в боковом меню — конфликты видны в общем дашборде рисков.",
        "pm": "Откройте раздел «Конфликты» в боковом меню — все конфликты команды с возможностью массового разрешения.",
        "admin": "Откройте раздел «Обзор» в боковом меню — общая аналитика конфликтов.",
    },
    "команда": {
        "employee": "Ваш риск и рекомендации — на странице «Обзор» в боковом меню.",
        "team_lead": "Откройте раздел «Команда» в боковом меню — состав вашей команды и дашборд рисков.",
        "hr": "Откройте раздел «Сотрудники» в боковом меню — список всех сотрудников с профилями.",
        "pm": "Откройте раздел «Команды» в боковом меню — список ваших команд и участников.",
        "admin": "Откройте раздел «Команды» в боковом меню — управление всеми командами.",
    },
    "настройки": {
        "employee": "Нажмите «Настройки» (шестерёнка) внизу бокового меню — профиль, рабочие часы, часовой пояс, тип занятости.",
        "team_lead": "Нажмите «Настройки» (шестерёнка) внизу бокового меню — редактирование профиля.",
        "hr": "Нажмите «Настройки» (шестерёнка) внизу бокового меню — редактирование профиля.",
        "pm": "Нажмите «Настройки» (шестерёнка) внизу бокового меню — редактирование профиля.",
        "admin": "Нажмите «Настройки» (шестерёнка) внизу бокового меню — редактирование профиля.",
    },
    "отпуск": {
        "employee": "Откройте раздел «Исключения» → нажмите «Добавить исключение» → выберите тип «Отпуск», укажите даты начала и окончания.",
        "team_lead": "Сотрудник создаёт исключение в разделе «Исключения», вы видите проблемы команды в разделе «Проблемы».",
        "hr": "Откройте раздел «Исключения» — там можно одобрить или отклонить запрос на отпуск сотрудника.",
        "pm": "Сотрудник создаёт исключение типа «Отпуск» в разделе «Исключения». Вы видите события команды в разделе «Планирование».",
        "admin": "Исключения сотрудников доступны через раздел «Обзор».",
    },
    "больничн": {
        "employee": "Откройте раздел «Исключения» → нажмите «Добавить исключение» → выберите тип «Больничный», укажите даты.",
        "team_lead": "Сотрудник создаёт больничный в разделе «Исключения», вы видите проблемы в разделе «Проблемы».",
        "hr": "Откройте раздел «Исключения» — можно одобрить или отклонить больничный сотрудника.",
        "pm": "Сотрудник создаёт исключение типа «Больничный» в разделе «Исключения».",
        "admin": "Исключения сотрудников доступны через раздел «Обзор».",
    },
    "задач": {
        "employee": "Откройте раздел «Задачи» в боковом меню — список ваших задач с возможностью создавать, редактировать и импортировать.",
        "team_lead": "Откройте раздел «Обзор» — дашборд рисков команды.",
        "hr": "Откройте раздел «Данные» — контроль данных сотрудников.",
        "pm": "Откройте раздел «Встречи» в боковом меню — запланированные встречи, которые вы инициировали.",
        "admin": "Откройте раздел «Обзор» — мониторинг задач по системе.",
    },
    "встреч": {
        "employee": "Ваши встречи отображаются в разделе «Календарь» и «Задачи» в боковом меню.",
        "team_lead": "Откройте раздел «Обзор» — обзор рисков команды.",
        "hr": "Откройте раздел «Аналитика» — аналитика рисков.",
        "pm": "Откройте раздел «Встречи» в боковом меню — запланированные встречи. Раздел «Планирование» — общий календарь с созданием событий.",
        "admin": "Откройте раздел «Обзор» — мониторинг системы.",
    },
    "уведомлен": {
        "employee": "Откройте раздел «Уведомления» в боковом меню (колокольчик).",
        "team_lead": "Откройте раздел «Уведомления» в боковом меню (колокольчик).",
        "hr": "Откройте раздел «Уведомления» в боковом меню (колокольчик).",
        "pm": "Откройте раздел «Уведомления» в боковом меню (колокольчик).",
        "admin": "Откройте раздел «Уведомления» в боковом меню (колокольчик).",
    },
    "обзор": {
        "employee": "Откройте раздел «Обзор» в боковом меню — ваш профиль, риск выгорания, метрики и конфликты.",
        "team_lead": "Откройте раздел «Обзор» в боковом меню — дашборд рисков команды по группам.",
        "hr": "Откройте раздел «Аналитика» в боковом меню — аналитика рисков всех сотрудников.",
        "pm": "Откройте раздел «Планирование» в боковом меню — общий календарь команды.",
        "admin": "Откройте раздел «Обзор» в боковом меню — мониторинг рисков по системе.",
    },
    "планирован": {
        "employee": "Откройте раздел «Календарь» в боковом меню — ваш календарь.",
        "team_lead": "Откройте раздел «Обзор» — дашборд рисков команды.",
        "hr": "Откройте раздел «Аналитика» — аналитика рисков.",
        "pm": "Откройте раздел «Планирование» в боковом меню — общий календарь команды с возможностью создавать события для сотрудников.",
        "admin": "Откройте раздел «Обзор» — мониторинг системы.",
    },
    "сотрудник": {
        "employee": "Ваш профиль и риск — на странице «Обзор» в боковом меню.",
        "team_lead": "Откройте раздел «Команда» — состав и риски вашей команды.",
        "hr": "Откройте раздел «Сотрудники» в боковом меню — список всех сотрудников с профилями и данными.",
        "pm": "Откройте раздел «Команды» — участники ваших команд.",
        "admin": "Откройте раздел «Пользователи» в боковом меню — управление всеми пользователями.",
    },
    "интеграц": {
        "employee": "Интеграции настраивает администратор.",
        "team_lead": "Интеграции настраивает администратор.",
        "hr": "Интеграции настраивает администратор.",
        "pm": "Интеграции настраивает администратор.",
        "admin": "Откройте раздел «Интеграции» в боковом меню — подключение календарей, HR-систем и таск-трекеров.",
    },
}


def detect_intent(message: str) -> str:
    # определяем намерение по ключевым словам
    # навигация имеет приоритет ниже чем рабочие интенты
    msg_lower = message.lower().strip()

    scores: Dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in msg_lower)
        if score > 0:
            scores[intent] = score

    # навигация должна уступать рабочим интентам
    # если у analyze/conflicts/etc такой же скор — отдаём приоритет им
    working_intents = {"analyze", "conflicts", "predict", "score", "anomalies"}
    max_score = max(scores.values()) if scores else 0
    if scores:
        top = max(scores, key=scores.get)
        # если навигация набрала столько же сколько рабочий интент — берём рабочий
        if top == "navigation" and max_score > 0:
            for wi in working_intents:
                if scores.get(wi, 0) == max_score:
                    return wi
        return top

    return "general"



# 2. ВЫЗОВ ИНСТРУМЕНТА
def call_tool(intent: str, context: Dict[str, Any]) -> Optional[ToolResult]:
    """Вызывает внутренний инструмент по имени интента.

    Если для conflicts нет конфликтов в контексте — fallback на analyze.
    """
    if intent == "general":
        return None

    # навигация не требует вызова инструмента
    if intent == "navigation":
        return None

    # Если спросили про конфликты но их нет — сделаем полный анализ
    if intent == "conflicts" and not context.get("conflicts"):
        intent = "analyze"

    tool_fn = TOOL_REGISTRY.get(intent)
    if tool_fn is None:
        return ToolResult(tool_name=intent, success=False, error=f"Неизвестный инструмент: {intent}")

    return tool_fn(context)



# 3. ГЕНЕРАЦИЯ ОТВЕТА ЧЕРЕЗ LLM
def _format_tool_data(tool_result: ToolResult, role: str = "employee") -> str:
    """Форматирует результат инструмента для вставки в промпт LLM.

    Args:
        role: внутренний формат роли (employee / pm / both).
              Фильтрует рекомендации — показывает только релевантные.
    """
    if not tool_result.success:
        return f"Ошибка при вызове инструмента {tool_result.tool_name}: {tool_result.error}"

    data = tool_result.data or {}

    if tool_result.tool_name == "analyze":
        metrics = data.get("metrics", {})
        classification = data.get("classification", {})
        recs = data.get("recommendations", {})
        risk_score = data.get('risk_score', 0)

        # общая оценка — чтобы LLM понимал контекст
        if risk_score < 0.3:
            overall = "ОБЩАЯ ОЦЕНКА: НИЗКИЙ РИСК — график в норме, проблем нет."
        elif risk_score < 0.6:
            overall = "ОБЩАЯ ОЦЕНКА: СРЕДНИЙ РИСК — есть отдельные проблемы."
        else:
            overall = "ОБЩАЯ ОЦЕНКА: ВЫСОКИЙ РИСК — серьёзные проблемы с графиком."

        # рекомендации: {"employee": [...], "pm": [...]}
        # фильтруем по роли
        if isinstance(recs, dict):
            relevant_recs = []
            if role in ("employee", "both"):
                relevant_recs.extend(recs.get("employee", []))
            if role in ("pm", "both"):
                relevant_recs.extend(recs.get("pm", []))
            recs_text = "; ".join(relevant_recs) if relevant_recs else "нет"
        elif isinstance(recs, list):
            recs_text = "; ".join(recs)
        else:
            recs_text = "нет"

        # группа: показываем только если она определена
        g_id = classification.get("groupId") or classification.get("group_id")
        g_name = classification.get("groupName") or classification.get("group_name")
        if g_id and g_name:
            group_line = f"Группа: {g_id} — {g_name}\n"
        elif g_name:
            group_line = f"Группа: {g_name}\n"
        else:
            group_line = ""

        # отпуск: показываем если on_vacation
        vacation_line = ""
        hr = data.get("hr_data") or {}
        if hr.get("on_vacation") or hr.get("onVacation"):
            vacation_line = "ВНИМАНИЕ: сотрудник официально в отпуске!\n"

        return (
            f"{overall}\n"
            f"Риск выгорания: {risk_score}\n"
            f"{vacation_line}"
            f"Метрики:\n"
            f"  — Актуальность данных: {metrics.get('A_i_freshness', 'N/A')}\n"
            f"  — Доля встреч вне рабочих часов: {metrics.get('C_i_outside_hours', 'N/A')}\n"
            f"  — Уровень загрузки: {metrics.get('L_i_workload', 'N/A')}\n"
            f"  — Часовой пояс (риск): {metrics.get('Z_i_timezone', 'N/A')}\n"
            f"  — Конфликт HR и календаря: {metrics.get('H_i_hr_conflict', 'N/A')}\n"
            f"{group_line}"
            f"Рекомендации: {recs_text}"
        )

    elif tool_result.tool_name == "predict":
        prob = data.get("conflict_probability", 0)
        pct = round(prob * 100, 1)
        level = "низкая" if prob < 0.3 else "средняя" if prob < 0.6 else "высокая"
        return f"Вероятность конфликта: {pct}% ({level}). Прогноз на {data.get('forecast_days', 7)} дней."

    elif tool_result.tool_name == "score":
        breakdown = data.get("breakdown", {})
        return (
            f"Оценка качества расписания: {data.get('quality_score', 'N/A')}/100 "
            f"(класс {data.get('grade', 'N/A')})\n"
            f"Баланс нагрузки: {breakdown.get('workload_balance', 'N/A')}\n"
            f"Защита фокусного времени: {breakdown.get('focus_time_protection', 'N/A')}\n"
            f"Стабильность расписания: {breakdown.get('schedule_stability', 'N/A')}"
        )

    elif tool_result.tool_name == "anomalies":
        patterns = data.get("detected_patterns", [])
        return (
            f"Аномалия обнаружена: {'да' if data.get('is_anomalous') else 'нет'}\n"
            f"Оценка аномальности: {data.get('anomaly_score', 'N/A')}\n"
            f"Обнаруженные паттерны: {'; '.join(patterns) if patterns else 'нет'}\n"
            f"Требуется действие: {'да' if data.get('action_required') else 'нет'}"
        )

    elif tool_result.tool_name == "conflicts":
        recs = data.get("recommendations", [])
        recs_text = []
        for r in recs:
            action = r.get("action", "")
            reason = r.get("reason", "")
            recs_text.append(f"{action}: {reason}")
        return (
            f"Конфликт: {data.get('conflict_type', 'N/A')}\n"
            f"Статус: {data.get('status', 'N/A')}\n"
            f"Пояснение: {data.get('explanation', 'N/A')}\n"
            f"Рекомендации: {'; '.join(recs_text) if recs_text else 'нет'}"
        )

    return json.dumps(data, ensure_ascii=False, indent=2)


def _nav_role_key(role: str) -> str:
    # маппинг внутренней роли на ключ SITE_SECTIONS
    mapping = {
        "employee": "employee",
        "pm": "pm",
        "team_lead": "team_lead",
        "hr": "hr",
        "admin": "admin",
    }
    return mapping.get(role, "employee")


def _build_navigation_context(message: str, role: str) -> str:
    # формируем подсказки по разделам сайта для промпта LLM
    role_key = _nav_role_key(role)
    msg_lower = message.lower()
    hints = []
    for section_key, texts in SITE_SECTIONS.items():
        if section_key in msg_lower:
            hints.append(f"- {section_key}: {texts.get(role_key, texts.get('employee', ''))}")
    if not hints:
        # даём все подсказки если не нашли конкретный раздел
        for section_key, texts in SITE_SECTIONS.items():
            hints.append(f"- {section_key}: {texts.get(role_key, texts.get('employee', ''))}")
    return "Справочник разделов:\n" + "\n".join(hints)


def _build_history_messages(history: List[ChatMessage], max_turns: int = 6) -> List[Dict[str, str]]:
    """Конвертирует историю чата в формат messages для LLM.
    Берём последние max_turns пар (user + assistant) чтобы не превышать контекст.
    """
    if not history:
        return []

    # Берём последние N сообщений
    recent = history[-(max_turns * 2):]

    messages = []
    for msg in recent:
        messages.append({"role": msg.role, "content": msg.content})

    return messages


def generate_chat_response(
    message: str,
    intent: str,
    tool_result: Optional[ToolResult],
    context: Dict[str, Any],
    history: List[ChatMessage] = None,
) -> str:
    """Генерирует ответ на русском языке через LLM.
    Если LLM недоступна — возвращает шаблонный ответ.
    """
    profile = context.get("profile", {})
    name = profile.get("name", "")
    surname = profile.get("surname", "")
    full_name = f"{name} {surname}".strip() or "Коллега"

    work_start = profile.get("workStart", profile.get("work_hours", {}).get("start", "09:00"))
    work_end = profile.get("workEnd", profile.get("work_hours", {}).get("end", "18:00"))
    if isinstance(work_start, str) and len(work_start) > 5:
        work_start = work_start[:5]
    if isinstance(work_end, str) and len(work_end) > 5:
        work_end = work_end[:5]

    specialization = profile.get("specialization", "не указана")
    employment = profile.get("employmentType", profile.get("employment", "полный рабочий день"))
    employment_ru = {
        "FULL_TIME": "полный рабочий день",
        "PART_TIME": "неполный рабочий день",
        "CONTRACT": "контракт",
    }.get(str(employment).upper().replace("-", "_"), str(employment))

    # Роль пользователя (employee / pm)
    role = normalize_role(context.get("role", ""))
    is_pm = role == "pm"

    # Данные инструмента (передаём роль для фильтрации рекомендаций)
    if tool_result:
        tool_data_text = _format_tool_data(tool_result, role=role)
    elif intent == "general":
        tool_data_text = "Инструмент не вызывался — общий вопрос пользователя."
    elif intent == "navigation":
        tool_data_text = "Инструмент не вызывался — вопрос по навигации по сайту."
    else:
        tool_data_text = "Данные инструмента недоступны."

    # Разный системный промпт для general vs tool-based
    # Адаптируем тон под роль (employee / pm)

    if intent == "navigation":
        # навигация — подсказываем где найти раздел
        nav_context = _build_navigation_context(message, role)
        system_prompt = f"""Ты — AI-ассистент. Помогаешь ориентироваться на сайте. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 1-2 предложения.
2. Укажи конкретный раздел в боковом меню и действие.
3. Обращайся к пользователю: «Откройте», «Перейдите».
4. ЗАПРЕЩЕНО: упоминать «я», «AI».

{nav_context}

Формат ответа: ТОЛЬКО JSON {{"answer": "ваш ответ"}}"""
    elif intent == "general":
        if is_pm:
            system_prompt = """Ты — AI-ассистент для Project Manager. Помогаешь управлять рабочими графиками команды и предотвращать выгорание. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-3 предложения.
2. Ты — АССИСТЕНТ. НЕ описывай PM, а помогай ему.
3. Если спрашивают о возможностях — перечисли: анализ риска выгорания сотрудников, оценка качества расписания, прогноз конфликтов, обнаружение аномалий, разрешение конфликтов.
4. Обращайся к PM, а не к сотруднику. Используй «у сотрудника», «команда».
5. ЗАПРЕЩЕНО: упоминать «я», «AI», технические термины.
6. ЗАПРЕЩЕНО: описывать пользователя — ты отвечаешь пользователю, а не описываешь его.
7. ЗАПРЕЩЕНО: «у тебя», «ты» — используйте «у сотрудника», «вы».

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
        else:
            system_prompt = """Ты — AI-ассистент для анализа рабочих графиков и предотвращения выгорания. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-3 предложения.
2. Ты — АССИСТЕНТ, который помогает сотруднику. НЕ описывай сотрудника, а помогай ему.
3. Если спрашивают «кто ты?» или «что ты умеешь?» — ответь: ассистент по анализу рабочих графиков. Перечисли: анализ риска выгорания, оценка качества расписания, прогноз конфликтов, обнаружение аномалий, разрешение конфликтов.
4. Если вопрос не связан с рабочим графиком — вежливо скажи, что помогаешь только с вопросами о рабочих графиках и выгорании.
5. Учитывай контекст предыдущих сообщений если он есть.
6. ЗАПРЕЩЕНО: упоминать «я», «AI», технические термины.
7. ЗАПРЕЩЕНО: описывать пользователя (имя, должность, рабочие часы) — ты отвечаешь пользователю, а не описываешь его.
8. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у вас», «вы».

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
    else:
        if is_pm:
            system_prompt = """Ты — AI-ассистент для Project Manager. Помогаешь управлять рабочими графиками команды и предотвращать выгорание. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-4 предложения, по существу.
2. Если риск НИЗКИЙ (ниже 30%) — скажите что у сотрудника всё хорошо, график в норме. НЕ выдумывайте проблемы.
3. Если риск СРЕДНИЙ или ВЫСОКИЙ — используй повелительное наклонение: «Пересмотрите», «Перераспределите», «Назначьте».
4. Пиши с большой буквы в начале предложений.
5. ОБРАЩАЙСЯ К PM, не к сотруднику: «у сотрудника», «команда», а не «у вас».
6. ОБЯЗАТЕЛЬНО упоминай ГЛАВНЫЙ показатель из <результат_инструмента> первым предложением.
7. Учитывай контекст предыдущих сообщений.
8. ЗАПРЕЩЕНО: технические термины (PART_TIME, L_i_workload и т.д.).
9. ЗАПРЕЩЕНО: «чтобы избежать», «для снижения», «рекомендуется».
10. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у сотрудника», «вы».
11. ЗАПРЕЩЕНО: упоминать «я» или «AI».
12. ЗАПРЕЩЕНО: выдумывать проблемы — если все метрики в норме, так и скажите.
13. ЗАПРЕЩЕНО: советовать перенести встречи, которые ВХОДЯТ в рабочее время сотрудника.

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
        else:
            system_prompt = """Ты — AI-ассистент для анализа рабочих графиков и предотвращения выгорания. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-4 предложения, по существу.
2. Если риск НИЗКИЙ (ниже 30%) — скажите что всё хорошо, график в норме. НЕ выдумывайте проблемы и НЕ давайте рекомендации по улучшению.
3. Если риск СРЕДНИЙ или ВЫСОКИЙ — используй повелительное наклонение: «Перенесите», «Обновите», «Сократите».
4. Пиши с большой буквы в начале предложений.
5. Ты обращаешься НАПРЯМУЮ к сотруднику. Говори «ваш риск», «ваши встречи», «вы работаете» — а НЕ «информация о сотруднике», «у сотрудника».
6. ОБЯЗАТЕЛЬНО упоминай ГЛАВНЫЙ показатель из <результат_инструмента> первым предложением:
   - analyze → «ваш риск выгорания X%»
   - score → «оценка вашего расписания X/100 (класс Y)»
   - predict → «вероятность конфликта X%»
   - anomalies → «аномалия обнаружена / не обнаружена, оценка X%»
   - conflicts → «конфликт типа X, статус Y»
7. Учитывай контекст предыдущих сообщений — если ранее был «риск 32%», а спрашивают «а что с ним?», повтори и разъясни «32%».
8. ЗАПРЕЩЕНО: технические термины (PART_TIME, FULL_TIME, L_i_workload и т.д.) — используй человеческий язык.
9. ЗАПРЕЩЕНО: «чтобы избежать», «для снижения», «рекомендуется», «обратите внимание».
10. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у вас», «вы».
11. ЗАПРЕЩЕНО: упоминать «я» или «AI».
12. ЗАПРЕЩЕНО: выдумывать проблемы — если все метрики в норме, так и скажите.
13. ЗАПРЕЩЕНО: советовать перенести встречи, которые ВХОДЯТ в рабочее время.

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""

    # Для general/navigation — профиль не нужен, только вопрос
    # Для рабочих интентов — профиль нужен чтобы дать персональный ответ
    is_work_intent = intent in ("analyze", "conflicts", "predict", "score", "anomalies")

    if is_work_intent:
        # рабочий интент — передаём профиль для персонализации
        if is_pm:
            # PM спрашивает о сотруднике — данные в третьем лице
            question_instruction = "Ответь на вопрос Project Manager'а о сотруднике на основе данных инструмента и контекста разговора."
            user_prompt = f"""<сотрудник>
Имя: {full_name}
Специализация: {specialization}
Тип занятости: {employment_ru}
Рабочие часы: {work_start}–{work_end}
</сотрудник>

<вопрос_пользователя>
{message}
</вопрос_пользователя>

<результат_инструмента name="{intent}">
{tool_data_text}
</результат_инструмента>

{question_instruction} Верни ТОЛЬКО JSON."""
        else:
            # Сотрудник спрашивает о себе — обращаемся напрямую на «вы»
            question_instruction = "Ответь на вопрос сотрудника на основе данных инструмента. Обращайся на «вы» — это ИХ профиль, ИХ график, ИХ риск."
            user_prompt = f"""<ваш_профиль>
Имя: {full_name}
Специализация: {specialization}
Тип занятости: {employment_ru}
Рабочие часы: {work_start}–{work_end}
</ваш_профиль>

<ваш_вопрос>
{message}
</ваш_вопрос>

<результат_инструмента name="{intent}">
{tool_data_text}
</результат_инструмента>

{question_instruction} Верни ТОЛЬКО JSON."""
    else:
        # general / navigation — профиль не нужен, бот отвечает как ассистент
        user_prompt = f"""<вопрос_пользователя>
{message}
</вопрос_пользователя>

{tool_data_text} Ответь на русском языке. Верни ТОЛЬКО JSON."""

    # Собираем сообщения для LLM: system + history + текущий user_prompt
    llm_messages = [{"role": "system", "content": system_prompt}]

    # Добавляем историю (пропускаем системные сообщения из истории)
    if history:
        history_msgs = _build_history_messages(history)
        llm_messages.extend(history_msgs)

    # Текущий запрос
    llm_messages.append({"role": "user", "content": user_prompt})

    try:
        from app.llm.client import ollama_client

        response = ollama_client.chat.completions.create(
            model="qwen2.5:7b",
            messages=llm_messages,
            response_format={"type": "json_object"},
            temperature=0.05,
            max_tokens=200,
            timeout=15.0,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        answer = data.get("answer", "").strip()

        if answer and len(answer) > 10:
            return answer

    except Exception as e:
        print(f"[chat engine] LLM ошибка: {e}")

    # Fallback — шаблонный ответ без LLM
    if tool_result and tool_result.success:
        print(f"[chat engine] LLM fallback. tool_data keys: {list((tool_result.data or {}).keys())}, classification: {tool_result.data.get('classification')}")
    return _fallback_response(message, intent, tool_result, full_name, is_pm=is_pm)


def _fallback_response(
    message: str,
    intent: str,
    tool_result: Optional[ToolResult],
    full_name: str,
    is_pm: bool = False,
) -> str:
    """Шаблонный ответ если LLM недоступна.

    Args:
        is_pm: если True — ответ формулируется для Project Manager
               (обращение «у сотрудника», «вашей команды»).
    """
    if intent == "navigation":
        # навигация — подсказка по разделам сайта
        role_key = "pm" if is_pm else "employee"
        msg_lower = message.lower()
        for section_key, texts in SITE_SECTIONS.items():
            if section_key in msg_lower:
                return texts.get(role_key, texts.get("employee", ""))
        # если не нашли конкретный раздел — общий ответ
        fallback_menu = {
            "employee": "Обзор, Календарь, Задачи, Исключения, Уведомления или Настройки",
            "team_lead": "Обзор, Команда, Проблемы, Уведомления или Настройки",
            "hr": "Аналитика, Сотрудники, Данные, Исключения, Уведомления или Настройки",
            "pm": "Планирование, Встречи, Команды, Конфликты, Уведомления или Настройки",
            "admin": "Обзор, Пользователи, Команды, Интеграции, Уведомления или Настройки",
        }
        menu = fallback_menu.get(role_key, fallback_menu["employee"])
        return f"Перейдите в нужный раздел через боковое меню: {menu}."

    if intent == "general":
        if is_pm:
            return (
                "Ассистент по анализу рабочих графиков. "
                "Спросите о риске выгорания сотрудника, оценке расписания, "
                "прогнозе конфликтов, аномалиях или разрешении конфликтов."
            )
        return (
            "Ассистент по анализу рабочих графиков. "
            "Спросите о риске выгорания, оценке расписания, "
            "прогнозе конфликтов, аномалиях или разрешении конфликтов."
        )

    if not tool_result or not tool_result.success:
        error_msg = tool_result.error if tool_result else "нет данных"
        if is_pm:
            return f"Не удалось получить данные по сотруднику ({error_msg}). Попробуйте переформулировать вопрос."
        return f"{full_name}, не удалось получить данные ({error_msg}). Попробуйте переформулировать вопрос."

    data = tool_result.data or {}

    if intent == "analyze":
        risk = data.get("risk_score", 0)
        level = "низкий" if risk < 0.3 else "средний" if risk < 0.6 else "высокий"
        cls = data.get("classification") or {}
        g_name = cls.get("groupName") or cls.get("group_name") or ""
        # группа: показываем только если она определена
        group_part = f" Группа: {g_name}." if g_name else ""
        if is_pm:
            return f"Уровень риска выгорания сотрудника {full_name} — {level} ({risk:.0%}).{group_part}"
        return f"{full_name}, ваш уровень риска выгорания — {level} ({risk:.0%}).{group_part}"

    if intent == "predict":
        prob = data.get("conflict_probability", 0)
        if is_pm:
            return f"Вероятность конфликта у сотрудника {full_name} — {prob:.0%} на ближайшие 7 дней."
        return f"{full_name}, вероятность конфликта — {prob:.0%} на ближайшие 7 дней."

    if intent == "score":
        score = data.get("quality_score", 0)
        grade = data.get("grade", "?")
        if is_pm:
            return f"Оценка расписания сотрудника {full_name} — {score}/100 (класс {grade})."
        return f"{full_name}, оценка вашего расписания — {score}/100 (класс {grade})."

    if intent == "anomalies":
        is_anom = data.get("is_anomalous", False)
        if is_anom:
            if is_pm:
                return f"В графике сотрудника {full_name} обнаружены аномалии. Рекомендуется проверить расписание."
            return f"{full_name}, в вашем графике обнаружены аномалии. Проверьте расписание на необычные паттерны."
        if is_pm:
            return f"Аномалий в графике сотрудника {full_name} не обнаружено. Расписание в пределах нормы."
        return f"{full_name}, аномалий в графике не обнаружено. Расписание в пределах нормы."

    if intent == "conflicts":
        explanation = data.get("explanation", "")
        if is_pm:
            return f"Конфликт сотрудника {full_name} проанализирован. {explanation}" if explanation else f"Конфликт сотрудника {full_name} проанализирован. Проверьте рекомендации."
        return f"{full_name}, {explanation}" if explanation else f"{full_name}, конфликт проанализирован. Проверьте рекомендации."

    if is_pm:
        return "Запрос обработан. Проверьте данные в панели управления командой."
    return f"{full_name}, ваш запрос обработан. Проверьте данные в личном кабинете."



# ГЛАВНЫЙ МЕТОД
def process_chat(request: ChatRequest) -> ChatResponse:
    """Основной пайплайн чат-ассистента.

    1. Определяет намерение
    2. Вызывает инструмент
    3. Генерирует ответ через LLM (с учётом истории)
    4. Возвращает обновлённую историю
    """
    now = datetime.utcnow().isoformat() + "Z"

    # 1. Intent detection
    intent = detect_intent(request.message)

    # 2. Build context
    role = normalize_role(getattr(request, "role", None) or "EMPLOYEE")
    context = {
        "user_id": request.user_id,
        "profile": request.profile or {},
        "tasks": request.tasks or [],
        "meetings": request.meetings or [],
        "conflicts": request.conflicts or [],
        "hr_data": request.hr_data or {},
        "role": role,
    }

    # 3. Call tool
    tool_result = call_tool(intent, context)

    # 4. Generate response (передаём историю для контекста)
    answer = generate_chat_response(
        message=request.message,
        intent=intent,
        tool_result=tool_result,
        context=context,
        history=request.history or [],
    )

    # 5. Обновляем историю: предыдущие + новый вопрос + ответ
    updated_history = list(request.history or [])
    updated_history.append(ChatMessage(role="user", content=request.message, timestamp=now))
    updated_history.append(ChatMessage(role="assistant", content=answer, timestamp=now))

    # Реальный инструмент (может отличаться от intent при fallback)
    actual_tool = tool_result.tool_name if tool_result and tool_result.success else (intent if intent != "general" else None)

    return ChatResponse(
        answer=answer,
        tool_used=actual_tool,
        tool_data=tool_result.data if tool_result and tool_result.success else None,
        history=updated_history,
        timestamp=now,
    )