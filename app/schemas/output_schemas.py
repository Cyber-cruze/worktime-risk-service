from pydantic import BaseModel, Field
from typing import List, Dict

class RiskMetrics(BaseModel):
    A_i_freshness: float
    L_i_workload: float
    C_i_outside_hours: float
    Z_i_timezone: float
    H_i_hr_conflict: float

class ClassificationResult(BaseModel):
    group_id: int = Field(alias="groupId")
    group_name: str = Field(alias="groupName")

    model_config = {"populate_by_name": True}

class RoleRecommendations(BaseModel):
    """Рекомендации, разделённые по ролям."""
    employee: List[str] = Field(
        default_factory=list,
        description="Рекомендации для сотрудника"
    )
    pm: List[str] = Field(
        default_factory=list,
        description="Рекомендации для Project Manager"
    )

class AnalyzeResponse(BaseModel):
    user_id: str
    risk_score: float
    metrics: RiskMetrics
    classification: ClassificationResult
    recommendations: RoleRecommendations