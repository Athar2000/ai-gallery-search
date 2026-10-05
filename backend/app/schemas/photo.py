import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    width: int | None
    height: int | None
    processing_status: str
    is_favorite: bool
    created_at: datetime


class PhotoMetadataOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    capture_date: date | None
    capture_time: time | None
    capture_date_source: str
    latitude: float | None
    longitude: float | None
    location_name: str | None
    camera_make: str | None
    camera_model: str | None
    caption: str | None
    tags: list | None


class DetectedObjectOut(BaseModel):
    name: str
    confidence: float


class DetectedPersonOut(BaseModel):
    id: uuid.UUID
    name: str | None


class PhotoDetailOut(PhotoOut):
    # Named photo_metadata, not metadata — "metadata" collides with
    # SQLAlchemy's reserved Base.metadata attribute on the ORM object.
    photo_metadata: PhotoMetadataOut | None = None
    objects: list[DetectedObjectOut] = []
    people: list[DetectedPersonOut] = []


class PaginatedPhotos(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PhotoOut]


class UploadResultItem(BaseModel):
    filename: str
    status: str  # accepted | duplicate | rejected
    photo_id: uuid.UUID | None = None
    reason: str | None = None


class UploadResponse(BaseModel):
    results: list[UploadResultItem]
