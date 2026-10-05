from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.photo import Album, Photo
from app.models.ai import Person
from app.models.user import User

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = db.query(Photo).filter(Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
    return {
        "total_photos": base.count(),
        "photos_ready": base.filter(Photo.processing_status == "ready").count(),
        "photos_processing": base.filter(Photo.processing_status.in_(["pending", "processing"])).count(),
        "total_albums": db.query(Album).filter(Album.user_id == current_user.id).count(),
        "total_people": db.query(Person).filter(Person.user_id == current_user.id).count(),
    }
