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
}


def detect_intent(message: str) -> str:
    """Определяет намерение пользователя по ключевым словам
    Возвращает имя инструмента или "general" если ничего не подошло
    """
    msg_lower = message.lower().strip()

    scores: Dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in msg_lower)
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)

    return "general"



# 2. ВЫЗОВ ИНСТРУМЕНТА
def call_tool(intent: str, context: Dict[str, Any]) -> Optional[ToolResult]:
    """Вызывает внутренний инструмент по имени интента
    """
    if intent == "general":
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
    """Форматирует результат инструмента для вставки в промпт LLM

    Args:
        role: внутренний формат роли (employee / pm / both)
              Фильтрует рекомендации — показывает только релевантные
    """
    if not tool_result.success:
        return f"Ошибка при вызове инструмента {tool_result.tool_name}: {tool_result.error}"

    data = tool_result.data or {}

    if tool_result.tool_name == "analyze":
        metrics = data.get("metrics", {})
        classification = data.get("classification", {})
        recs = data.get("recommendations", {})
        # recommendations: {"employee": [...], "pm": [...]}
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

        return (
            f"Риск выгорания: {data.get('risk_score', 'N/A')}\n"
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


def _build_history_messages(history: List[ChatMessage], max_turns: int = 6) -> List[Dict[str, str]]:
    """Конвертирует историю чата в формат messages для LLM
    Берём последние max_turns пар (user + assistant) чтобы не превышать контекст
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
    else:
        tool_data_text = "Данные инструмента недоступны."

    # Разный системный промпт для general и tool-based
    # Адаптируем тон под роль (employee / pm)

    if intent == "general":
        if is_pm:
            system_prompt = """Ты — AI-ассистент для Project Manager. Помогаешь управлять рабочими графиками команды и предотвращать выгорание. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-3 предложения.
2. Если спрашивают о возможностях — перечисли: анализ риска выгорания сотрудников, оценка качества расписания, прогноз конфликтов, обнаружение аномалий, разрешение конфликтов.
3. Обращайся к PM, а не к сотруднику. Используй «у сотрудника», «команда».
4. ЗАПРЕЩЕНО: упоминать «я», «AI», технические термины.
5. ЗАПРЕЩЕНО: «у тебя», «ты» — используйте «у сотрудника», «вы».

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
        else:
            system_prompt = """Ты — AI-ассистент для анализа рабочих графиков и предотвращения выгорания. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-3 предложения.
2. Если спрашивают о твоих возможностях — перечисли: анализ риска выгорания, оценка качества расписания, прогноз конфликтов, обнаружение аномалий, разрешение конфликтов.
3. Если вопрос не связан с рабочим графиком — вежливо скажи, что помогаешь только с вопросами о рабочих графиках и выгорании.
4. Учитывай контекст предыдущих сообщений если он есть.
5. ЗАПРЕЩЕНО: упоминать «я», «AI», технические термины.
6. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у вас», «вы».

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
    else:
        if is_pm:
            system_prompt = """Ты — AI-ассистент для Project Manager. Помогаешь управлять рабочими графиками команды и предотвращать выгорание. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-4 предложения, по существу.
2. Используй повелительное наклонение: «Пересмотрите», «Перераспределите», «Назначьте».
3. Пиши с большой буквы в начале предложений.
4. ОБРАЩАЙСЯ К PM, не к сотруднику: «у сотрудника», «команда», а не «у вас».
5. ОБЯЗАТЕЛЬНО упоминай ГЛАВНЫЙ показатель из <результат_инструмента> первым предложением.
6. Учитывай контекст предыдущих сообщений.
7. ЗАПРЕЩЕНО: технические термины (PART_TIME, L_i_workload и т.д.).
8. ЗАПРЕЩЕНО: «чтобы избежать», «для снижения», «рекомендуется».
9. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у сотрудника», «вы».
10. ЗАПРЕЩЕНО: упоминать «я» или «AI».
11. ЗАПРЕЩЕНО: общие фразы без чисел — всегда вытащи главное число из данных.

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""
        else:
            system_prompt = """Ты — AI-ассистент для анализа рабочих графиков и предотвращения выгорания. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-4 предложения, по существу.
2. Используй повелительное наклонение: «Перенесите», «Обновите», «Сократите» — а не страдательный залог.
3. Пиши с большой буквы в начале предложений.
4. Обращайся к сотруднику по имени.
5. ОБЯЗАТЕЛЬНО упоминай ГЛАВНЫЙ показатель из <результат_инструмента> первым предложением:
   - analyze → «риск выгорания X%»
   - score → «оценка расписания X/100 (класс Y)»
   - predict → «вероятность конфликта X%»
   - anomalies → «аномалия обнаружена / не обнаружена, оценка X%»
   - conflicts → «конфликт типа X, статус Y»
6. Учитывай контекст предыдущих сообщений — если ранее был «риск 32%», а спрашивают «а что с ним?», повтори и разъясни «32%».
7. ЗАПРЕЩЕНО: технические термины (PART_TIME, FULL_TIME, L_i_workload и т.д.) — используй человеческий язык.
8. ЗАПРЕЩЕНО: «чтобы избежать», «для снижения», «рекомендуется», «обратите внимание».
9. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у вас», «вы».
10. ЗАПРЕЩЕНО: упоминать «я» или «AI».
11. ЗАПРЕЩЕНО: общие фразы без чисел — всегда вытащи главное число из данных.
12. Если данных недостаточно — попросите уточнить вопрос.

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""

    # Адаптируем user_prompt под роль
    subject_label = "сотрудник"
    if is_pm:
        question_instruction = "Ответь на вопрос Project Manager'а о сотруднике на основе данных инструмента и контекста разговора."
    else:
        question_instruction = "Ответь на вопрос сотрудника на основе данных инструмента и контекста разговора."

    user_prompt = f"""<{subject_label}>
Имя: {full_name}
Специализация: {specialization}
Тип занятости: {employment_ru}
Рабочие часы: {work_start}–{work_end}
</{subject_label}>

<вопрос_пользователя>
{message}
</вопрос_пользователя>

<результат_инструмента name="{intent}">
{tool_data_text}
</результат_инструмента>

{question_instruction} Верни ТОЛЬКО JSON."""

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
    if intent == "general":
        if is_pm:
            return (
                "Я умею анализировать рабочие графики сотрудников. "
                "Спросите о риске выгорания сотрудника, оценке расписания, "
                "прогнозе конфликтов, аномалиях или разрешении конфликтов."
            )
        return (
            f"{full_name}, я умею анализировать рабочие графики. "
            "Спросите меня о риске выгорания, оценке расписания, "
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