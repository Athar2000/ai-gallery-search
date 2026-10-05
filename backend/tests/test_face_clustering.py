"""
Phase 6 integration tests: the upload -> detect -> crop -> embed -> cluster
-> person pipeline, and the /api/people endpoints.

Real face *detection* is covered separately (test_face_detection.py) against
the real Haar Cascade. Here, detection is replaced with a fixed-box test
double so these tests isolate what they're actually meant to check:
clustering and naming logic, using the deterministic stub face embedder
(same honesty rules as test_embeddings.py -- this proves the plumbing, not
real facial-identity matching, which needs FACE_EMBEDDING_BACKEND=arcface).
"""
import io

from PIL import Image

from app.ai.face_detector import DetectedFace, FaceDetector
import app.services.photo_processor as photo_processor_module

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


class _FixedBoxDetector(FaceDetector):
    """Always reports exactly one face over a fixed region -- lets tests
    control the 'face crop' just by controlling the photo's pixel colors."""

    def detect_faces(self, content: bytes) -> list[DetectedFace]:
        with Image.open(io.BytesIO(content)) as img:
            w, h = img.size
        return [DetectedFace(x=0, y=0, width=min(100, w), height=min(100, h), confidence=0.95)]


def _install_fixed_box_detector(monkeypatch):
    monkeypatch.setattr(photo_processor_module, "get_face_detector", lambda: _FixedBoxDetector())


def _photo_with_face_patch(face_color, background=(200, 200, 200)) -> bytes:
    img = Image.new("RGB", (400, 300), color=background)
    for x in range(100):
        for y in range(100):
            img.putpixel((x, y), face_color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


def _upload(token, face_color, filename="photo.jpg"):
    files = [("files", (filename, _photo_with_face_patch(face_color), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    return res.json()["results"][0]["photo_id"]


def test_same_face_across_two_photos_clusters_into_one_person(monkeypatch):
    _install_fixed_box_detector(monkeypatch)
    token = _register_and_login()

    _upload(token, (50, 60, 200), "a.jpg")
    _upload(token, (52, 58, 198), "b.jpg")  # near-identical patch, not byte-identical

    people = client.get("/api/people", headers=_auth(token)).json()
    assert len(people) == 1
    assert people[0]["photo_count"] == 2


def test_different_face_creates_a_new_person(monkeypatch):
    _install_fixed_box_detector(monkeypatch)
    token = _register_and_login()

    _upload(token, (255, 0, 0), "red_face.jpg")
    _upload(token, (0, 255, 0), "green_face.jpg")

    people = client.get("/api/people", headers=_auth(token)).json()
    assert len(people) == 2
    assert {p["photo_count"] for p in people} == {1, 1}


def test_rename_person():
    token = _register_and_login()

    # No detector patch needed here -- Haar Cascade genuinely runs, it will
    # just find 0 faces on this synthetic image, so we drive Person
    # creation directly through the fixed-box path in a nested import to
    # keep this test self-contained without needing the monkeypatch fixture
    # plumbing for a test that's really about the rename endpoint.
    import app.services.photo_processor as pp

    original_get_detector = pp.get_face_detector
    pp.get_face_detector = lambda: _FixedBoxDetector()
    try:
        photo_id = _upload(token, (10, 20, 30), "person.jpg")
    finally:
        pp.get_face_detector = original_get_detector

    people = client.get("/api/people", headers=_auth(token)).json()
    assert len(people) == 1
    person_id = people[0]["id"]
    assert people[0]["name"] is None

    res = client.patch(f"/api/people/{person_id}", headers=_auth(token), json={"name": "Athar"})
    assert res.status_code == 200
    assert res.json()["name"] == "Athar"

    refreshed = client.get("/api/people", headers=_auth(token)).json()
    assert refreshed[0]["name"] == "Athar"

    photos = client.get(f"/api/people/{person_id}/photos", headers=_auth(token)).json()
    assert photos["total"] == 1
    assert photos["items"][0]["id"] == photo_id


def test_people_and_faces_isolated_per_user(monkeypatch):
    _install_fixed_box_detector(monkeypatch)
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")

    # Same exact face color for both users -- must NOT cluster across users
    # even though the embeddings would be identical.
    _upload(token_a, (100, 100, 100), "a.jpg")
    _upload(token_b, (100, 100, 100), "b.jpg")

    people_a = client.get("/api/people", headers=_auth(token_a)).json()
    people_b = client.get("/api/people", headers=_auth(token_b)).json()
    assert len(people_a) == 1
    assert len(people_b) == 1
    assert people_a[0]["id"] != people_b[0]["id"]

    # User B can't rename or view user A's person
    assert client.patch(f"/api/people/{people_a[0]['id']}", headers=_auth(token_b), json={"name": "x"}).status_code == 404
    assert client.get(f"/api/people/{people_a[0]['id']}/photos", headers=_auth(token_b)).status_code == 404
