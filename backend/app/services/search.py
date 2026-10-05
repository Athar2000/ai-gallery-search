"""
Vector similarity search (Phase 4).

This is deliberately narrow: given free text, embed it and rank the user's
photos by cosine similarity against their stored image embeddings. It does
NOT parse dates, locations, or object names out of the query — that's
Phase 5's job (hybrid search), which will call into this function for the
"semantic" half of its ranking and combine it with metadata filters.

Result quality depends entirely on which embedder backend is active
(EMBEDDING_BACKEND). With the real CLIP backend, `embed_text` and
`embed_image` share a semantic space, so "beach sunset" finds beach photos.
With the sandbox's DeterministicStubEmbedder, they do NOT share a
meaningful space (see app/ai/stub_embedder.py) — only the plumbing
(ranking, threshold filtering, isolation) is verified here, not result
relevance.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embedder import ImageEmbedder
from app.core.config import settings
from app.models.ai import PhotoEmbedding
from app.models.photo import Photo
from app.models.search import SearchHistory


@dataclass
class SemanticSearchHit:
    photo: Photo
    similarity: float  # cosine similarity, roughly -1..1 (1 = identical direction)


def semantic_search(
    db: Session,
    user_id: uuid.UUID,
    query_text: str,
    embedder: ImageEmbedder,
    limit: int = 50,
    min_similarity: float | None = None,
) -> list[SemanticSearchHit]:
    """
    Returns the user's photos ranked by cosine similarity to `query_text`,
    most similar first, filtered to similarity >= min_similarity (defaults
    to settings.SIMILARITY_THRESHOLD).

    Only photos with processing_status == "ready" and is_deleted == False
    are eligible — a photo with no embedding yet (still processing, or
    processing failed) can't be matched.
    """
    threshold = settings.SIMILARITY_THRESHOLD if min_similarity is None else min_similarity
    # pgvector's cosine_distance = 1 - cosine_similarity, so a *minimum*
    # similarity becomes a *maximum* distance.
    max_distance = 1 - threshold

    query_vector = embedder.embed_text(query_text)

    distance_col = PhotoEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(Photo, distance_col.label("distance"))
        .join(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .where(
            Photo.user_id == user_id,
            Photo.is_deleted.is_(False),
            Photo.processing_status == "ready",
            PhotoEmbedding.embedding.is_not(None),
            distance_col <= max_distance,
        )
        .order_by(distance_col)
        .limit(limit)
    )

    hits = [SemanticSearchHit(photo=photo, similarity=1 - distance) for photo, distance in db.execute(stmt).all()]

    db.add(
        SearchHistory(
            user_id=user_id,
            query_text=query_text,
            parsed_filters={"semantic_query": query_text, "min_similarity": threshold},
            result_count=len(hits),
        )
    )
    db.commit()

    return hits
