from abc import ABC, abstractmethod

FACE_EMBEDDING_DIM = 512  # must match models/ai.py CLIP_EMBEDDING_DIM and the pgvector migration


class FaceEmbedder(ABC):
    dimension: int = FACE_EMBEDDING_DIM

    @abstractmethod
    def embed_face(self, face_crop: bytes) -> list[float]:
        """Returns a `dimension`-length vector for a cropped face image,
        such that the same person's faces land close together in cosine
        distance (this is what makes clustering/person-matching work)."""
