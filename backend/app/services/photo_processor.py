"""
Orchestrates the (currently synchronous-in-background) part of the pipeline
described in spec section 3: EXIF extraction -> thumbnail -> DB update.

Deliberately takes only a photo_id and opens its own DB session, exactly
like a Celery/RQ task would — so in Phase 3 this function can be wrapped in
`@celery_app.task` with no change to its body, and called via `.delay()`
instead of `BackgroundTasks.add_task()`.
"""
import logging
from datetime import datetime
from uuid import UUID

from app.ai.face_factory import get_face_detector, get_face_embedder
from app.ai.factory import get_embedder
from app.ai.object_factory import get_object_detector
from app.core import database as database_module
from app.models.ai import ObjectLabel, Person, PhotoEmbedding, PhotoObject, PhotoPerson
from app.models.photo import Photo, PhotoMetadata, ProcessingJob
from app.services import storage as storage_module
from app.services.caption_generator import generate_caption_and_tags
from app.services.exif import extract_exif, fallback_capture_date
from app.services.face_processor import process_faces
from app.services.object_processor import process_objects
from app.services.thumbnail import generate_thumbnail

logger = logging.getLogger(__name__)


def _mark_job(db, user_id: UUID, photo_id: UUID, job_type: str, status: str, error: str | None = None) -> None:
    job = ProcessingJob(user_id=user_id, photo_id=photo_id, job_type=job_type, status=status, error_message=error)
    db.add(job)


def process_photo(photo_id: UUID) -> None:
    # Reference the module attribute (not a name bound at import time) so
    # tests can monkeypatch app.core.database.SessionLocal to point at a
    # test database and have this background task pick it up.
    db = database_module.SessionLocal()
    try:
        photo = db.get(Photo, photo_id)
        if photo is None:
            logger.warning("process_photo: photo %s no longer exists", photo_id)
            return

        photo.processing_status = "processing"
        db.commit()

        try:
            original_bytes = storage_module.storage.original_path(photo.file_path).read_bytes()
        except (OSError, ValueError) as exc:
            photo.processing_status = "failed"
            _mark_job(db, photo.user_id, photo.id, "exif", "failed", str(exc))
            db.commit()
            return

        # --- EXIF ---
        try:
            exif_data = extract_exif(original_bytes)
            if exif_data["capture_date"] is None:
                fallback_date, fallback_time, source = fallback_capture_date(photo.created_at or datetime.utcnow())
                exif_data["capture_date"] = fallback_date
                exif_data["capture_time"] = fallback_time
                capture_date_source = source
            else:
                capture_date_source = "exif"

            metadata = db.get(PhotoMetadata, photo.id) or PhotoMetadata(photo_id=photo.id)
            metadata.capture_date = exif_data["capture_date"]
            metadata.capture_time = exif_data["capture_time"]
            metadata.capture_date_source = capture_date_source
            if exif_data["latitude"] is not None:
                metadata.latitude = exif_data["latitude"]
            if exif_data["longitude"] is not None:
                metadata.longitude = exif_data["longitude"]
            metadata.camera_make = exif_data["camera_make"]
            metadata.camera_model = exif_data["camera_model"]
            metadata.orientation = exif_data["orientation"]
            metadata.exif_json = exif_data["exif_json"]
            db.add(metadata)

            if exif_data["width"] and exif_data["height"]:
                photo.width, photo.height = exif_data["width"], exif_data["height"]

            _mark_job(db, photo.user_id, photo.id, "exif", "done")
            db.commit()
        except Exception as exc:  # noqa: BLE001 - a bad photo must not crash the worker
            logger.exception("EXIF extraction failed for photo %s", photo_id)
            _mark_job(db, photo.user_id, photo.id, "exif", "failed", str(exc))
            db.commit()

        # --- Thumbnail ---
        try:
            thumb_bytes = generate_thumbnail(original_bytes)
            relative_thumb_path = storage_module.storage.save_thumbnail(photo.user_id, photo.id, thumb_bytes)
            photo.thumbnail_path = relative_thumb_path
            _mark_job(db, photo.user_id, photo.id, "thumbnail", "done")
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Thumbnail generation failed for photo %s", photo_id)
            photo.processing_status = "failed"
            _mark_job(db, photo.user_id, photo.id, "thumbnail", "failed", str(exc))
            db.commit()
            return

        # --- Embedding (Phase 3) ---
        try:
            embedder = get_embedder()
            vector = embedder.embed_image(original_bytes)
            embedding_row = db.get(PhotoEmbedding, photo.id) or PhotoEmbedding(photo_id=photo.id)
            embedding_row.embedding = vector
            embedding_row.model_name = type(embedder).__name__
            db.add(embedding_row)
            _mark_job(db, photo.user_id, photo.id, "embedding", "done")
            photo.processing_status = "ready"
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Embedding generation failed for photo %s", photo_id)
            photo.processing_status = "failed"
            _mark_job(db, photo.user_id, photo.id, "embedding", "failed", str(exc))
            db.commit()
            return

        # --- Face detection + clustering (Phase 6) ---
        try:
            process_faces(db, photo, original_bytes, get_face_detector(), get_face_embedder())
            _mark_job(db, photo.user_id, photo.id, "face", "done")
            db.commit()
        except Exception as exc:  # noqa: BLE001
            # A failed face pass doesn't roll back the (already-committed)
            # embedding/ready status -- a photo with no detected/matched
            # faces is still a fully valid, searchable photo.
            logger.exception("Face processing failed for photo %s", photo_id)
            _mark_job(db, photo.user_id, photo.id, "face", "failed", str(exc))
            db.commit()

        # --- Object detection (Phase 7) ---
        try:
            process_objects(db, photo, original_bytes, get_object_detector())
            _mark_job(db, photo.user_id, photo.id, "object", "done")
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Object detection failed for photo %s", photo_id)
            _mark_job(db, photo.user_id, photo.id, "object", "failed", str(exc))
            db.commit()

        # --- Caption + tags (Phase 7): rule-based, built from the real
        # object/face detections above -- see caption_generator.py's
        # docstring for why this isn't a full ML captioning model.
        try:
            object_names = [
                name
                for (name,) in db.query(ObjectLabel.name)
                .join(PhotoObject, PhotoObject.object_id == ObjectLabel.id)
                .filter(PhotoObject.photo_id == photo.id)
                .all()
            ]
            person_names = [
                name
                for (name,) in db.query(Person.name)
                .join(PhotoPerson, PhotoPerson.person_id == Person.id)
                .filter(PhotoPerson.photo_id == photo.id, Person.name.is_not(None))
                .all()
            ]
            caption, tags = generate_caption_and_tags(object_names, person_names)
            metadata = db.get(PhotoMetadata, photo.id)
            if metadata:
                metadata.caption = caption
                metadata.tags = tags
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Caption/tag generation failed for photo %s", photo_id)
            _mark_job(db, photo.user_id, photo.id, "caption", "failed", str(exc))
            db.commit()

    finally:
        db.close()
