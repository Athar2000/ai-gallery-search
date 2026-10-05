"""
Object detection pipeline step (Phase 7): run the configured detector,
get-or-create the `objects` label rows (a shared vocabulary across all
users, per the spec's schema -- "car" is the same row for every user, only
the photo_objects link is per-photo), and store one photo_objects row per
detection above the confidence threshold.
"""
from sqlalchemy.orm import Session

from app.ai.object_detector import ObjectDetector
from app.models.ai import ObjectLabel, PhotoObject
from app.models.photo import Photo


def _get_or_create_label(db: Session, name: str) -> ObjectLabel:
    label = db.query(ObjectLabel).filter(ObjectLabel.name == name).first()
    if label:
        return label
    label = ObjectLabel(name=name)
    db.add(label)
    db.flush()  # need label.id for the photo_objects row
    return label


def process_objects(db: Session, photo: Photo, original_bytes: bytes, detector: ObjectDetector) -> None:
    detections = detector.detect_objects(original_bytes)
    if not detections:
        return

    # A single photo can have several detections of the same class (e.g.
    # "4 persons") -- photo_objects has no per-instance bounding box column
    # in the spec's schema, so we keep the highest-confidence detection per
    # distinct class name for that photo.
    best_confidence_by_name: dict[str, float] = {}
    for det in detections:
        best_confidence_by_name[det.name] = max(best_confidence_by_name.get(det.name, 0.0), det.confidence)

    for name, confidence in best_confidence_by_name.items():
        label = _get_or_create_label(db, name)
        existing = db.get(PhotoObject, (photo.id, label.id))
        if existing:
            existing.confidence = max(existing.confidence, confidence)
        else:
            db.add(PhotoObject(photo_id=photo.id, object_id=label.id, confidence=confidence))

    db.commit()
