from pydantic import BaseModel, Field
from typing import List, Dict

class RiskMetrics(BaseModel):
    A_i_freshness: float = Field(alias="freshness")
    L_i_workload: float = Field(alias="workload")
    C_i_outside_hours: float = Field(alias="outsideHours")
    Z_i_timezone: float = Field(alias="timezone")
    H_i_hr_conflict: float = Field(alias="hrConflict")

    model_config = {"populate_by_name": True}

class ClassificationResult(BaseModel):
    group_id: int = Field(alias="groupId")
    group_name: str = Field(alias="groupName")

    model_config = {"populate_by_name": True}

class RoleRecommendations(BaseModel):
    employee: List[str] = Field(
        default_factory=list,
        description="Рекомендации для сотрудника"
    )
    pm: List[str] = Field(
        default_factory=list,
        description="Рекомендации для Project Manager"
    )

class AnalyzeResponse(BaseModel):
    user_id: int = Field(alias="userId")
    risk_score: float = Field(alias="riskScore")
    metrics: RiskMetrics
    classification: ClassificationResult
    recommendations: RoleRecommendations

    model_config = {"populate_by_name": True}