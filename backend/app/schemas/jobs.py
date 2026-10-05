import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProcessingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    photo_id: uuid.UUID | None
    job_type: str
    status: str
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime
