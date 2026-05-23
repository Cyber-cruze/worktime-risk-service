from pydantic import BaseModel, Field
from typing import List, Optional

class Task(BaseModel):
    hours: float = Field(..., description="Часы на задачу")

class Meeting(BaseModel):
    start: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")
    end: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")

class Profile(BaseModel):
    work_hours: dict = Field(default_factory=lambda: {"start": "09:00", "end": "18:00"})
    timezone: str = "Europe/Moscow"
    last_updated: str = Field(..., description="ISO дата обновления")
    employment: str = "full-time"

class HRData(BaseModel):
    official_schedule: str = "09:00-18:00"
    on_vacation: bool = False

class AnalyzeRequest(BaseModel):
    user_id: str
    profile: Profile
    tasks: List[Task] = []
    meetings: List[Meeting] = []
    hr_data: HRData = HRData()
    conflicts: list = []