from pydantic import BaseModel
from typing import List
from .conflict_schemas import ConflictResolveRequest
from .resolution_schemas import ResolutionResponse


class ConflictResolutionResult(BaseModel):
    conflict_id: str
    conflict_type: str
    status: str
    recommendations: List = []
    explanation: str


class ConflictResolveBatchRequest(BaseModel):
    conflicts: List[ConflictResolveRequest]


class ConflictResolveBatchResponse(BaseModel):
    results: List[ConflictResolutionResult]
    total_processed: int
    success_count: int
    error_count: int