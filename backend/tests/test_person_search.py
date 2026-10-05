"""
Phase 7 extension: once a person is named (Phase 6), searching for that
name should filter to photos containing them -- the spec's own example,
"Photos with Athar". Uses the same fixed-box face detector test double as
test_face_clustering.py to keep this fast and deterministic.
"""
import io

from PIL import Image

from app.ai.face_detector import DetectedFace, FaceDetector
import app.services.photo_processor as photo_processor_module

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


class _FixedBoxDetector(FaceDetector):
    def detect_faces(self, content: bytes) -> list[DetectedFace]:
        with Image.open(io.BytesIO(content)) as img:
            w, h = img.size
        return [DetectedFace(x=0, y=0, width=min(100, w), height=min(100, h), confidence=0.95)]


def _upload_face(token, face_color, filename):
    photo_processor_module.get_face_detector = lambda: _FixedBoxDetector()
    img = Image.new("RGB", (400, 300), color=(200, 200, 200))
    for x in range(100):
        for y in range(100):
            img.putpixel((x, y), face_color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    files = [("files", (filename, buf.getvalue(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    return res.json()["results"][0]["photo_id"]


def test_search_by_named_person_filters_correctly(monkeypatch):
    monkeypatch.setattr(photo_processor_module, "get_face_detector", lambda: _FixedBoxDetector())
    token = _register_and_login()

    athar_photo = _upload_face(token, (50, 60, 200), "athar.jpg")
    _upload_face(token, (255, 0, 0), "someone_else.jpg")  # different face -> different person

    people = client.get("/api/people", headers=_auth(token)).json()
    athar = next(p for p in people if p["avatar_photo_id"] == athar_photo)
    client.patch(f"/api/people/{athar['id']}", headers=_auth(token), json={"name": "Athar"})

    res = client.post("/api/search", headers=_auth(token), json={"query": "photos with Athar"})
    body = res.json()
    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [athar_photo]
    assert body["filters"]["person_name"] == "Athar"
    assert body["results"][0]["face_score"] == 1.0


def test_unnamed_person_cannot_be_searched_by_name(monkeypatch):
    """A cluster with no name yet shouldn't match anything -- there's
    nothing to match against."""
    monkeypatch.setattr(photo_processor_module, "get_face_detector", lambda: _FixedBoxDetector())
    token = _register_and_login()
    _upload_face(token, (50, 60, 200), "unnamed.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "photos with Athar", "min_similarity": -1})
    body = res.json()
    assert body["filters"]["person_name"] is None
    # "Athar" just becomes semantic text since no person by that name exists
    assert "Athar" in body["filters"]["semantic_query"]


def test_named_person_and_object_filters_combine_with_no_leftover_semantic_text(monkeypatch):
    """
    Exercises the spec's own example: 'photos with Athar and a car' should
    resolve entirely to two hard filters (named person + detected object)
    with nothing left over for vector search -- regression coverage for
    the leftover-filler-word bug found live (see test_query_parser.py).
    """
    from app.ai.object_detector import DetectedObject, ObjectDetector

    class _FixedObjectDetector(ObjectDetector):
        def detect_objects(self, content: bytes) -> list[DetectedObject]:
            return [DetectedObject(name="car", confidence=0.9, x=0, y=0, width=10, height=10)]

    monkeypatch.setattr(photo_processor_module, "get_face_detector", lambda: _FixedBoxDetector())
    monkeypatch.setattr(photo_processor_module, "get_object_detector", lambda: _FixedObjectDetector())
    token = _register_and_login()

    photo_id = _upload_face(token, (50, 60, 200), "athar_with_car.jpg")
    people = client.get("/api/people", headers=_auth(token)).json()
    athar = next(p for p in people if p["avatar_photo_id"] == photo_id)
    client.patch(f"/api/people/{athar['id']}", headers=_auth(token), json={"name": "Athar"})

    res = client.post("/api/search", headers=_auth(token), json={"query": "photos with Athar and a car"})
    body = res.json()
    assert body["filters"]["person_name"] == "Athar"
    assert body["filters"]["object_name"] == "car"
    assert body["filters"]["semantic_query"] is None  # nothing leftover -- both stages fully consumed the query
    assert [r["photo"]["id"] for r in body["results"]] == [photo_id]
