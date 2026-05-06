from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import (
    Doubt, DoubtStatus, DoubtResolution, ResolutionImage, Teacher
)
from app.schemas.doubts import DoubtListItem, DoubtOut, ResolveDoubtRequest
from app.core.security import require_role
from app.services.storage import upload_image

router = APIRouter(prefix="/faculty", tags=["Faculty"])


def _get_teacher(db: Session, user_id: str) -> Teacher:
    teacher = db.query(Teacher).filter(Teacher.user_id == user_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher profile not found")
    return teacher


@router.get("/doubts", response_model=List[DoubtListItem])
def get_faculty_doubts(
    subject: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("teacher")),
):
    """Get doubts visible to faculty - filtered by subject or status."""
    teacher = _get_teacher(db, current_user["sub"])

    query = db.query(Doubt)

    # Filter by teacher's subjects if available
    if teacher.subjects:
        query = query.filter(Doubt.subject.in_(teacher.subjects))

    if status:
        query = query.filter(Doubt.status == status)
    else:
        # Default: show open and pending doubts
        query = query.filter(
            Doubt.status.in_([DoubtStatus.open, DoubtStatus.pending_faculty, DoubtStatus.ai_suggested])
        )

    doubts = query.order_by(Doubt.priority.desc(), Doubt.created_at.asc()).all()

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


@router.get("/doubts/{doubt_id}", response_model=DoubtOut)
def get_doubt_detail(
    doubt_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("teacher")),
):
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found")
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
    )


@router.post("/doubts/{doubt_id}/resolve")
async def resolve_doubt(
    doubt_id: str,
    answer_text: str = Form(...),
    images: List[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("teacher")),
):
    teacher = _get_teacher(db, current_user["sub"])
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found")
    if doubt.resolution:
        raise HTTPException(status_code=409, detail="Doubt already resolved")

    resolution = DoubtResolution(
        doubt_id=doubt.id,
        teacher_id=teacher.id,
        answer_text=answer_text,
        is_ai_answer=False,
    )
    db.add(resolution)
    db.flush()

    for img_file in images:
        if img_file.filename:
            upload_data = await upload_image(img_file, folder=f"resolutions/{resolution.id}")
            db_image = ResolutionImage(
                resolution_id=resolution.id,
                storage_path=upload_data["storage_path"],
                public_url=upload_data["public_url"],
                file_name=upload_data["file_name"],
                file_size=upload_data["file_size"],
                mime_type=upload_data["mime_type"],
            )
            db.add(db_image)

    doubt.status = DoubtStatus.resolved
    db.commit()

    return {"message": "Doubt resolved successfully", "resolution_id": str(resolution.id)}


@router.get("/stats")
def get_faculty_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("teacher")),
):
    teacher = _get_teacher(db, current_user["sub"])
    total_resolved = db.query(DoubtResolution).filter(DoubtResolution.teacher_id == teacher.id).count()
    return {
        "total_resolved": total_resolved,
        "teacher_name": teacher.full_name,
        "subjects": teacher.subjects,
    }
