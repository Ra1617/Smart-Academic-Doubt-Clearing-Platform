from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class DoubtImageOut(BaseModel):
    id: UUID
    storage_path: str
    public_url: Optional[str]
    file_name: Optional[str]

    class Config:
        from_attributes = True


class ResolutionImageOut(BaseModel):
    id: UUID
    public_url: Optional[str]
    file_name: Optional[str]

    class Config:
        from_attributes = True


class DoubtResolutionOut(BaseModel):
    id: UUID
    answer_text: str
    is_ai_answer: bool
    rating: Optional[int]
    resolved_at: datetime
    images: List[ResolutionImageOut] = []

    class Config:
        from_attributes = True


class AISuggestion(BaseModel):
    matched_doubt_id: UUID
    matched_title: str
    matched_description: str
    similarity_score: float
    answer_text: Optional[str]
    rank: int


class DoubtCreate(BaseModel):
    title: str
    description: str
    subject: Optional[str] = None
    priority: Optional[int] = 1
    preferred_teacher_id: Optional[UUID] = None


class DoubtOut(BaseModel):
    id: UUID
    title: str
    description: str
    subject: Optional[str]
    status: str
    priority: int
    ai_accepted: bool
    created_at: datetime
    updated_at: datetime
    images: List[DoubtImageOut] = []
    resolution: Optional[DoubtResolutionOut] = None
    ai_suggestions: Optional[List[AISuggestion]] = None

    class Config:
        from_attributes = True


class DoubtListItem(BaseModel):
    id: UUID
    title: str
    subject: Optional[str]
    status: str
    priority: int
    created_at: datetime
    student_name: Optional[str] = None
    image_count: int = 0

    class Config:
        from_attributes = True


class ResolveDoubtRequest(BaseModel):
    answer_text: str


class AcceptAIRequest(BaseModel):
    matched_doubt_id: UUID
    similarity_score: float


class RateResolutionRequest(BaseModel):
    rating: int  # 1–5
