"""
Phase 7 integration tests: object detection storage + object/person-aware
hybrid search. Real object *detection* is covered separately
(test_object_detection.py) against real YOLOv8n. Here, detection is
replaced with a fixed-response test double so these tests isolate what
they're actually meant to check: that a detected object becomes a real
search filter, exactly like a detected/named person does.
"""
import io

from PIL import Image

from app.ai.object_detector import DetectedObject, ObjectDetector
import app.services.photo_processor as photo_processor_module

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


class _FixedObjectDetector(ObjectDetector):
    def __init__(self, names: list[str]):
        self._names = names

    def detect_objects(self, content: bytes) -> list[DetectedObject]:
        return [DetectedObject(name=name, confidence=0.9, x=0, y=0, width=10, height=10) for name in self._names]


def _upload_with_objects(token, names: list[str], filename="photo.jpg", color=(150, 150, 150)):
    import app.services.photo_processor as pp

    original = pp.get_object_detector
    pp.get_object_detector = lambda: _FixedObjectDetector(names)
    try:
        img = Image.new("RGB", (200, 200), color=color)
        buf = io.BytesIO()
        img.save(buf, "jpeg")
        files = [("files", (filename, buf.getvalue(), "image/jpeg"))]
        res = client.post("/api/photos/upload", headers=_auth(token), files=files)
        return res.json()["results"][0]["photo_id"]
    finally:
        pp.get_object_detector = original


def test_detected_objects_appear_in_photo_detail():
    token = _register_and_login()
    photo_id = _upload_with_objects(token, ["car", "dog"])

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    names = {o["name"] for o in detail["objects"]}
    assert names == {"car", "dog"}


def test_search_by_object_name_filters_correctly():
    token = _register_and_login()
    car_photo = _upload_with_objects(token, ["car"], "car.jpg")
    _upload_with_objects(token, ["dog"], "dog.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "photos with cars"})
    body = res.json()
    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [car_photo]
    assert body["filters"]["object_name"] == "car"
    assert body["results"][0]["object_score"] == 1.0


def test_search_by_object_plural_matches_singular_class_name():
    token = _register_and_login()
    _upload_with_objects(token, ["dog"], "dog.jpg")
    res = client.post("/api/search", headers=_auth(token), json={"query": "dogs"})
    assert len(res.json()["results"]) == 1


def test_object_and_date_filters_combine():
    """This directly exercises the spec's own example query:
    'my photos with car from August 2025'."""
    import piexif

    def _jpeg_with_date(color, date_str):
        img = Image.new("RGB", (200, 200), color=color)
        exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode()}}
        buf = io.BytesIO()
        img.save(buf, "jpeg", exif=piexif.dump(exif_dict))
        return buf.getvalue()

    import app.services.photo_processor as pp

    token = _register_and_login()

    def upload(names, date_str, filename):
        original = pp.get_object_detector
        pp.get_object_detector = lambda: _FixedObjectDetector(names)
        try:
            files = [("files", (filename, _jpeg_with_date((100, 100, 100), date_str), "image/jpeg"))]
            res = client.post("/api/photos/upload", headers=_auth(token), files=files)
            return res.json()["results"][0]["photo_id"]
        finally:
            pp.get_object_detector = original

    august_car = upload(["car"], "2025:08:15 10:00:00", "aug_car.jpg")
    upload(["car"], "2025:03:15 10:00:00", "mar_car.jpg")  # right object, wrong date
    upload(["dog"], "2025:08:15 10:00:00", "aug_dog.jpg")  # right date, wrong object

    res = client.post("/api/search", headers=_auth(token), json={"query": "my photos with car from August 2025"})
    body = res.json()
    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [august_car]
    assert body["filters"]["start_date"] == "2025-08-01"
    assert body["filters"]["object_name"] == "car"


def test_no_matching_object_falls_through_to_semantic_text():
    """A word that isn't a known object class should just stay in the
    semantic query rather than being (incorrectly) treated as a filter."""
    token = _register_and_login()
    _upload_with_objects(token, ["car"], "car.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "sunset beach", "min_similarity": -1})
    body = res.json()
    assert body["filters"]["object_name"] is None
    assert body["filters"]["semantic_query"] == "sunset beach"
