import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.photo import Photo, ProcessingJob
from app.models.user import User
from app.schemas.jobs import ProcessingJobOut
from app.services.photo_processor import process_photo

router = APIRouter(tags=["jobs"])


@router.get("/api/jobs", response_model=list[ProcessingJobOut])
def list_jobs(
    status_filter: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 200)
    query = db.query(ProcessingJob).filter(ProcessingJob.user_id == current_user.id)
    if status_filter:
        query = query.filter(ProcessingJob.status == status_filter)
    return query.order_by(ProcessingJob.created_at.desc()).limit(limit).all()


@router.get("/api/jobs/{job_id}", response_model=ProcessingJobOut)
def get_job(job_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id, ProcessingJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/api/photos/{photo_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_photo(
    photo_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retry processing for a photo whose pipeline previously failed (spec
    section 27: "Mark failed jobs and allow retry"). Bumps retry_count on
    the most recent failed job of each type so repeated retries are
    visible, then re-runs the full pipeline exactly like a fresh upload.
    """
    photo = (
        db.query(Photo)
        .filter(Photo.id == photo_id, Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
        .first()
    )
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    failed_jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.photo_id == photo_id, ProcessingJob.status == "failed")
        .all()
    )
    for job in failed_jobs:
        job.retry_count += 1
    photo.processing_status = "pending"
    db.commit()

    background_tasks.add_task(process_photo, photo.id)
    return {"status": "reprocessing", "photo_id": str(photo_id)}
