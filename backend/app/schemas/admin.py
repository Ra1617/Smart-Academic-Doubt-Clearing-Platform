from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str  # student | teacher
    full_name: str
    # Student fields
    roll_number: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[int] = None
    # Teacher fields
    employee_id: Optional[str] = None
    subjects: Optional[List[str]] = []
    phone: Optional[str] = None


class UserListItem(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class AIConfigUpdate(BaseModel):
    similarity_threshold: Optional[float] = None
    auto_resolve_threshold: Optional[float] = None
    max_suggestions: Optional[int] = None
    embedding_model: Optional[str] = None


class AIConfigOut(BaseModel):
    id: UUID
    similarity_threshold: float
    auto_resolve_threshold: float
    max_suggestions: int
    embedding_model: str
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class AILogOut(BaseModel):
    id: UUID
    doubt_id: UUID
    model_used: Optional[str]
    similarity_score: Optional[float]
    action_taken: Optional[str]
    processing_time_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ToggleUserRequest(BaseModel):
    is_active: bool
