from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class EmploymentType(str, Enum):
    PART_TIME = "PART_TIME"
    FULL_TIME = "FULL_TIME"
    CONTRACT = "CONTRACT"

class EventType(str, Enum):
    TASK = "TASK"
    MEETING = "MEETING"

class ConflictType(str, Enum):
    OUTSIDE_WORK_HOURS = "OUTSIDE_WORK_HOURS"
    OVERLAPPING_EVENTS = "OVERLAPPING_EVENTS"
    OVERLOAD = "OVERLOAD"
    WORKDAY_EXCEPTION_CONFLICT = "WORKDAY_EXCEPTION_CONFLICT"

class ProfileSchema(BaseModel):
    userId: int
    authId: Optional[int] = None
    name: str
    surname: str
    phoneNumber: Optional[str] = None
    specialization: str
    employmentType: EmploymentType
    timezone: str
    workStart: str  # "HH:MM:SS"
    workEnd: str    # "HH:MM:SS"
    updatedAt: datetime

class TaskSchema(BaseModel):
    id: str
    initiatorId: int
    userIds: List[int]
    externalEventId: Optional[str] = None
    title: str
    description: str
    type: EventType
    provider: Optional[str] = None
    startTime: datetime
    endTime: datetime
    timezone: str
    recurring: bool = False
    createdAt: datetime
    updatedAt: datetime

class ConflictSchema(BaseModel):
    id: str
    userId: int
    eventId: str
    type: ConflictType
    description: str
    conflictDate: Optional[datetime] = None
    severity: int = Field(ge=1, le=5)
    resolved: bool = False
    detectedAt: datetime

class ConflictResolveRequest(BaseModel):
    conflict: ConflictSchema
    profile: ProfileSchema
    tasks: List[TaskSchema] = Field(default_factory=list)

