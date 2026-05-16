from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class RiskInput(BaseModel):
    user_id: str

    weekly_work_hours: float = Field(..., description="Часов работы в неделю")
    overtime_hours: float = Field(..., ge=0, description="Часы переработки")
    meeting_density: float = Field(..., ge=0.0, le=1.0, description="Плотность встреч (0.0 - 1.0)")
    consecutive_work_days: int = Field(..., ge=0, description="Дней подряд без отдыха")
    conflict_count: int = Field(..., ge=0, description="Количество конфликтов")
    workload_trend: float = Field(..., ge=-1.0, le=1.0, description="Тренд нагрузки (-1.0 падение, 1.0 рост)")
    night_weekend_hours: Optional[float] = Field(0.0, ge=0.0, description="Часы в выходные/ночь")

class RiskResponse(BaseModel):
    user_id: str
    score: float
    category: str
    forecast_3d: List[float]
    recommendations: List[str]
    feature_importance: Optional[Dict[str, float]] = None