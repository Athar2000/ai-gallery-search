import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlbumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class AlbumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    cover_photo_id: uuid.UUID | None
    photo_count: int
    created_at: datetime


class AddPhotosToAlbumRequest(BaseModel):
    photo_ids: list[uuid.UUID] = Field(min_length=1)
