from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


class RegisterStudentRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    roll_number: Optional[str] = None
    department: Optional[str] = None
    semester: Optional[int] = None
    phone: Optional[str] = None


class RegisterFacultyRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    subjects: Optional[list[str]] = []
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    profile_id: str
    full_name: str


class RefreshRequest(BaseModel):
    refresh_token: str
