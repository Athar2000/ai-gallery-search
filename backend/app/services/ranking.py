"""
Hybrid natural-language search (Phase 5, extended in Phase 7).

Parses the query in stages, each stage cutting its matched phrase out of
the text before the next stage runs, per spec sections 6/7/10:

    "photos with Athar and a car from August 2025"
        1. date:   "August 2025"  -> start/end date filter
        2. person: "Athar"       -> filter to photos containing that named person
        3. object: "car"         -> filter to photos with a detected car
        4. whatever's left       -> semantic (vector) ranking, if anything remains

Each matched stage is a hard filter (spec: "Do NOT use vector search for
simple date filtering" generalizes naturally to "don't burn a vector query
matching an exact name/object YOLO/clustering already gave us for free").
Scoring still follows spec section 12's weighted formula:

    final_score = semantic*0.5 + object*0.2 + metadata*0.2 + face*0.1

renormalized over whichever signals are actually active for a given query
(a photo either passed a given filter or isn't in the result set, so each
active signal contributes 1.0 for every row -- this decides *inclusion*,
not fine-grained intra-result ordering, same as metadata_score before).
Only the semantic component can meaningfully re-rank within a result set;
the others narrow *which* photos qualify.
"""
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedder import ImageEmbedder
from app.ai.factory import get_embedder
from app.core.config import settings
from app.models.ai import ObjectLabel, Person, PhotoEmbedding, PhotoObject, PhotoPerson
from app.models.photo import Photo, PhotoMetadata
from app.models.search import SearchHistory
from app.services.query_parser import ParsedQuery, parse_query, strip_filler_and_connectors


@dataclass
class HybridSearchHit:
    photo: Photo
    final_score: float
    semantic_score: float | None
    metadata_score: float | None
    object_score: float | None
    face_score: float | None


@dataclass
class MatchedEntities:
    person_id: UUID | None
    person_name: str | None
    object_id: int | None
    object_name: str | None
    location_name: str | None
    semantic_query: str | None


def _extract_person_filter(db: Session, user_id: UUID, text: str) -> tuple[UUID | None, str | None, str]:
    """Finds a case-insensitive whole-word match against one of this user's
    *named* people, longest name first (so "Ann" can't shadow "Anna")."""
    people = db.query(Person.id, Person.name).filter(Person.user_id == user_id, Person.name.is_not(None)).all()
    for person_id, name in sorted(people, key=lambda p: -len(p[1])):
        m = re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)
        if m:
            remaining = strip_filler_and_connectors(text[: m.start()] + " " + text[m.end() :])
            return person_id, name, remaining
    return None, None, text


_OBJECT_CATEGORIES = {
    "man": {"person"},
    "men": {"person"},
    "woman": {"person"},
    "women": {"person"},
    "people": {"person"},
    "animal": {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"},
    "animals": {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"},
    "fruit": {"apple", "banana", "orange"},
    "fruits": {"apple", "banana", "orange"},
}


def _extract_object_filter(db: Session, text: str) -> tuple[list[int], str | None, str]:
    """Finds a word in `text` matching a known object class name (the ones
    YOLO can actually detect), with simple singular/plural handling
    ("cars" -> "car")."""
    words = re.findall(r"[a-zA-Z]+", text)
    if not words:
        return [], None, text

    labels = {name.lower(): obj_id for obj_id, name in db.query(ObjectLabel.id, ObjectLabel.name).all()}
    if not labels:
        return [], None, text

    for word in words:
        lower = word.lower()
        candidate = lower if lower in labels else (lower[:-1] if lower.endswith("s") and lower[:-1] in labels else None)
        category_names = _OBJECT_CATEGORIES.get(lower) or _OBJECT_CATEGORIES.get(lower[:-1])
        category_matches = [name for name in category_names or set() if name in labels]
        if category_matches:
            remaining = strip_filler_and_connectors(re.sub(rf"\b{re.escape(word)}\b", " ", text, count=1, flags=re.IGNORECASE))
            return [labels[name] for name in category_matches], lower, remaining
        if candidate:
            remaining = strip_filler_and_connectors(re.sub(rf"\b{re.escape(word)}\b", " ", text, count=1, flags=re.IGNORECASE))
            return [labels[candidate]], candidate, remaining
    return [], None, text


def _extract_location_filter(db: Session, text: str) -> tuple[str | None, str]:
    if re.search(r"\bplaces?\b", text, re.IGNORECASE):
        remaining = strip_filler_and_connectors(re.sub(r"\bplaces?\b", " ", text, count=1, flags=re.IGNORECASE))
        return "Place", remaining
    locations = [name for (name,) in db.query(PhotoMetadata.location_name).filter(PhotoMetadata.location_name.is_not(None)).distinct().all()]
    for name in sorted(locations, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)
        if match:
            remaining = strip_filler_and_connectors(text[: match.start()] + " " + text[match.end() :])
            return name, remaining
    return None, text


def hybrid_search(
    db: Session,
    user_id: UUID,
    raw_query: str,
    embedder: ImageEmbedder | None = None,
    limit: int = 50,
    min_similarity: float | None = None,
) -> tuple[ParsedQuery, MatchedEntities, list[HybridSearchHit]]:
    parsed = parse_query(raw_query)
    date_active = parsed.start_date is not None

    remaining = parsed.semantic_query
    person_id, person_name, remaining = _extract_person_filter(db, user_id, remaining)
    object_ids, object_name, remaining = _extract_object_filter(db, remaining)
    location_name, remaining = _extract_location_filter(db, remaining)
    person_active, object_active = person_id is not None, bool(object_ids)
    location_active = location_name is not None

    semantic_text = remaining.strip()
    semantic_active = bool(semantic_text)

    active_weights: dict[str, float] = {}
    if semantic_active:
        active_weights["semantic"] = settings.RANK_WEIGHT_SEMANTIC
    if date_active:
        active_weights["metadata"] = settings.RANK_WEIGHT_METADATA
    if object_active:
        active_weights["object"] = settings.RANK_WEIGHT_OBJECT
    if location_active:
        active_weights["metadata"] = settings.RANK_WEIGHT_METADATA
    if person_active:
        active_weights["face"] = settings.RANK_WEIGHT_FACE
    weight_sum = sum(active_weights.values()) or 1.0

    conditions = [Photo.user_id == user_id, Photo.is_deleted.is_(False), Photo.processing_status == "ready"]
    if date_active:
        conditions += [PhotoMetadata.capture_date >= parsed.start_date, PhotoMetadata.capture_date <= parsed.end_date]
    if location_active:
        if location_name == "Place":
            conditions.append(
                PhotoMetadata.location_name.is_not(None)
                | (PhotoMetadata.latitude.is_not(None) & PhotoMetadata.longitude.is_not(None))
            )
        else:
            conditions.append(PhotoMetadata.location_name.ilike(f"%{location_name}%"))

    def _apply_entity_joins(stmt):
        if person_active:
            stmt = stmt.join(
                PhotoPerson, (PhotoPerson.photo_id == Photo.id) & (PhotoPerson.person_id == person_id)
            )
        if object_active:
            stmt = stmt.join(
                PhotoObject, (PhotoObject.photo_id == Photo.id) & PhotoObject.object_id.in_(object_ids)
            )
        return stmt

    def _score(semantic_score: float | None) -> float:
        components = {
            "semantic": semantic_score if semantic_active else 0.0,
            "metadata": 1.0 if date_active else 0.0,
            "object": 1.0 if object_active else 0.0,
            "face": 1.0 if person_active else 0.0,
        }
        numerator = sum(components[name] * weight for name, weight in active_weights.items())
        return numerator / weight_sum

    hits: list[HybridSearchHit] = []

    if semantic_active:
        embedder = embedder or get_embedder()
        query_vector = embedder.embed_text(semantic_text)
        threshold = settings.SIMILARITY_THRESHOLD if min_similarity is None else min_similarity
        max_distance = 1 - threshold
        distance_col = PhotoEmbedding.embedding.cosine_distance(query_vector)

        stmt = select(Photo, distance_col.label("distance")).join(
            PhotoMetadata, PhotoMetadata.photo_id == Photo.id, isouter=True
        )
        stmt = _apply_entity_joins(stmt)
        stmt = (
            stmt.join(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
            .where(*conditions, PhotoEmbedding.embedding.is_not(None), distance_col <= max_distance)
            .order_by(distance_col)
            .limit(limit)
        )
        for photo, distance in db.execute(stmt).all():
            semantic_score = 1 - distance
            hits.append(
                HybridSearchHit(
                    photo,
                    _score(semantic_score),
                    semantic_score,
                    1.0 if date_active else None,
                    1.0 if object_active else None,
                    1.0 if person_active else None,
                )
            )
    else:
        order_col = PhotoMetadata.capture_date.desc() if date_active else Photo.created_at.desc()
        stmt = select(Photo).join(PhotoMetadata, PhotoMetadata.photo_id == Photo.id, isouter=True)
        stmt = _apply_entity_joins(stmt)
        stmt = stmt.where(*conditions).order_by(order_col).limit(limit)
        for (photo,) in db.execute(stmt).all():
            hits.append(
                HybridSearchHit(
                    photo,
                    _score(None),
                    None,
                    1.0 if date_active else None,
                    1.0 if object_active else None,
                    1.0 if person_active else None,
                )
            )

    db.add(
        SearchHistory(
            user_id=user_id,
            query_text=raw_query,
            parsed_filters={
                "start_date": parsed.start_date.isoformat() if parsed.start_date else None,
                "end_date": parsed.end_date.isoformat() if parsed.end_date else None,
                "person_name": person_name,
                "object_name": object_name,
                "location_name": location_name,
                "semantic_query": semantic_text or None,
            },
            result_count=len(hits),
        )
    )
    db.commit()

    return parsed, MatchedEntities(
        person_id, person_name, object_ids[0] if len(object_ids) == 1 else None,
        object_name, location_name, semantic_text or None,
    ), hits
