from functools import lru_cache

from app.ai.embedder import ImageEmbedder
from app.core.config import settings


@lru_cache(maxsize=1)
def get_embedder() -> ImageEmbedder:
    if settings.EMBEDDING_BACKEND == "clip":
        from app.ai.clip_embedder import get_clip_embedder

        return get_clip_embedder()
    if settings.EMBEDDING_BACKEND == "deterministic_stub":
        from app.ai.stub_embedder import DeterministicStubEmbedder

        return DeterministicStubEmbedder()
    raise ValueError(f"Unknown EMBEDDING_BACKEND: {settings.EMBEDDING_BACKEND!r}")
