from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.db.database import get_db
from app.models.models import User, Student, Teacher, Admin, UserRole
from app.schemas.auth import (
    RegisterStudentRequest, RegisterFacultyRequest,
    LoginRequest, TokenResponse, RefreshRequest
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_token_response(user: User, profile_id: str, full_name: str) -> TokenResponse:
    payload = {"sub": str(user.id), "role": user.role.value, "profile_id": profile_id}
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
        role=user.role.value,
        user_id=str(user.id),
        profile_id=profile_id,
        full_name=full_name,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register_student(body: RegisterStudentRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole.student,
    )
    db.add(user)
    db.flush()

    student = Student(
        user_id=user.id,
        full_name=body.full_name,
        register_number=body.roll_number or f"REG-{uuid.uuid4().hex[:8].upper()}",
        section=(body.department[:10] if body.department else "A"),
        roll_number=body.roll_number,
        department=body.department,
        semester=body.semester,
        phone=body.phone,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    return _build_token_response(user, str(student.id), student.full_name)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Get profile
    profile_id = None
    full_name = ""
    if user.role == UserRole.student and user.student:
        profile_id = str(user.student.id)
        full_name = user.student.full_name or user.name or ""
    elif user.role == UserRole.teacher and user.teacher:
        profile_id = str(user.teacher.id)
        full_name = user.teacher.full_name or user.name or ""
    elif user.role == UserRole.admin and user.admin:
        profile_id = str(user.admin.id)
        full_name = user.admin.full_name or user.name or ""
    else:
        full_name = user.name or ""

    return _build_token_response(user, profile_id or str(user.id), full_name)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token, settings.JWT_REFRESH_SECRET)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    profile_id = payload.get("profile_id", str(user.id))
    full_name = ""
    if user.student:
        full_name = user.student.full_name or user.name or ""
    elif user.teacher:
        full_name = user.teacher.full_name or user.name or ""
    elif user.admin:
        full_name = user.admin.full_name or user.name or ""
    else:
        full_name = user.name or ""

    return _build_token_response(user, profile_id, full_name)
