from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.ai.factory import get_embedder
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.search import SearchHistory
from app.models.user import User
from app.schemas.search import (
    HybridSearchFilters,
    HybridSearchRequest,
    HybridSearchResponse,
    HybridSearchResultItem,
    SearchHistoryItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from app.services.ranking import hybrid_search
from app.services.search import semantic_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=HybridSearchResponse)
def search_hybrid(
    payload: HybridSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    The main search endpoint (spec section 7): parses dates, a named
    person, and a detected-object class out of free text (each a hard
    filter, applied in that order), then ranks whatever text is left over
    by vector similarity — combined per the weighted formula in spec
    section 12. See app/services/ranking.py for exactly how the four
    signals are combined and extracted.
    """
    parsed, entities, hits = hybrid_search(
        db=db,
        user_id=current_user.id,
        raw_query=payload.query,
        embedder=get_embedder(),
        limit=payload.limit,
        min_similarity=payload.min_similarity,
    )
    return HybridSearchResponse(
        query=payload.query,
        filters=HybridSearchFilters(
            start_date=parsed.start_date,
            end_date=parsed.end_date,
            person_name=entities.person_name,
            object_name=entities.object_name,
            location_name=entities.location_name,
            semantic_query=entities.semantic_query,
        ),
        results=[
            HybridSearchResultItem(
                photo=hit.photo,
                final_score=hit.final_score,
                semantic_score=hit.semantic_score,
                metadata_score=hit.metadata_score,
                object_score=hit.object_score,
                face_score=hit.face_score,
            )
            for hit in hits
        ],
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
def search_semantic(
    payload: SemanticSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Vector-only similarity search (Phase 4). Phase 5's POST /api/search will
    wrap this with date/location/object filters and natural-language
    parsing; for now this is the raw "find photos like this text" endpoint.
    """
    threshold = payload.min_similarity if payload.min_similarity is not None else settings.SIMILARITY_THRESHOLD
    hits = semantic_search(
        db=db,
        user_id=current_user.id,
        query_text=payload.query,
        embedder=get_embedder(),
        limit=payload.limit,
        min_similarity=threshold,
    )
    return SemanticSearchResponse(
        query=payload.query,
        min_similarity=threshold,
        results=[SemanticSearchResultItem(photo=hit.photo, similarity=hit.similarity) for hit in hits],
    )


@router.get("/history", response_model=list[SearchHistoryItem])
def search_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    rows = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(desc(SearchHistory.created_at))
        .limit(limit)
        .all()
    )
    return rows
