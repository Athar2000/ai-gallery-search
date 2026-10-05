import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_user_file_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256 hex digest
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # processing_status: pending | processing | ready | failed
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    is_favorite: Mapped[bool] = mapped_column(default=False)
    is_deleted: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PhotoMetadata(Base):
    __tablename__ = "photo_metadata"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True
    )

    capture_date: Mapped[date | None] = mapped_column(Date, index=True)
    capture_time: Mapped[time | None] = mapped_column(Time)
    # Where capture_date came from: exif | file_created | file_modified | unknown
    capture_date_source: Mapped[str] = mapped_column(String(20), default="unknown")

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_name: Mapped[str | None] = mapped_column(String(255), index=True)  # reverse-geocoded, Phase 4+

    camera_make: Mapped[str | None] = mapped_column(String(100))
    camera_model: Mapped[str | None] = mapped_column(String(100))
    orientation: Mapped[int | None] = mapped_column(Integer)

    caption: Mapped[str | None] = mapped_column(Text)  # AI-generated, Phase 7
    tags: Mapped[list | None] = mapped_column(JSON)  # AI-generated tag list, Phase 7

    exif_json: Mapped[dict | None] = mapped_column(JSON)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    photo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), nullable=True)

    job_type: Mapped[str] = mapped_column(String(50))  # exif | thumbnail | embedding | face | object | caption
    # status: queued | running | done | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cover_photo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlbumPhoto(Base):
    __tablename__ = "album_photos"

    album_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("albums.id"), primary_key=True)
    photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
