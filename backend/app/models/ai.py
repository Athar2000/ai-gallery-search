"""
AI pipeline tables.

`photo_embeddings.embedding` / `face_embeddings.embedding` are now real
pgvector columns (Phase 3), not the JSON placeholder used in Phase 1/2.
512 dimensions matches CLIP ViT-B/32's output size — if a different CLIP
variant is used later, this dimension (and the migration below) must change
together with `app/ai/clip_embedder.py`.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base

CLIP_EMBEDDING_DIM = 512


class PhotoEmbedding(Base):
    __tablename__ = "photo_embeddings"

    photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(CLIP_EMBEDDING_DIM), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), default="ViT-B-32/openai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Face(Base):
    __tablename__ = "faces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), index=True)
    bounding_box: Mapped[dict] = mapped_column(JSON)  # {x, y, width, height}
    confidence: Mapped[float] = mapped_column(Float)
    # Added in Phase 6: the spec's original schema only linked photos to
    # people at the photo level (photo_people), which can't tell which
    # specific face in a multi-person photo belongs to which person. This
    # column is what clustering actually assigns to; photo_people stays as
    # a derived, deduplicated "this photo contains person X" index for
    # search, populated from this.
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("people.id"), index=True)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    face_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("faces.id"), primary_key=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(CLIP_EMBEDDING_DIM), nullable=True)
    model_name: Mapped[str] = mapped_column(String(100), default="arcface")


class Person(Base):
    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255))  # null until user labels the cluster
    avatar_photo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"))


class PhotoPerson(Base):
    __tablename__ = "photo_people"

    photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("people.id"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float)


class ObjectLabel(Base):
    """A distinct detectable object class, e.g. 'car', 'dog'."""

    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)


class PhotoObject(Base):
    __tablename__ = "photo_objects"

    photo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("photos.id"), primary_key=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"), primary_key=True)
    confidence: Mapped[float] = mapped_column(Float)
