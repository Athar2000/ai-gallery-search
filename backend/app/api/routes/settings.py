from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ai import Face, FaceEmbedding, Person, PhotoEmbedding, PhotoObject, PhotoPerson
from app.models.photo import Album, AlbumPhoto, Photo, PhotoMetadata, ProcessingJob
from app.models.search import SearchHistory
from app.models.user import User
from app.services import storage as storage_module

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.post("/delete-all-data", status_code=200)
def delete_all_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    "Delete all photos and AI data" (spec section 21) -- a full wipe of
    this user's photos, derived AI data (embeddings, faces, detected
    objects), people, albums, and search history. The account itself is
    kept so they can start fresh, not deleted.

    Order matters here: child rows (metadata, embeddings, faces, links)
    must go before their parent `photos` rows to satisfy foreign keys, and
    original/thumbnail files are removed from disk only after every DB
    reference to them is gone.
    """
    photo_ids = [p.id for p in db.query(Photo.id).filter(Photo.user_id == current_user.id).all()]
    face_ids = [f.id for f in db.query(Face.id).filter(Face.photo_id.in_(photo_ids)).all()] if photo_ids else []

    if face_ids:
        db.query(FaceEmbedding).filter(FaceEmbedding.face_id.in_(face_ids)).delete(synchronize_session=False)
    if photo_ids:
        db.query(Face).filter(Face.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(PhotoEmbedding).filter(PhotoEmbedding.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(PhotoObject).filter(PhotoObject.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(PhotoPerson).filter(PhotoPerson.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(PhotoMetadata).filter(PhotoMetadata.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(ProcessingJob).filter(ProcessingJob.photo_id.in_(photo_ids)).delete(synchronize_session=False)
        db.query(AlbumPhoto).filter(AlbumPhoto.photo_id.in_(photo_ids)).delete(synchronize_session=False)

    db.query(Person).filter(Person.user_id == current_user.id).delete(synchronize_session=False)
    db.query(Album).filter(Album.user_id == current_user.id).delete(synchronize_session=False)
    db.query(SearchHistory).filter(SearchHistory.user_id == current_user.id).delete(synchronize_session=False)

    # Remove files from disk before dropping the Photo rows that name them.
    photos = db.query(Photo).filter(Photo.user_id == current_user.id).all()
    for photo in photos:
        storage_module.storage.delete_original(photo.file_path)
        if photo.thumbnail_path:
            storage_module.storage.delete_thumbnail(photo.thumbnail_path)

    deleted_count = db.query(Photo).filter(Photo.user_id == current_user.id).delete(synchronize_session=False)

    db.commit()
    return {"deleted_photos": deleted_count}
