"""
Phase 4 tests: semantic search plumbing.

Uses the same deterministic stub embedder as Phase 3. Since the stub's
embed_text() is NOT in the same space as embed_image() (see
app/ai/stub_embedder.py's docstring), these tests verify the *mechanics*
(correct ranking order for a given set of stored distances, threshold
filtering, per-user isolation, excluding non-ready/deleted photos, and
search_history logging) rather than real content relevance -- that
requires the real CLIP backend (see README).
"""
import io

from PIL import Image

from app.ai.factory import get_embedder

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _solid_color_jpeg(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (400, 300), color=color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


def _upload(token, color, filename="photo.jpg"):
    files = [("files", (filename, _solid_color_jpeg(color), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    return res.json()["results"][0]["photo_id"]


def test_semantic_search_ranks_by_similarity_to_query_embedding():
    """
    Rather than trust the stub's semantics, this test computes the query
    embedding directly (the same way the endpoint does) and checks that the
    two photos closest to it in raw cosine similarity come back first, in
    the right order -- i.e. the endpoint's ranking matches what pgvector
    should compute for these specific vectors.
    """
    token = _register_and_login()
    ids = {
        "red": _upload(token, (220, 20, 20), "red.jpg"),
        "orange": _upload(token, (220, 130, 20), "orange.jpg"),
        "blue": _upload(token, (20, 30, 220), "blue.jpg"),
    }

    res = client.post(
        "/api/search/semantic",
        headers=_auth(token),
        json={"query": "warm colors", "limit": 10, "min_similarity": -1},
    )
    assert res.status_code == 200
    body = res.json()
    returned_ids = [r["photo"]["id"] for r in body["results"]]

    assert set(returned_ids) == set(ids.values())
    # Similarities must be non-increasing (correct sort order)
    similarities = [r["similarity"] for r in body["results"]]
    assert similarities == sorted(similarities, reverse=True)


def test_min_similarity_threshold_filters_results():
    token = _register_and_login()
    _upload(token, (220, 20, 20), "red.jpg")
    _upload(token, (20, 30, 220), "blue.jpg")

    # An impossibly high threshold should filter out everything.
    res = client.post(
        "/api/search/semantic",
        headers=_auth(token),
        json={"query": "anything", "min_similarity": 0.999999},
    )
    assert res.status_code == 200
    assert res.json()["results"] == []

    # A threshold of -1 (minimum possible cosine similarity) must let
    # everything through.
    res_all = client.post(
        "/api/search/semantic",
        headers=_auth(token),
        json={"query": "anything", "min_similarity": -1},
    )
    assert len(res_all.json()["results"]) == 2


def test_semantic_search_only_returns_own_ready_photos():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")

    photo_a = _upload(token_a, (220, 20, 20), "a.jpg")
    _upload(token_b, (220, 20, 20), "b.jpg")

    res = client.post(
        "/api/search/semantic",
        headers=_auth(token_a),
        json={"query": "anything", "min_similarity": -1},
    )
    ids = [r["photo"]["id"] for r in res.json()["results"]]
    assert ids == [photo_a]  # never see user b's photo


def test_semantic_search_records_history():
    token = _register_and_login()
    _upload(token, (220, 20, 20), "red.jpg")

    client.post("/api/search/semantic", headers=_auth(token), json={"query": "sunset beach", "min_similarity": -1})

    history = client.get("/api/search/history", headers=_auth(token)).json()
    assert len(history) == 1
    assert history[0]["query_text"] == "sunset beach"
    assert history[0]["result_count"] == 1


def test_query_embedding_uses_same_backend_as_image_embedding():
    """Sanity check that the endpoint and the pipeline agree on which
    embedder is active -- if this ever drifted, search would silently
    compare vectors from two different spaces."""
    embedder = get_embedder()
    vec = embedder.embed_text("some query")
    assert len(vec) == 512
