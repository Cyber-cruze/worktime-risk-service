from pydantic import BaseModel, Field
from typing import List, Optional

class Task(BaseModel):
    hours: float = Field(..., description="Часы на задачу")

class Meeting(BaseModel):
    start: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")
    end: str = Field(..., description="ISO формат: YYYY-MM-DDTHH:MM:SS")

class Profile(BaseModel):
    work_hours: dict = Field(
        alias="workHours",
        default_factory=lambda: {"start": "09:00", "end": "18:00"}
    )
    timezone: str = "Europe/Moscow"
    last_updated: str = Field(alias="lastUpdated", description="ISO дата обновления")
    employment: str = "full-time"

    model_config = {"populate_by_name": True}

class HRData(BaseModel):
    official_schedule: str = Field(alias="officialSchedule", default="09:00-18:00")
    on_vacation: bool = Field(alias="onVacation", default=False)

    model_config = {"populate_by_name": True}

class AnalyzeRequest(BaseModel):
    user_id: int = Field(alias="userId")
    profile: Profile
    tasks: List[Task] = []
    meetings: List[Meeting] = []
    hr_data: HRData = Field(alias="hrData", default_factory=HRData)
    conflicts: list = []
    role: str = Field(
        default="EMPLOYEE",
        description="Роль запрашивающего: EMPLOYEE или PROJECT_MANAGER"
    )

    model_config = {"populate_by_name": True}