import uuid

from pydantic import BaseModel, ConfigDict, Field


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    avatar_photo_id: uuid.UUID | None
    photo_count: int


class PersonRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
