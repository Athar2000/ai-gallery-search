"""
Phase 5 integration tests: POST /api/search (hybrid NL search).

Uploads photos with real injected EXIF dates (via piexif, same pattern as
test_photos.py/test_embeddings.py) so date filtering can be verified
against real capture_date values, not just upload time.
"""
import io

import piexif
from PIL import Image

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _jpeg_with_date(color, date_str: str, filename="photo.jpg") -> tuple[str, bytes, str]:
    img = Image.new("RGB", (400, 300), color=color)
    exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode()}}
    buf = io.BytesIO()
    img.save(buf, "jpeg", exif=piexif.dump(exif_dict))
    return (filename, buf.getvalue(), "image/jpeg")


def _upload(token, color, date_str, filename):
    files = [("files", _jpeg_with_date(color, date_str, filename))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    return res.json()["results"][0]["photo_id"]


def test_pure_date_query_filters_without_vector_search():
    token = _register_and_login()
    august_photo = _upload(token, (220, 20, 20), "2025:08:15 10:00:00", "aug.jpg")
    _upload(token, (20, 20, 220), "2025:03:10 10:00:00", "mar.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "August 2025"})
    assert res.status_code == 200
    body = res.json()

    assert body["filters"]["start_date"] == "2025-08-01"
    assert body["filters"]["end_date"] == "2025-08-31"
    assert body["filters"]["semantic_query"] is None

    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [august_photo]
    # Pure date query -> no semantic component was scored
    assert body["results"][0]["semantic_score"] is None
    assert body["results"][0]["metadata_score"] == 1.0
    assert body["results"][0]["final_score"] == 1.0


def test_date_range_query():
    token = _register_and_login()
    jan = _upload(token, (200, 100, 50), "2024:01:15 10:00:00", "jan.jpg")
    feb = _upload(token, (200, 120, 60), "2024:02:15 10:00:00", "feb.jpg")
    _upload(token, (10, 10, 200), "2024:06:15 10:00:00", "jun.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "January 2024 to March 2024"})
    body = res.json()
    ids = {r["photo"]["id"] for r in body["results"]}
    assert ids == {jan, feb}


def test_combined_date_and_semantic_query_scores_both_signals():
    token = _register_and_login()
    photo_id = _upload(token, (220, 20, 20), "2025:08:15 10:00:00", "aug_red.jpg")
    # A photo with matching date but we'll search with an impossible
    # similarity threshold to prove the semantic component is actually
    # applied on top of the date filter, not ignored.
    res = client.post(
        "/api/search",
        headers=_auth(token),
        json={"query": "August 2025 something", "min_similarity": -1},
    )
    body = res.json()
    assert body["filters"]["start_date"] == "2025-08-01"
    assert body["filters"]["semantic_query"] == "something"
    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [photo_id]
    # Both signals contributed
    assert body["results"][0]["semantic_score"] is not None
    assert body["results"][0]["metadata_score"] == 1.0


def test_combined_query_excludes_photos_outside_the_date_even_if_visually_similar():
    token = _register_and_login()
    _upload(token, (220, 20, 20), "2025:08:15 10:00:00", "aug_red.jpg")
    _upload(token, (220, 20, 20), "2025:03:15 10:00:00", "mar_red_same_color.jpg")

    res = client.post(
        "/api/search",
        headers=_auth(token),
        json={"query": "August 2025 anything", "min_similarity": -1},
    )
    body = res.json()
    assert len(body["results"]) == 1  # the March photo is visually identical but outside the date range


def test_pure_semantic_query_has_no_date_filter():
    token = _register_and_login()
    _upload(token, (220, 20, 20), "2025:08:15 10:00:00", "red.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "warm colors", "min_similarity": -1})
    body = res.json()
    assert body["filters"]["start_date"] is None
    assert body["results"][0]["metadata_score"] is None
    assert body["results"][0]["semantic_score"] is not None


def test_search_isolated_per_user():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    photo_a = _upload(token_a, (220, 20, 20), "2025:08:15 10:00:00", "a.jpg")
    _upload(token_b, (220, 20, 20), "2025:08:15 10:00:00", "b.jpg")

    res = client.post("/api/search", headers=_auth(token_a), json={"query": "August 2025"})
    ids = [r["photo"]["id"] for r in res.json()["results"]]
    assert ids == [photo_a]
