from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date


# Входные данные:

class WorkHours(BaseModel):
    start: str = Field(..., description="Начало рабочего дня, например '09:00'")
    end: str = Field(..., description="Конец рабочего дня, например '18:00'")

class UserProfile(BaseModel):
    work_hours: WorkHours
    timezone: str = Field(..., description="Часовой пояс сотрудника, например 'Europe/Moscow'")
    last_updated: date = Field(..., description="Дата последнего обновления профиля")
    employment: str = Field("full-time", description="full-time или part-time")

class Task(BaseModel):
    id: str
    hours: float = Field(..., ge=0, description="Плановые часы на задачу")
    deadline: date

class Meeting(BaseModel):
    start: datetime
    end: datetime

class Conflict(BaseModel):
    type: str = Field(..., description="outside_hours | overlap | hr_mismatch")
    severity: str = Field(..., description="low | medium | high | critical")

class HRData(BaseModel):
    official_schedule: str = Field(..., description="График из HR-системы, например '09:00-18:00'")
    official_timezone: str
    on_vacation: bool = False

class AnalysisRequest(BaseModel):
    user_id: str
    profile: UserProfile
    tasks: List[Task] = []
    meetings: List[Meeting] = []
    conflicts: List[Conflict] = []
    hr_data: HRData


# Выходные данные:

class RiskMetrics(BaseModel):
    overload_ratio: float = Field(..., description="Нагрузка: (часы задач + часов встреч) / рабочие часы")
    freshness_score: float = Field(..., ge=0.0, le=1.0, description="Актуальность данных (0.0 - устарело, 1.0 - свежо)")
    timezone_match: float = Field(..., ge=0.0, le=1.0, description="Совпадение часового пояса с реальной активностью")
    hr_conflict_score: float = Field(..., ge=0.0, le=1.0, description="Расхождение HR-данных и календаря")

class AnalysisResponse(BaseModel):
    user_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Итоговый риск по формуле Ri (0.0 - нет риска, 1.0 - критический)")
    risk_level: str = Field(..., description="low | medium | high")
    metrics: RiskMetrics
    group: int = Field(..., ge=1, le=9, description="Класс сотрудника от 1 до 9")
    group_name: str
    recommendations: List[str]