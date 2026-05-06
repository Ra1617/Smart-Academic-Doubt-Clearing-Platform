import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import (
    Doubt, DoubtImage, DoubtStatus, DoubtResolution,
    Student, SimilarDoubtMatch
)
from app.schemas.doubts import (
    DoubtCreate, DoubtOut, DoubtListItem,
    AcceptAIRequest, RateResolutionRequest
)
from app.core.security import get_current_user, require_role
from app.services.storage import upload_image
from app.ai.engine import process_doubt_ai

router = APIRouter(prefix="/doubts", tags=["Doubts"])


def _get_student(db: Session, user_id: str) -> Student:
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student


@router.post("/", response_model=DoubtOut, status_code=201)
async def create_doubt(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    subject: Optional[str] = Form(None),
    priority: int = Form(1),
    preferred_teacher_id: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("student")),
):
    student = _get_student(db, current_user["sub"])

    doubt = Doubt(
        student_id=student.id,
        title=title,
        description=description,
        subject=subject,
        priority=priority,
        status=DoubtStatus.open,
        preferred_teacher_id=uuid.UUID(preferred_teacher_id) if preferred_teacher_id else None,
    )
    db.add(doubt)
    db.flush()

    # Upload images
    for img_file in images:
        if img_file.filename:
            upload_data = await upload_image(img_file, folder=f"doubts/{doubt.id}")
            db_image = DoubtImage(
                doubt_id=doubt.id,
                storage_path=upload_data["storage_path"],
                public_url=upload_data["public_url"],
                file_name=upload_data["file_name"],
                file_size=upload_data["file_size"],
                mime_type=upload_data["mime_type"],
            )
            db.add(db_image)

    db.commit()
    db.refresh(doubt)

    # Run AI in background
    background_tasks.add_task(process_doubt_ai, db, doubt)

    return _build_doubt_out(doubt, db)


@router.get("/my", response_model=List[DoubtListItem])
def get_my_doubts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("student")),
):
    student = _get_student(db, current_user["sub"])
    doubts = db.query(Doubt).filter(Doubt.student_id == student.id)\
        .order_by(Doubt.created_at.desc()).all()
    return [
        DoubtListItem(
            id=d.id,
            title=d.title,
            subject=d.subject,
            status=d.status.value,
            priority=d.priority,
            created_at=d.created_at,
            image_count=len(d.images),
        )
        for d in doubts
    ]


@router.get("/{doubt_id}", response_model=DoubtOut)
def get_doubt(
    doubt_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found")

    # Students can only see their own doubts
    if current_user["role"] == "student":
        student = _get_student(db, current_user["sub"])
        if str(doubt.student_id) != str(student.id):
            raise HTTPException(status_code=403, detail="Access denied")

    return _build_doubt_out(doubt, db)


@router.post("/{doubt_id}/accept-ai")
def accept_ai_suggestion(
    doubt_id: str,
    body: AcceptAIRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("student")),
):
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found")

    student = _get_student(db, current_user["sub"])
    if str(doubt.student_id) != str(student.id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch the matched doubt's resolution
    matched = db.query(Doubt).filter(Doubt.id == body.matched_doubt_id).first()
    if not matched or not matched.resolution:
        raise HTTPException(status_code=404, detail="Matched doubt or resolution not found")

    # Create resolution from AI
    resolution = DoubtResolution(
        doubt_id=doubt.id,
        answer_text=matched.resolution.answer_text,
        is_ai_answer=True,
    )
    db.add(resolution)
    doubt.status = DoubtStatus.resolved
    doubt.ai_accepted = True
    db.commit()

    return {"message": "AI answer accepted. Doubt resolved."}


@router.post("/{doubt_id}/rate")
def rate_resolution(
    doubt_id: str,
    body: RateResolutionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("student")),
):
    if not 1 <= body.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1–5")
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt or not doubt.resolution:
        raise HTTPException(status_code=404, detail="Doubt or resolution not found")
    doubt.resolution.rating = body.rating
    db.commit()
    return {"message": "Rating submitted"}


def _build_doubt_out(doubt: Doubt, db: Session) -> DoubtOut:
    """Build DoubtOut with AI suggestions loaded from DB."""
    suggestions = None
    if doubt.status in [DoubtStatus.ai_suggested]:
        matches = db.query(SimilarDoubtMatch)\
            .filter(SimilarDoubtMatch.source_doubt_id == doubt.id)\
            .order_by(SimilarDoubtMatch.rank).all()

        suggestions = []
        for m in matches:
            matched_d = db.query(Doubt).filter(Doubt.id == m.matched_doubt_id).first()
            if matched_d:
                suggestions.append({
                    "matched_doubt_id": m.matched_doubt_id,
                    "matched_title": matched_d.title,
                    "matched_description": matched_d.description,
                    "similarity_score": m.similarity_score,
                    "answer_text": matched_d.resolution.answer_text if matched_d.resolution else None,
                    "rank": m.rank,
                })

    return DoubtOut(
        id=doubt.id,
        title=doubt.title,
        description=doubt.description,
        subject=doubt.subject,
        status=doubt.status.value,
        priority=doubt.priority,
        ai_accepted=doubt.ai_accepted,
        created_at=doubt.created_at,
        updated_at=doubt.updated_at,
        images=doubt.images,
        resolution=doubt.resolution,
        ai_suggestions=suggestions,
    )
