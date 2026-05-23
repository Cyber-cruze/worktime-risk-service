from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Recommendation(BaseModel):
    action: str
    suggested_start: Optional[datetime] = None
    suggested_duration_min: Optional[int] = None
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    affected_user_ids: List[int] = Field(default_factory=list)

class ResolutionResponse(BaseModel):
    conflict_id: str
    conflict_type: str
    status: str
    recommendations: List[Recommendation]
    explanation: str