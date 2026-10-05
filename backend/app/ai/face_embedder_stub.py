"""
Deterministic, dependency-free stand-in for ArcFaceEmbedder — same pattern
and same honesty as app/ai/stub_embedder.py: reduces the face crop to raw
pixel values so near-identical crops land close together in cosine
distance (enough to test clustering/storage plumbing), with zero real
understanding of facial identity. Two different photos of the same actual
person will NOT reliably cluster together with this backend — only real
ArcFace embeddings do that. Swap to FACE_EMBEDDING_BACKEND=arcface before
relying on Phase 6 people-matching quality.
"""
from io import BytesIO

from PIL import Image

from app.ai.face_embedder import FACE_EMBEDDING_DIM, FaceEmbedder
from app.ai.stub_embedder import _l2_normalize

_GRID = 13


class DeterministicFaceStubEmbedder(FaceEmbedder):
    def embed_face(self, face_crop: bytes) -> list[float]:
        with Image.open(BytesIO(face_crop)) as img:
            img = img.convert("RGB").resize((_GRID, _GRID))
            pixels = list(img.getdata())

        flat = [channel / 255.0 for pixel in pixels for channel in pixel]
        flat += [0.0] * (FACE_EMBEDDING_DIM - len(flat))
        return _l2_normalize(flat)
