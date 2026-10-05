import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ai import Person, PhotoPerson
from app.models.photo import Photo
from app.models.user import User
from app.schemas.people import PersonOut, PersonRenameRequest
from app.schemas.photo import PaginatedPhotos, PhotoOut

router = APIRouter(prefix="/api/people", tags=["people"])


def _get_owned_person_or_404(person_id: uuid.UUID, current_user: User, db: Session) -> Person:
    person = db.query(Person).filter(Person.id == person_id, Person.user_id == current_user.id).first()
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


@router.get("", response_model=list[PersonOut])
def list_people(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Person, func.count(PhotoPerson.photo_id).label("photo_count"))
        .outerjoin(PhotoPerson, PhotoPerson.person_id == Person.id)
        .filter(Person.user_id == current_user.id)
        .group_by(Person.id)
        .order_by(func.count(PhotoPerson.photo_id).desc())
        .all()
    )
    return [
        PersonOut(id=person.id, name=person.name, avatar_photo_id=person.avatar_photo_id, photo_count=count)
        for person, count in rows
    ]


@router.get("/photos", response_model=PaginatedPhotos)
def all_people_photos(
    page: int = 1,
    page_size: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every visible photo in this account that contains a detected person."""
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    base = (
        db.query(Photo)
        .join(PhotoPerson, PhotoPerson.photo_id == Photo.id)
        .filter(Photo.user_id == current_user.id, Photo.is_deleted.is_(False), Photo.processing_status == "ready")
        .distinct()
    )
    total = base.count()
    items = base.order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedPhotos(total=total, page=page, page_size=page_size, items=[PhotoOut.model_validate(p) for p in items])


@router.patch("/{person_id}", response_model=PersonOut)
def rename_person(
    person_id: uuid.UUID,
    payload: PersonRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    person = _get_owned_person_or_404(person_id, current_user, db)
    person.name = payload.name
    db.commit()
    photo_count = db.query(PhotoPerson).filter(PhotoPerson.person_id == person.id).count()
    return PersonOut(id=person.id, name=person.name, avatar_photo_id=person.avatar_photo_id, photo_count=photo_count)


@router.get("/{person_id}/photos", response_model=PaginatedPhotos)
def person_photos(
    person_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_person_or_404(person_id, current_user, db)  # 404s before leaking any photo data
    page, page_size = max(page, 1), min(max(page_size, 1), 200)

    base = (
        db.query(Photo)
        .join(PhotoPerson, PhotoPerson.photo_id == Photo.id)
        .filter(PhotoPerson.person_id == person_id, Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
    )
    total = base.count()
    items = base.order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedPhotos(total=total, page=page, page_size=page_size, items=[PhotoOut.model_validate(p) for p in items])
