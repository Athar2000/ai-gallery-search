import io
import mimetypes
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ai import ObjectLabel, Person, PhotoObject, PhotoPerson
from app.models.photo import Photo, PhotoMetadata
from app.models.user import User
from app.schemas.photo import (
    DetectedObjectOut,
    DetectedPersonOut,
    PaginatedPhotos,
    PhotoDetailOut,
    PhotoMetadataOut,
    PhotoOut,
    UploadResponse,
    UploadResultItem,
)
from app.services import storage as storage_module
from app.services.hashing import sha256_of
from app.services.photo_processor import process_photo

router = APIRouter(prefix="/api/photos", tags=["photos"])

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _extension_for(filename: str, mime_type: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if ext in storage_module.ALLOWED_EXTENSIONS:
        return ext
    guessed = mimetypes.guess_extension(mime_type) or ""
    return guessed.lower()


def _verify_is_real_image(content: bytes) -> bool:
    """Never trust the declared content-type — actually decode the bytes."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_photos(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    location_name: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts one or more files (also used for "upload a folder", since a
    folder input just sends many files at once from the browser). Each file
    is validated, deduplicated by SHA-256 per-user, saved, and queued for
    background processing (EXIF + thumbnail) so this endpoint returns
    immediately instead of blocking on image processing.
    """
    results: list[UploadResultItem] = []

    for upload in files:
        content = await upload.read()

        if len(content) > MAX_UPLOAD_BYTES:
            results.append(
                UploadResultItem(filename=upload.filename or "unknown", status="rejected", reason="File too large")
            )
            continue

        mime_type = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or ""
        if mime_type not in settings.ALLOWED_IMAGE_MIME_TYPES:
            results.append(
                UploadResultItem(
                    filename=upload.filename or "unknown", status="rejected", reason=f"Unsupported type: {mime_type}"
                )
            )
            continue

        if not _verify_is_real_image(content):
            results.append(
                UploadResultItem(
                    filename=upload.filename or "unknown", status="rejected", reason="File is not a valid image"
                )
            )
            continue

        file_hash = sha256_of(content)
        existing = (
            db.query(Photo)
            .filter(Photo.user_id == current_user.id, Photo.file_hash == file_hash, Photo.is_deleted.is_(False))
            .first()
        )
        if existing:
            results.append(
                UploadResultItem(
                    filename=upload.filename or "unknown",
                    status="duplicate",
                    photo_id=existing.id,
                    reason="Already in your library",
                )
            )
            continue

        extension = _extension_for(upload.filename or "", mime_type)
        if extension not in storage_module.ALLOWED_EXTENSIONS:
            results.append(
                UploadResultItem(filename=upload.filename or "unknown", status="rejected", reason="Unknown file extension")
            )
            continue

        relative_path = storage_module.storage.save_original(current_user.id, extension, content)

        photo = Photo(
            id=uuid.uuid4(),
            user_id=current_user.id,
            file_path=relative_path,
            original_filename=upload.filename or "unknown",
            file_hash=file_hash,
            mime_type=mime_type,
            file_size_bytes=len(content),
            processing_status="pending",
        )
        db.add(photo)
        db.commit()
        db.refresh(photo)

        if latitude is not None and longitude is not None:
            db.add(PhotoMetadata(photo_id=photo.id, latitude=latitude, longitude=longitude, location_name=location_name))
            db.commit()

        background_tasks.add_task(process_photo, photo.id)

        results.append(UploadResultItem(filename=upload.filename or "unknown", status="accepted", photo_id=photo.id))

    return UploadResponse(results=results)


@router.get("", response_model=PaginatedPhotos)
def list_photos(
    page: int = 1,
    page_size: int = 50,
    capture_year: int | None = None,
    capture_month: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    base_query = db.query(Photo).filter(Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
    if capture_year is not None or capture_month is not None:
        base_query = base_query.join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        if capture_year is not None:
            base_query = base_query.filter(func.extract("year", PhotoMetadata.capture_date) == capture_year)
        if capture_month is not None:
            base_query = base_query.filter(func.extract("month", PhotoMetadata.capture_date) == capture_month)

    total = base_query.count()
    items = (
        base_query.order_by(Photo.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedPhotos(total=total, page=page, page_size=page_size, items=items)


@router.get("/timeline")
def photos_timeline(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Grouped counts for the Timeline view (spec section 17): year > month
    > count, driven off capture_date so it reflects when photos were
    actually taken, not when they were uploaded."""
    year_col = func.extract("year", PhotoMetadata.capture_date)
    month_col = func.extract("month", PhotoMetadata.capture_date)
    rows = (
        db.query(year_col.label("year"), month_col.label("month"), func.count(Photo.id).label("count"))
        .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .filter(Photo.user_id == current_user.id, Photo.is_deleted.is_(False), PhotoMetadata.capture_date.is_not(None))
        .group_by(year_col, month_col)
        .order_by(year_col.desc(), month_col.desc())
        .all()
    )
    return [{"year": int(r.year), "month": int(r.month), "count": r.count} for r in rows]


def _get_owned_photo_or_404(photo_id: uuid.UUID, current_user: User, db: Session) -> Photo:
    photo = (
        db.query(Photo)
        .filter(Photo.id == photo_id, Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
        .first()
    )
    if not photo:
        # Same 404 whether the photo doesn't exist or belongs to someone else —
        # never reveal that another user's photo ID is valid.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return photo


@router.get("/{photo_id}", response_model=PhotoDetailOut)
def get_photo(photo_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = _get_owned_photo_or_404(photo_id, current_user, db)
    metadata = db.get(PhotoMetadata, photo.id)
    out = PhotoDetailOut.model_validate(photo)
    if metadata:
        out.photo_metadata = PhotoMetadataOut.model_validate(metadata)

    object_rows = (
        db.query(ObjectLabel.name, PhotoObject.confidence)
        .join(PhotoObject, PhotoObject.object_id == ObjectLabel.id)
        .filter(PhotoObject.photo_id == photo.id)
        .all()
    )
    out.objects = [DetectedObjectOut(name=name, confidence=confidence) for name, confidence in object_rows]

    person_rows = (
        db.query(Person.id, Person.name)
        .join(PhotoPerson, PhotoPerson.person_id == Person.id)
        .filter(PhotoPerson.photo_id == photo.id)
        .all()
    )
    out.people = [DetectedPersonOut(id=pid, name=name) for pid, name in person_rows]

    return out


@router.patch("/{photo_id}/favorite", response_model=PhotoOut)
def toggle_favorite(
    photo_id: uuid.UUID,
    is_favorite: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    photo = _get_owned_photo_or_404(photo_id, current_user, db)
    photo.is_favorite = is_favorite
    db.commit()
    db.refresh(photo)
    return photo


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(photo_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = _get_owned_photo_or_404(photo_id, current_user, db)
    # Soft delete: keeps the row (and file) so this can back a "Recently
    # Deleted" / undo flow later. A permanent purge is a separate operation
    # (Settings > "Delete all photos and AI data", spec section 21).
    photo.is_deleted = True
    db.commit()


@router.get("/{photo_id}/thumbnail")
def get_thumbnail(photo_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = _get_owned_photo_or_404(photo_id, current_user, db)
    if not photo.thumbnail_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not ready yet")
    path = storage_module.storage.thumbnail_path(photo.thumbnail_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail file missing")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{photo_id}/original")
def get_original(photo_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    photo = _get_owned_photo_or_404(photo_id, current_user, db)
    path = storage_module.storage.original_path(photo.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original file missing")
    return FileResponse(path, media_type=photo.mime_type, filename=photo.original_filename)
