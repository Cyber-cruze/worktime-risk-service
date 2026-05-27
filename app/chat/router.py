from fastapi import APIRouter
from app.chat.schemas import ChatRequest, ChatResponse
from app.chat.engine import process_chat

router = APIRouter(prefix="/chat", tags=["AI Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="AI Chat Assistant",
    description=(
        "AI-ассистент для анализа рабочих графиков. "
        "Принимает вопрос на русском языке, контекст сотрудника (профиль, задачи, встречи) "
        "и историю предыдущих сообщений. Автоматически определяет намерение и вызывает "
        "нужный инструмент анализа. Возвращает ответ и обновлённую историю чата.\n\n"
        "**Поддерживаемые интенты** (определяются автоматически по вопросу):\n"
        "- `analyze` — полный анализ риска выгорания\n"
        "- `predict` — ML-прогноз вероятности конфликта\n"
        "- `score` — оценка качества расписания (A/B/C/D)\n"
        "- `anomalies` — обнаружение аномалий в графике\n"
        "- `conflicts` — разрешение конфликтов расписания\n\n"
        "**История чата**: отправляйте массив `history` с предыдущими сообщениями, "
        "чтобы AI помнил контекст разговора. Ответ содержит обновлённую историю — "
        "сохраните её на фронтенде и отправляйте со следующим запросом."
    ),
)
def chat(request: ChatRequest):
    return process_chat(request)
