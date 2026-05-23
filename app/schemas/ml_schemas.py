from pydantic import BaseModel, Field
from typing import List, Dict

class PredictionResponse(BaseModel):
    conflict_probability: float = Field(ge=0.0, le=1.0)
    top_risk_factors: List[str]
    forecast_days: int = 7

class ScoreBreakdown(BaseModel):
    workload_balance: float
    focus_time_protection: float
    schedule_stability: float

class ScoreResponse(BaseModel):
    user_id: int
    quality_score: float = Field(ge=0.0, le=100.0)
    grade: str  # "A", "B", "C", "D"
    breakdown: ScoreBreakdown

class AnomalyResponse(BaseModel):
    is_anomalous: bool
    anomaly_score: float
    detected_patterns: List[str]
    action_required: str