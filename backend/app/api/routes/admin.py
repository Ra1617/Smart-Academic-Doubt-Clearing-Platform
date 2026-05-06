from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import (
    User, Student, Teacher, Admin, Doubt,
    AIResponseLog, AIConfig, UserRole
)
from app.schemas.admin import (
    CreateUserRequest, UserListItem,
    AIConfigUpdate, AIConfigOut, AILogOut, ToggleUserRequest
)
from app.schemas.doubts import DoubtListItem
from app.core.security import hash_password, require_role

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/users", response_model=UserListItem, status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    role = body.role.lower()
    if role not in ["student", "teacher"]:
        raise HTTPException(status_code=400, detail="Role must be student or teacher")

    user = User(
        name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole(role),
    )
    db.add(user)
    db.flush()

    full_name = body.full_name
    if role == "student":
        profile = Student(
            user_id=user.id,
            full_name=full_name,
            roll_number=body.roll_number,
            department=body.department,
            semester=body.semester,
            phone=body.phone,
        )
    else:
        profile = Teacher(
            user_id=user.id,
            full_name=full_name,
            employee_id=body.employee_id,
            department=body.department,
            subjects=body.subjects or [],
            phone=body.phone,
        )
    db.add(profile)
    db.commit()
    db.refresh(user)

    return UserListItem(
        id=user.id,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        full_name=full_name,
        created_at=user.created_at,
    )


@router.get("/users", response_model=List[UserListItem])
def list_users(
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.order_by(User.created_at.desc()).all()

    result = []
    for u in users:
        full_name = ""
        if u.student:
            full_name = u.student.full_name
        elif u.teacher:
            full_name = u.teacher.full_name
        elif u.admin:
            full_name = u.admin.full_name
        result.append(UserListItem(
            id=u.id,
            email=u.email,
            role=u.role.value,
            is_active=u.is_active,
            full_name=full_name,
            created_at=u.created_at,
        ))
    return result


@router.patch("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    body: ToggleUserRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = body.is_active
    db.commit()
    return {"message": f"User {'activated' if body.is_active else 'deactivated'}"}


@router.get("/doubts", response_model=List[DoubtListItem])
def list_all_doubts(
    status: Optional[str] = None,
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    query = db.query(Doubt)
    if status:
        query = query.filter(Doubt.status == status)
    if subject:
        query = query.filter(Doubt.subject == subject)
    doubts = query.order_by(Doubt.created_at.desc()).all()
    return [
        DoubtListItem(
            id=d.id,
            title=d.title,
            subject=d.subject,
            status=d.status.value,
            priority=d.priority,
            created_at=d.created_at,
            student_name=d.student.full_name if d.student else None,
            image_count=len(d.images),
        )
        for d in doubts
    ]


@router.get("/ai-logs", response_model=List[AILogOut])
def get_ai_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    logs = db.query(AIResponseLog).order_by(AIResponseLog.created_at.desc()).limit(limit).all()
    return logs


@router.get("/ai-config", response_model=AIConfigOut)
def get_ai_config(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
    if not config:
        raise HTTPException(status_code=404, detail="AI config not found")
    return config


@router.put("/ai-config", response_model=AIConfigOut)
def update_ai_config(
    body: AIConfigUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
    if not config:
        config = AIConfig()
        db.add(config)

    if body.similarity_threshold is not None:
        config.similarity_threshold = body.similarity_threshold
    if body.auto_resolve_threshold is not None:
        config.auto_resolve_threshold = body.auto_resolve_threshold
    if body.max_suggestions is not None:
        config.max_suggestions = body.max_suggestions
    if body.embedding_model is not None:
        config.embedding_model = body.embedding_model

    db.commit()
    db.refresh(config)
    return config


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    from app.models.models import DoubtStatus
    return {
        "total_students": db.query(Student).count(),
        "total_teachers": db.query(Teacher).count(),
        "total_doubts": db.query(Doubt).count(),
        "open_doubts": db.query(Doubt).filter(Doubt.status == DoubtStatus.open).count(),
        "resolved_doubts": db.query(Doubt).filter(Doubt.status == DoubtStatus.resolved).count(),
        "ai_suggested": db.query(Doubt).filter(Doubt.status == DoubtStatus.ai_suggested).count(),
        "total_ai_logs": db.query(AIResponseLog).count(),
    }
