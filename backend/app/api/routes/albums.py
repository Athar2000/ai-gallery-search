import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.photo import Album, AlbumPhoto, Photo
from app.models.user import User
from app.schemas.albums import AddPhotosToAlbumRequest, AlbumCreate, AlbumOut
from app.schemas.photo import PaginatedPhotos, PhotoOut

router = APIRouter(prefix="/api/albums", tags=["albums"])


def _get_owned_album_or_404(album_id: uuid.UUID, current_user: User, db: Session) -> Album:
    album = db.query(Album).filter(Album.id == album_id, Album.user_id == current_user.id).first()
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    return album


def _to_out(album: Album, photo_count: int) -> AlbumOut:
    return AlbumOut(
        id=album.id,
        name=album.name,
        description=album.description,
        cover_photo_id=album.cover_photo_id,
        photo_count=photo_count,
        created_at=album.created_at,
    )


@router.post("", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
def create_album(payload: AlbumCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    album = Album(user_id=current_user.id, name=payload.name, description=payload.description)
    db.add(album)
    db.commit()
    db.refresh(album)
    return _to_out(album, 0)


@router.get("", response_model=list[AlbumOut])
def list_albums(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Album, func.count(AlbumPhoto.photo_id).label("photo_count"))
        .outerjoin(AlbumPhoto, AlbumPhoto.album_id == Album.id)
        .filter(Album.user_id == current_user.id)
        .group_by(Album.id)
        .order_by(Album.created_at.desc())
        .all()
    )
    return [_to_out(album, count) for album, count in rows]


@router.post("/{album_id}/photos", response_model=AlbumOut)
def add_photos_to_album(
    album_id: uuid.UUID,
    payload: AddPhotosToAlbumRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    album = _get_owned_album_or_404(album_id, current_user, db)

    owned_photo_ids = {
        p.id
        for p in db.query(Photo.id).filter(Photo.id.in_(payload.photo_ids), Photo.user_id == current_user.id).all()
    }
    if not owned_photo_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No matching photos found")

    for photo_id in owned_photo_ids:
        if not db.get(AlbumPhoto, (album_id, photo_id)):
            db.add(AlbumPhoto(album_id=album_id, photo_id=photo_id))

    if album.cover_photo_id is None:
        album.cover_photo_id = next(iter(owned_photo_ids))

    db.commit()
    photo_count = db.query(AlbumPhoto).filter(AlbumPhoto.album_id == album_id).count()
    return _to_out(album, photo_count)


@router.delete("/{album_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo_from_album(
    album_id: uuid.UUID,
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_album_or_404(album_id, current_user, db)
    link = db.get(AlbumPhoto, (album_id, photo_id))
    if link:
        db.delete(link)
        db.commit()


@router.get("/{album_id}/photos", response_model=PaginatedPhotos)
def album_photos(
    album_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_owned_album_or_404(album_id, current_user, db)
    page, page_size = max(page, 1), min(max(page_size, 1), 200)

    base = (
        db.query(Photo)
        .join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id)
        .filter(AlbumPhoto.album_id == album_id, Photo.user_id == current_user.id, Photo.is_deleted.is_(False))
    )
    total = base.count()
    items = base.order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedPhotos(total=total, page=page, page_size=page_size, items=[PhotoOut.model_validate(p) for p in items])


@router.delete("/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_album(album_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    album = _get_owned_album_or_404(album_id, current_user, db)
    db.query(AlbumPhoto).filter(AlbumPhoto.album_id == album_id).delete()
    db.delete(album)
    db.commit()
