from pydantic import BaseModel, Field
from typing import List, Dict

class PredictionResponse(BaseModel):
    conflict_probability: float = Field(alias="conflictProbability", ge=0.0, le=1.0)
    top_risk_factors: List[str] = Field(alias="topRiskFactors")
    forecast_days: int = Field(alias="forecastDays", default=7)

    model_config = {"populate_by_name": True}

class ScoreBreakdown(BaseModel):
    workload_balance: float = Field(alias="workloadBalance")
    focus_time_protection: float = Field(alias="focusTimeProtection")
    schedule_stability: float = Field(alias="scheduleStability")

    model_config = {"populate_by_name": True}

class ScoreResponse(BaseModel):
    user_id: int = Field(alias="userId")
    quality_score: float = Field(alias="qualityScore", ge=0.0, le=100.0)
    grade: str
    breakdown: ScoreBreakdown

    model_config = {"populate_by_name": True}

class AnomalyResponse(BaseModel):
    is_anomalous: bool = Field(alias="isAnomalous")
    anomaly_score: float = Field(alias="anomalyScore")
    detected_patterns: List[str] = Field(alias="detectedPatterns")
    action_required: str = Field(alias="actionRequired")

    model_config = {"populate_by_name": True}