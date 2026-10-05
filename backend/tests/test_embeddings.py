"""
Phase 3 tests: the embedding step of the indexing pipeline.

Uses the deterministic stub embedder (see app/ai/stub_embedder.py) since
this sandbox cannot load real CLIP weights — these tests validate the
*plumbing* (a processed photo gets a 512-dim vector stored in a real
pgvector column, and pgvector's cosine-distance operator returns a sane
similarity ordering for that vector), not real semantic search quality.
"""
import io

from PIL import Image
from sqlalchemy import select

from app.core import database as database_module
from app.core.config import settings
from app.models.ai import PhotoEmbedding
from app.models.photo import Photo

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _solid_color_jpeg(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (400, 300), color=color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


def test_embedding_backend_is_stub_in_tests():
    assert settings.EMBEDDING_BACKEND == "deterministic_stub", (
        "Tests must run against the dependency-free stub embedder, not real CLIP "
        "(see conftest.py / .env for how EMBEDDING_BACKEND is set)"
    )


def test_upload_creates_a_512_dim_embedding_row():
    token = _register_and_login()
    files = [("files", ("red.jpg", _solid_color_jpeg((220, 30, 30)), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert detail["processing_status"] == "ready"

    db = database_module.SessionLocal()
    try:
        row = db.get(PhotoEmbedding, photo_id)
        assert row is not None
        assert row.embedding is not None
        assert len(row.embedding) == 512
        assert row.model_name == "DeterministicStubEmbedder"
    finally:
        db.close()


def test_cosine_similarity_orders_visually_similar_photos_closer():
    """
    Upload two red-ish photos and one blue photo. A pgvector cosine-distance
    query anchored on one red photo should return the other red photo before
    the blue one -- proving the stored vectors and the similarity query
    actually work together, independent of real CLIP semantics.
    """
    token = _register_and_login()

    def upload(color):
        files = [("files", (f"{color}.jpg", _solid_color_jpeg(color), "image/jpeg"))]
        res = client.post("/api/photos/upload", headers=_auth(token), files=files)
        return res.json()["results"][0]["photo_id"]

    red_a = upload((220, 20, 20))
    red_b = upload((200, 30, 40))
    blue = upload((20, 30, 220))

    db = database_module.SessionLocal()
    try:
        anchor = db.get(PhotoEmbedding, red_a)
        assert anchor is not None and anchor.embedding is not None

        stmt = (
            select(PhotoEmbedding.photo_id, PhotoEmbedding.embedding.cosine_distance(anchor.embedding).label("dist"))
            .where(PhotoEmbedding.photo_id != red_a)
            .order_by("dist")
        )
        ordered = [str(row.photo_id) for row in db.execute(stmt)]
        assert ordered[0] == red_b  # nearer red photo ranks before the blue one
        assert ordered[1] == blue
    finally:
        db.close()


def test_deleted_photo_processing_does_not_crash_worker():
    """
    process_photo() must tolerate a photo row disappearing before the
    background task runs (e.g. deleted immediately after upload) -- it
    should log and return, not raise.
    """
    from app.services.photo_processor import process_photo
    import uuid

    process_photo(uuid.uuid4())  # should not raise
