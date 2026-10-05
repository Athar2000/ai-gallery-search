"""
A deterministic, dependency-free stand-in for OpenCLIPEmbedder.

This exists ONLY to let the indexing pipeline (storage, pgvector columns,
similarity queries) be built and tested end-to-end in an environment that
cannot load real CLIP weights (see clip_embedder.py's docstring for why).

IMPORTANT — this is NOT semantic search. `embed_image` reduces the photo to
a small grid of raw pixel values, so two images with similar colors/layout
end up with nearby vectors, and two images that look nothing alike end up
far apart. That's enough to prove the plumbing (an upload -> a stored
512-dim vector -> a meaningful cosine-similarity ordering) actually works.
It has no idea what a "beach" or a "car" is. `embed_text` hashes words into
a pseudo-random unit vector purely so the same query string always returns
the same vector — it is not in the same semantic space as the image
vectors, so text-to-image search will not return sensible results with
this backend. Swap to OpenCLIPEmbedder (EMBEDDING_BACKEND=clip) before
relying on Phase 4/5 search quality.
"""
import hashlib
import math
from io import BytesIO

from PIL import Image

from app.ai.embedder import EMBEDDING_DIM, ImageEmbedder

_GRID = 13  # 13*13*3 = 507 values; padded to EMBEDDING_DIM (512) with zeros


class DeterministicStubEmbedder(ImageEmbedder):
    def embed_image(self, content: bytes) -> list[float]:
        with Image.open(BytesIO(content)) as img:
            img = img.convert("RGB").resize((_GRID, _GRID))
            pixels = list(img.getdata())

        flat = [channel / 255.0 for pixel in pixels for channel in pixel]
        flat += [0.0] * (EMBEDDING_DIM - len(flat))
        return _l2_normalize(flat)

    def embed_text(self, text: str) -> list[float]:
        # Deterministic pseudo-random vector seeded from the text's hash —
        # reproducible, but semantically meaningless (see module docstring).
        digest = hashlib.sha256(text.strip().lower().encode("utf-8")).digest()
        values: list[float] = []
        seed = digest
        while len(values) < EMBEDDING_DIM:
            seed = hashlib.sha256(seed).digest()
            values.extend((b / 255.0) * 2 - 1 for b in seed)
        return _l2_normalize(values[:EMBEDDING_DIM])


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]
