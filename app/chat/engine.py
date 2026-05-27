import os
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.chat.schemas import ChatRequest, ChatResponse, ChatMessage, ToolResult
from app.chat.tools import TOOL_REGISTRY


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
def _format_tool_data(tool_result: ToolResult) -> str:
    """Форматирует результат инструмента для вставки в промпт LLM."""
    if not tool_result.success:
        return f"Ошибка при вызове инструмента {tool_result.tool_name}: {tool_result.error}"

    data = tool_result.data or {}

    if tool_result.tool_name == "analyze":
        metrics = data.get("metrics", {})
        classification = data.get("classification", {})
        recs = data.get("recommendations", [])
        return (
            f"Риск выгорания: {data.get('risk_score', 'N/A')}\n"
            f"Метрики:\n"
            f"  — Актуальность данных: {metrics.get('A_i_freshness', 'N/A')}\n"
            f"  — Доля встреч вне рабочих часов: {metrics.get('C_i_outside_hours', 'N/A')}\n"
            f"  — Уровень загрузки: {metrics.get('L_i_workload', 'N/A')}\n"
            f"  — Часовой пояс (риск): {metrics.get('Z_i_timezone', 'N/A')}\n"
            f"  — Конфликт HR и календаря: {metrics.get('H_i_hr_conflict', 'N/A')}\n"
            f"Группа: {classification.get('group_id', 'N/A')} — {classification.get('group_name', 'N/A')}\n"
            f"Рекомендации: {'; '.join(recs) if recs else 'нет'}"
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

    # Данные инструмента
    if tool_result:
        tool_data_text = _format_tool_data(tool_result)
    elif intent == "general":
        tool_data_text = "Инструмент не вызывался — общий вопрос пользователя."
    else:
        tool_data_text = "Данные инструмента недоступны."

    # Разный системный промпт для general и tool-based
    if intent == "general":
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
        system_prompt = """Ты — AI-ассистент для анализа рабочих графиков и предотвращения выгорания. Отвечай на русском языке.

ПРАВИЛА:
1. Отвечай КОРОТКО — 2-4 предложения, по существу.
2. Используй повелительное наклонение: «Перенесите», «Обновите», «Сократите» — а не страдательный залог.
3. Пиши с большой буквы в начале предложений.
4. Обращайся к сотруднику по имени.
5. ОБЯЗАТЕЛЬНО упоминай конкретные числа из раздела <результат_инструмента>: проценты (например «32%»), часы, баллы. НИКОГДА не давай ответ без конкретных цифр из данных.
6. Учитывай контекст предыдущих сообщений если он есть — если пользователь спрашивает «а что с ним?» — понимай что «он» из контекста.
7. ЗАПРЕЩЕНО: технические термины (PART_TIME, FULL_TIME, L_i_workload и т.д.) — используй человеческий язык.
8. ЗАПРЕЩЕНО: «чтобы избежать», «для снижения», «рекомендуется», «обратите внимание».
9. ЗАПРЕЩЕНО: «у тебя», «ты» — используй «у вас», «вы».
10. ЗАПРЕЩЕНО: упоминать «я» или «AI».
11. ЗАПРЕЩЕНО: общие фразы без чисел — если в данных есть «Риск выгорания: 0.322», напиши «риск 32%», а не «риск зависит от факторов».
12. Если данных недостаточно — попросите уточнить вопрос.

Формат ответа: ТОЛЬКО JSON {"answer": "ваш ответ"}"""

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

Ответь на вопрос сотрудника на основе данных инструмента и контекста разговора. Верни ТОЛЬКО JSON."""

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

    # Fallback
    return _fallback_response(message, intent, tool_result, full_name)


def _fallback_response(
    message: str,
    intent: str,
    tool_result: Optional[ToolResult],
    full_name: str,
) -> str:
    # Шаблонный ответ если LLM недоступна.
    if intent == "general":
        return (
            f"{full_name}, я умею анализировать рабочие графики. "
            "Спросите меня о риске выгорания, оценке расписания, "
            "прогнозе конфликтов, аномалиях или разрешении конфликтов."
        )

    if not tool_result or not tool_result.success:
        error_msg = tool_result.error if tool_result else "нет данных"
        return f"{full_name}, не удалось получить данные ({error_msg}). Попробуйте переформулировать вопрос."

    data = tool_result.data or {}

    if intent == "analyze":
        risk = data.get("risk_score", 0)
        level = "низкий" if risk < 0.3 else "средний" if risk < 0.6 else "высокий"
        group_name = data.get("classification", {}).get("group_name", "не определена")
        return f"{full_name}, ваш уровень риска выгорания — {level} ({risk:.0%}). Группа: {group_name}."

    if intent == "predict":
        prob = data.get("conflict_probability", 0)
        return f"{full_name}, вероятность конфликта — {prob:.0%} на ближайшие 7 дней."

    if intent == "score":
        score = data.get("quality_score", 0)
        grade = data.get("grade", "?")
        return f"{full_name}, оценка вашего расписания — {score}/100 (класс {grade})."

    if intent == "anomalies":
        is_anom = data.get("is_anomalous", False)
        if is_anom:
            return f"{full_name}, в вашем графике обнаружены аномалии. Проверьте расписание на необычные паттерны."
        return f"{full_name}, аномалий в графике не обнаружено. Расписание в пределах нормы."

    if intent == "conflicts":
        explanation = data.get("explanation", "")
        return f"{full_name}, {explanation}" if explanation else f"{full_name}, конфликт проанализирован. Проверьте рекомендации."

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
    context = {
        "user_id": request.user_id,
        "profile": request.profile or {},
        "tasks": request.tasks or [],
        "meetings": request.meetings or [],
        "conflicts": request.conflicts or [],
        "hr_data": request.hr_data or {},
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