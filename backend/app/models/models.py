"""
SQLAlchemy models matching the existing Supabase schema exactly.
Do not alter the schema - only read/write to existing columns.
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Integer,
    Float, ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class DoubtStatus(str, enum.Enum):
    open = "open"
    ai_suggested = "ai_suggested"
    pending_faculty = "pending_faculty"
    resolved = "resolved"
    closed = "closed"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Legacy schema compatibility: some deployments require `name` as NOT NULL.
    name = Column(String(120), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("Student", back_populates="user", uselist=False)
    teacher = relationship("Teacher", back_populates="user", uselist=False)
    admin = relationship("Admin", back_populates="user", uselist=False)


class Student(Base):
    __tablename__ = "students"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    # Legacy schema compatibility
    register_number = Column(Text)
    section = Column(String(10))
    roll_number = Column(String(50), unique=True)
    department = Column(String(100))
    semester = Column(Integer)
    phone = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="student")
    doubts = relationship("Doubt", back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    employee_id = Column(String(50), unique=True)
    department = Column(String(100))
    subjects = Column(JSON, default=list)
    phone = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="teacher")
    resolutions = relationship("DoubtResolution", back_populates="teacher")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="admin")


class Doubt(Base):
    __tablename__ = "doubts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    subject = Column(String(200))
    status = Column(SAEnum(DoubtStatus), default=DoubtStatus.open)
    priority = Column(Integer, default=1)
    preferred_teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True)
    ai_accepted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    # embedding column added via pgvector init - not declared here to avoid migration issues

    student = relationship("Student", back_populates="doubts")
    images = relationship("DoubtImage", back_populates="doubt", cascade="all, delete")
    resolution = relationship("DoubtResolution", back_populates="doubt", uselist=False)
    ai_logs = relationship("AIResponseLog", back_populates="doubt")
    similar_matches = relationship("SimilarDoubtMatch", foreign_keys="SimilarDoubtMatch.source_doubt_id", back_populates="source_doubt")


class DoubtImage(Base):
    __tablename__ = "doubt_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doubt_id = Column(UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    storage_path = Column(Text, nullable=False)
    public_url = Column(Text)
    file_name = Column(String(255))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    doubt = relationship("Doubt", back_populates="images")


class DoubtResolution(Base):
    __tablename__ = "doubt_resolutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doubt_id = Column(UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, unique=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=True)
    answer_text = Column(Text, nullable=False)
    is_ai_answer = Column(Boolean, default=False)
    rating = Column(Integer, nullable=True)
    resolved_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    doubt = relationship("Doubt", back_populates="resolution")
    teacher = relationship("Teacher", back_populates="resolutions")
    images = relationship("ResolutionImage", back_populates="resolution", cascade="all, delete")


class ResolutionImage(Base):
    __tablename__ = "resolution_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("doubt_resolutions.id", ondelete="CASCADE"), nullable=False)
    storage_path = Column(Text, nullable=False)
    public_url = Column(Text)
    file_name = Column(String(255))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    resolution = relationship("DoubtResolution", back_populates="images")


class AIResponseLog(Base):
    __tablename__ = "ai_response_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doubt_id = Column(UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    model_used = Column(String(200))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    similarity_score = Column(Float)
    action_taken = Column(String(100))  # auto_resolved, suggested, skipped
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    doubt = relationship("Doubt", back_populates="ai_logs")


class SimilarDoubtMatch(Base):
    __tablename__ = "similar_doubt_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_doubt_id = Column(UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    matched_doubt_id = Column(UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    rank = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    source_doubt = relationship("Doubt", foreign_keys=[source_doubt_id], back_populates="similar_matches")
    matched_doubt = relationship("Doubt", foreign_keys=[matched_doubt_id])


class AIConfig(Base):
    __tablename__ = "ai_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    similarity_threshold = Column(Float, default=0.75)
    auto_resolve_threshold = Column(Float, default=0.90)
    max_suggestions = Column(Integer, default=3)
    embedding_model = Column(String(200), default="nvidia/nv-embedqa-e5-v5")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
