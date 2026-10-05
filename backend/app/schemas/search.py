import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.photo import PhotoOut


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=50, ge=1, le=200)
    min_similarity: float | None = Field(default=None, ge=-1, le=1)


class SemanticSearchResultItem(BaseModel):
    photo: PhotoOut
    similarity: float


class SemanticSearchResponse(BaseModel):
    query: str
    min_similarity: float
    results: list[SemanticSearchResultItem]


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=50, ge=1, le=200)
    min_similarity: float | None = Field(default=None, ge=-1, le=1)


class HybridSearchFilters(BaseModel):
    start_date: date | None
    end_date: date | None
    person_name: str | None
    object_name: str | None
    location_name: str | None
    semantic_query: str | None


class HybridSearchResultItem(BaseModel):
    photo: PhotoOut
    final_score: float
    semantic_score: float | None
    metadata_score: float | None
    object_score: float | None
    face_score: float | None


class HybridSearchResponse(BaseModel):
    query: str
    filters: HybridSearchFilters
    results: list[HybridSearchResultItem]


class SearchHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query_text: str
    parsed_filters: dict | None
    result_count: int | None
    created_at: datetime
