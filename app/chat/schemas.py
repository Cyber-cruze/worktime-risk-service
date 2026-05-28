from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime



# Сообщения в истории чата
class ChatMessage(BaseModel):
    # Одно сообщение в истории чата
    role: str = Field(..., description="user или assistant")
    content: str = Field(..., description="Текст сообщения")
    timestamp: Optional[str] = Field(None, description="ISO время сообщения")



# Запрос
class ChatRequest(BaseModel):
    """Запрос к чат-ассистенту

    Фронтенд отправляет вопрос, контекст и историю предыдущих сообщений
    История позволяет AI помнить о чём уже говорили
    """
    message: str = Field(..., description="Вопрос пользователя на естественном языке")
    session_id: Optional[str] = Field(None, description="ID сессии чата (для логирования)")
    user_id: Optional[int] = None
    role: Optional[str] = Field(
        "EMPLOYEE",
        description="Роль: EMPLOYEE (сотрудник) или PROJECT_MANAGER (Project Manager)"
    )
    profile: Optional[Dict[str, Any]] = None
    tasks: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    meetings: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    conflicts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    hr_data: Optional[Dict[str, Any]] = None
    history: Optional[List[ChatMessage]] = Field(
        default_factory=list,
        description="История предыдущих сообщений в этом чате. "
                    "Фронтенд хранит историю и отправляет с каждым запросом."
    )



# Внутренний тип (не в API)
class ToolResult(BaseModel):
    # Результат вызова внутреннего инструмента
    tool_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None



# Ответ
class ChatResponse(BaseModel):
    """Ответ чат-ассистента.

    Включает историю — фронтенд добавляет ответ к локальной истории
    и показывает весь список сообщений в UI.
    """
    answer: str = Field(..., description="Ответ AI на русском языке")
    tool_used: Optional[str] = Field(None, description="Вызванный инструмент: analyze | predict | score | anomalies | conflicts")
    tool_data: Optional[Dict[str, Any]] = Field(None, description="Сырые данные инструмента (опционально)")
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Обновлённая история чата: предыдущие сообщения + новый вопрос + ответ"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO 8601 время ответа"
    )