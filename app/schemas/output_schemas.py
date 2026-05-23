from pydantic import BaseModel
from typing import List, Dict

class RiskMetrics(BaseModel):
    A_i_freshness: float
    L_i_workload: float
    C_i_outside_hours: float
    Z_i_timezone: float
    H_i_hr_conflict: float

class ClassificationResult(BaseModel):
    group_id: int
    group_name: str

class AnalyzeResponse(BaseModel):
    user_id: str
    risk_score: float
    metrics: RiskMetrics
    classification: ClassificationResult
    recommendations: List[str]