from pydantic import BaseModel, Field
from typing import List, Optional

class Task(BaseModel):
    hours: float = Field(..., description="Часы на задачу")

class Meeting(BaseModel):
    startTime: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")
    endTime: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")

class Profile(BaseModel):
    workHours: dict = Field(default_factory=lambda: {"start": "09:00", "end": "18:00"})
    timezone: str = "Europe/Moscow"
    lastUpdated: str = Field(..., description="ISO дата обновления")
    employment: str = "full-time"

class HRData(BaseModel):
    officialSchedule: str = "09:00-18:00"
    onVacation: bool = False

class AnalyzeRequest(BaseModel):
    userId: int
    profile: Profile
    tasks: List[Task] = []
    meetings: List[Meeting] = []
    hrData: HRData = HRData()
    conflicts: list = []