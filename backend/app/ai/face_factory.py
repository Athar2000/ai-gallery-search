from functools import lru_cache

from app.ai.face_detector import FaceDetector
from app.ai.face_embedder import FaceEmbedder
from app.core.config import settings


@lru_cache(maxsize=1)
def get_face_detector() -> FaceDetector:
    if settings.FACE_DETECTION_BACKEND == "haarcascade":
        from app.ai.haar_face_detector import get_haar_detector

        return get_haar_detector()
    raise ValueError(f"Unknown FACE_DETECTION_BACKEND: {settings.FACE_DETECTION_BACKEND!r}")


@lru_cache(maxsize=1)
def get_face_embedder() -> FaceEmbedder:
    if settings.FACE_EMBEDDING_BACKEND == "arcface":
        from app.ai.arcface_embedder import get_arcface_embedder

        return get_arcface_embedder()
    if settings.FACE_EMBEDDING_BACKEND == "deterministic_stub":
        from app.ai.face_embedder_stub import DeterministicFaceStubEmbedder

        return DeterministicFaceStubEmbedder()
    raise ValueError(f"Unknown FACE_EMBEDDING_BACKEND: {settings.FACE_EMBEDDING_BACKEND!r}")
