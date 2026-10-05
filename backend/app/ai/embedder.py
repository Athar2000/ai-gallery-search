"""
Every image/text embedding backend implements this interface. Swapping
`get_embedder()`'s return value is the only thing that changes between
"real CLIP" and "sandbox test double" — nothing in photo_processor.py or
any route needs to know which one is active.
"""
from abc import ABC, abstractmethod

EMBEDDING_DIM = 512  # must match models/ai.py CLIP_EMBEDDING_DIM and the pgvector migration


class ImageEmbedder(ABC):
    dimension: int = EMBEDDING_DIM

    @abstractmethod
    def embed_image(self, content: bytes) -> list[float]:
        """Returns a `dimension`-length vector for the given image bytes."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Returns a `dimension`-length vector in the *same space* as
        embed_image, so a text query can be compared against image vectors
        with cosine similarity (this is what makes "beach sunset" -> photos
        work in Phase 4/5)."""
