"""
Face detection + clustering pipeline (Phase 6).

Pipeline, per spec section 9: Photo -> Face Detection -> Face Crop -> Face
Embedding -> Clustering -> Person Group.

Clustering strategy: for each newly detected face, find the closest
already-clustered face belonging to the same user (by cosine distance on
FaceEmbedding.embedding). If it's within FACE_CLUSTER_SIMILARITY_THRESHOLD,
assign the new face to that same person; otherwise start a new (unnamed)
Person. This is "incremental nearest-neighbor" clustering, not a batch
algorithm (no DBSCAN/HDBSCAN) — simple, explainable, and works fine at
personal-gallery scale, but it's order-dependent (an early mis-cluster
isn't retroactively fixed) — a batch re-cluster pass would be a reasonable
future improvement rather than something this implementation covers.

Real facial-identity quality entirely depends on FACE_EMBEDDING_BACKEND —
see app/ai/arcface_embedder.py and app/ai/face_embedder_stub.py.
"""
import io
from uuid import UUID

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.face_detector import FaceDetector
from app.ai.face_embedder import FaceEmbedder
from app.core.config import settings
from app.models.ai import Face, FaceEmbedding, Person, PhotoPerson
from app.models.photo import Photo


def process_faces(db: Session, photo: Photo, original_bytes: bytes, detector: FaceDetector, embedder: FaceEmbedder) -> None:
    detected = detector.detect_faces(original_bytes)
    if not detected:
        return

    with Image.open(io.BytesIO(original_bytes)) as img:
        rgb = img.convert("RGB")

        for det in detected:
            crop = rgb.crop((det.x, det.y, det.x + det.width, det.y + det.height))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG")
            crop_bytes = buf.getvalue()

            face = Face(
                photo_id=photo.id,
                bounding_box={"x": det.x, "y": det.y, "width": det.width, "height": det.height},
                confidence=det.confidence,
            )
            db.add(face)
            db.flush()  # need face.id before creating the embedding row

            vector = embedder.embed_face(crop_bytes)
            db.add(FaceEmbedding(face_id=face.id, embedding=vector, model_name=type(embedder).__name__))

            person = _match_or_create_person(db, photo.user_id, vector)
            face.person_id = person.id

            existing_link = db.get(PhotoPerson, (photo.id, person.id))
            if existing_link:
                existing_link.confidence = max(existing_link.confidence, det.confidence)
            else:
                db.add(PhotoPerson(photo_id=photo.id, person_id=person.id, confidence=det.confidence))

            if person.avatar_photo_id is None:
                person.avatar_photo_id = photo.id

    db.commit()


def _match_or_create_person(db: Session, user_id: UUID, vector: list[float]) -> Person:
    max_distance = 1 - settings.FACE_CLUSTER_SIMILARITY_THRESHOLD
    distance_col = FaceEmbedding.embedding.cosine_distance(vector)

    stmt = (
        select(Face.person_id, distance_col.label("distance"))
        .join(FaceEmbedding, FaceEmbedding.face_id == Face.id)
        .join(Photo, Photo.id == Face.photo_id)
        .where(Photo.user_id == user_id, Face.person_id.is_not(None), distance_col <= max_distance)
        .order_by(distance_col)
        .limit(1)
    )
    nearest = db.execute(stmt).first()
    if nearest:
        return db.get(Person, nearest.person_id)

    person = Person(user_id=user_id, name=None)
    db.add(person)
    db.flush()  # need person.id for the caller to link it
    return person
