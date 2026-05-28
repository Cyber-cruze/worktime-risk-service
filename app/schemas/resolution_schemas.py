from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Recommendation(BaseModel):
    action: str
    suggested_start: Optional[datetime] = Field(alias="suggestedStart", default=None)
    suggested_duration_min: Optional[int] = Field(alias="suggestedDurationMin", default=None)
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    affected_user_ids: List[int] = Field(alias="affectedUserIds", default_factory=list)

    model_config = {"populate_by_name": True}

class ResolutionResponse(BaseModel):
    conflict_id: str = Field(alias="conflictId")
    conflict_type: str = Field(alias="conflictType")
    status: str
    recommendations: List[Recommendation]
    explanation: str

    model_config = {"populate_by_name": True}