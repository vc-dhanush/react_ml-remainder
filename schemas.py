
from pydantic import BaseModel
from typing import Optional

class TaskBase(BaseModel):
    email: str
    title: str
    description: str
    category: str
    priority: str
    recurring: bool
    deadline: str

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    recurring: Optional[bool] = None
    deadline: Optional[str] = None

class Task(TaskBase):
    id: int
    scheduled_reminder: str | None = None
    reminder_sent: bool | None = False
    completed: bool | None = False
    class Config:
        orm_mode = True

class TaskMinimal(BaseModel):
    title: str
    description: str
    category: str
    priority: str
    recurring: bool
    deadline: str

class ParseOut(BaseModel):
    detected_deadline: str | None
    inferred_category: str
    priority_hint: str

class PredOut(BaseModel):
    pred_priority: str
    prob_complete_on_time: float

class RecoOut(BaseModel):
    hour: int
