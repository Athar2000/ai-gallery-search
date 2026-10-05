"""
Phase 2 tests: upload pipeline, EXIF extraction, dedup, thumbnails, and the
user-isolation guarantees on photo access.

Reuses the same test-database setup as test_auth.py. Uses a temp directory
for storage so tests never touch real dev/prod photo files.
"""
import io

import piexif
import pytest
from PIL import Image

from app.core import database as database_module
from app.core.config import settings
from app.services import storage as storage_module

from .test_auth import TestingSessionLocal, client, fresh_schema  # noqa: F401 (fixtures)


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Point the storage backend at a throwaway directory for every test."""
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path / "originals"))
    monkeypatch.setattr(settings, "THUMBNAIL_STORAGE_ROOT", str(tmp_path / "thumbnails"))
    fresh = storage_module.LocalStorage()
    monkeypatch.setattr(storage_module, "storage", fresh)
    # photos.py imported `storage_module` (the module), so this patches the
    # instance every route sees too.

    # The upload endpoint's BackgroundTask runs process_photo(), which opens
    # its own DB session — point that at the same test database the API
    # requests use, or the background task can't see the row it should process.
    monkeypatch.setattr(database_module, "SessionLocal", TestingSessionLocal)
    yield


def _make_jpeg_bytes(color=(120, 180, 220), size=(800, 600), with_exif=True) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    if with_exif:
        exif_dict = {
            "0th": {piexif.ImageIFD.Make: b"TestCam", piexif.ImageIFD.Model: b"Model X"},
            "Exif": {piexif.ExifIFD.DateTimeOriginal: b"2025:08:15 10:30:00"},
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"N",
                piexif.GPSIFD.GPSLatitude: ((26, 1), (50, 1), (8, 100)),
                piexif.GPSIFD.GPSLongitudeRef: b"E",
                piexif.GPSIFD.GPSLongitude: ((80, 1), (56, 1), (46, 100)),
            },
        }
        img.save(buf, "jpeg", exif=piexif.dump(exif_dict))
    else:
        img.save(buf, "jpeg")
    return buf.getvalue()


def _register_and_login(email="user1@example.com", password="password123") -> str:
    client.post("/api/auth/register", json={"email": email, "password": password})
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_upload_accepts_valid_jpeg_and_processes_synchronously_in_tests():
    token = _register_and_login()
    files = [("files", ("photo.jpg", _make_jpeg_bytes(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert res.status_code == 201
    body = res.json()["results"][0]
    assert body["status"] == "accepted"
    photo_id = body["photo_id"]

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert detail["processing_status"] == "ready"
    assert detail["photo_metadata"]["capture_date"] == "2025-08-15"
    assert detail["photo_metadata"]["capture_date_source"] == "exif"
    assert detail["photo_metadata"]["camera_make"] == "TestCam"
    assert detail["photo_metadata"]["latitude"] is not None
    assert detail["photo_metadata"]["longitude"] is not None


def test_duplicate_upload_detected_by_hash():
    token = _register_and_login()
    content = _make_jpeg_bytes()
    files = [("files", ("photo.jpg", content, "image/jpeg"))]
    first = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert first.json()["results"][0]["status"] == "accepted"

    second = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert second.json()["results"][0]["status"] == "duplicate"

    listing = client.get("/api/photos", headers=_auth(token)).json()
    assert listing["total"] == 1  # duplicate must not create a second row


def test_upload_without_exif_falls_back_to_file_modified_date():
    token = _register_and_login()
    content = _make_jpeg_bytes(color=(10, 10, 10), with_exif=False)
    files = [("files", ("no_exif.jpg", content, "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert detail["photo_metadata"]["capture_date_source"] == "file_modified"
    assert detail["photo_metadata"]["capture_date"] is not None


def test_corrupt_file_rejected():
    token = _register_and_login()
    files = [("files", ("fake.jpg", b"this is not an image", "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert res.json()["results"][0]["status"] == "rejected"


def test_unsupported_mime_type_rejected():
    token = _register_and_login()
    files = [("files", ("notes.txt", b"hello world", "text/plain"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert res.json()["results"][0]["status"] == "rejected"


def test_oversized_file_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0)  # anything counts as too big
    import app.api.routes.photos as photos_route

    monkeypatch.setattr(photos_route, "MAX_UPLOAD_BYTES", 1)
    token = _register_and_login()
    files = [("files", ("photo.jpg", _make_jpeg_bytes(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    assert res.json()["results"][0]["status"] == "rejected"


def test_thumbnail_is_generated_and_smaller_than_original():
    token = _register_and_login()
    files = [("files", ("photo.jpg", _make_jpeg_bytes(size=(2000, 1500)), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    thumb_res = client.get(f"/api/photos/{photo_id}/thumbnail", headers=_auth(token))
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/jpeg"

    with Image.open(io.BytesIO(thumb_res.content)) as img:
        assert max(img.size) <= 480


def test_user_cannot_access_another_users_photo():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")

    files = [("files", ("photo.jpg", _make_jpeg_bytes(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token_a), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    assert client.get(f"/api/photos/{photo_id}", headers=_auth(token_b)).status_code == 404
    assert client.get(f"/api/photos/{photo_id}/thumbnail", headers=_auth(token_b)).status_code == 404
    assert client.delete(f"/api/photos/{photo_id}", headers=_auth(token_b)).status_code == 404

    # Owner can still see it fine
    assert client.get(f"/api/photos/{photo_id}", headers=_auth(token_a)).status_code == 200


def test_delete_is_soft_and_hides_photo_from_listing():
    token = _register_and_login()
    files = [("files", ("photo.jpg", _make_jpeg_bytes(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    assert client.delete(f"/api/photos/{photo_id}", headers=_auth(token)).status_code == 204
    assert client.get(f"/api/photos/{photo_id}", headers=_auth(token)).status_code == 404
    listing = client.get("/api/photos", headers=_auth(token)).json()
    assert listing["total"] == 0
