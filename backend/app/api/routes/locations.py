import uuid

from sqlalchemy import Numeric, Text, cast, func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.photo import Photo, PhotoMetadata
from app.models.user import User
from app.schemas.locations import LocationCluster
from app.schemas.photo import PaginatedPhotos, PhotoOut

router = APIRouter(prefix="/api/locations", tags=["locations"])

# ~1.1km precision at the equator -- close enough to group "the same trip"
# without real reverse geocoding (see schemas/locations.py for why that's
# not available here).
_ROUND_DECIMALS = 2


@router.get("", response_model=list[LocationCluster])
def list_locations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Postgres's two-argument round() only accepts `numeric`, not the
    # `double precision` that latitude/longitude are stored as -- found by
    # actually running this query (UndefinedFunction error), not assumed.
    lat_numeric = cast(PhotoMetadata.latitude, Numeric)
    lon_numeric = cast(PhotoMetadata.longitude, Numeric)
    lat_rounded = func.round(lat_numeric, _ROUND_DECIMALS)
    lon_rounded = func.round(lon_numeric, _ROUND_DECIMALS)

    rows = (
        db.query(
            lat_rounded.label("lat"),
            lon_rounded.label("lon"),
            func.count(Photo.id).label("photo_count"),
            func.max(PhotoMetadata.location_name).label("location_name"),
            # Postgres has no min()/max() aggregate for uuid either -- cast
            # to text for the aggregate, then back to UUID in Python.
            func.min(cast(Photo.id, Text)).label("sample_photo_id"),
        )
        .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .filter(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            PhotoMetadata.latitude.is_not(None),
            PhotoMetadata.longitude.is_not(None),
        )
        .group_by(lat_rounded, lon_rounded)
        .order_by(func.count(Photo.id).desc())
        .all()
    )

    return [
        LocationCluster(
            latitude=row.lat, longitude=row.lon, location_name=row.location_name,
            photo_count=row.photo_count, sample_photo_id=uuid.UUID(row.sample_photo_id),
        )
        for row in rows
    ]


@router.get("/photos", response_model=PaginatedPhotos)
def all_location_photos(
    page: int = 1,
    page_size: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return every visible photo with GPS coordinates or a place name."""
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    base = (
        db.query(Photo)
        .join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id)
        .filter(
            Photo.user_id == current_user.id,
            Photo.is_deleted.is_(False),
            Photo.processing_status == "ready",
            (PhotoMetadata.latitude.is_not(None) & PhotoMetadata.longitude.is_not(None))
            | PhotoMetadata.location_name.is_not(None),
        )
    )
    total = base.count()
    items = base.order_by(Photo.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedPhotos(total=total, page=page, page_size=page_size, items=[PhotoOut.model_validate(p) for p in items])
