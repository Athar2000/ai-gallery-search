"""
Phase 9 additional coverage: fills genuine gaps left after the auth,
photos, search, and jobs test files -- JWT token edge cases beyond
"no token"/"refresh as access", a year-only search through the actual
/api/search endpoint (not just the parser unit test), the database-level
uniqueness constraint that backstops the app-level dedup check, and proof
that a later pipeline step failing doesn't wipe out earlier steps' work.
"""
import io
from datetime import datetime, timedelta, timezone

import piexif
from jose import jwt
from PIL import Image
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core import database as database_module
from app.models.photo import Photo

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _jpeg(color=(150, 150, 150), date_str=None) -> bytes:
    img = Image.new("RGB", (300, 200), color=color)
    buf = io.BytesIO()
    if date_str:
        exif_dict = {"Exif": {piexif.ExifIFD.DateTimeOriginal: date_str.encode()}}
        img.save(buf, "jpeg", exif=piexif.dump(exif_dict))
    else:
        img.save(buf, "jpeg")
    return buf.getvalue()


# --- JWT edge cases ---


def test_malformed_token_rejected():
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert res.status_code == 401


def test_expired_access_token_rejected():
    token = _register_and_login()
    # Craft a token identical in shape to a real one but already expired.
    payload = {
        "sub": jwt.get_unverified_claims(token)["sub"],
        "type": "access",
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers=_auth(expired))
    assert res.status_code == 401


def test_token_signed_with_wrong_secret_rejected():
    token = _register_and_login()
    claims = jwt.get_unverified_claims(token)
    tampered = jwt.encode(claims, "not-the-real-secret-key", algorithm=settings.JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers=_auth(tampered))
    assert res.status_code == 401


def test_token_for_nonexistent_user_rejected():
    """A structurally-valid, correctly-signed token for a user id that
    doesn't exist (e.g. the account was deleted after the token was
    issued) must not authenticate."""
    import uuid

    payload = {
        "sub": str(uuid.uuid4()),
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers=_auth(token))
    assert res.status_code == 401


# --- Search by year only, through the real endpoint ---


def test_search_by_year_only_via_api():
    token = _register_and_login()

    def upload(date_str, filename):
        files = [("files", (filename, _jpeg(date_str=date_str), "image/jpeg"))]
        res = client.post("/api/photos/upload", headers=_auth(token), files=files)
        return res.json()["results"][0]["photo_id"]

    photo_2025 = upload("2025:06:01 10:00:00", "y2025.jpg")
    upload("2024:06:01 10:00:00", "y2024.jpg")

    res = client.post("/api/search", headers=_auth(token), json={"query": "2025"})
    body = res.json()
    assert body["filters"]["start_date"] == "2025-01-01"
    assert body["filters"]["end_date"] == "2025-12-31"
    ids = [r["photo"]["id"] for r in body["results"]]
    assert ids == [photo_2025]


# --- DB-level dedup constraint ---


def test_duplicate_hash_blocked_at_database_level_not_just_app_level():
    """
    The upload endpoint checks for an existing hash before inserting, but
    that's a check-then-act race in theory -- this confirms the database's
    own unique constraint (uq_user_file_hash) is the real backstop, by
    trying to insert two Photo rows with the same user_id+file_hash
    directly, bypassing the app-level check entirely.
    """
    token = _register_and_login()
    db = database_module.SessionLocal()
    try:
        from app.models.user import User

        user = db.query(User).first()
        photo1 = Photo(
            user_id=user.id,
            file_path="a.jpg",
            original_filename="a.jpg",
            file_hash="same_hash_value",
            mime_type="image/jpeg",
            file_size_bytes=100,
        )
        db.add(photo1)
        db.commit()

        photo2 = Photo(
            user_id=user.id,
            file_path="b.jpg",
            original_filename="b.jpg",
            file_hash="same_hash_value",
            mime_type="image/jpeg",
            file_size_bytes=200,
        )
        db.add(photo2)
        try:
            db.commit()
            assert False, "expected IntegrityError from the uq_user_file_hash constraint"
        except IntegrityError:
            db.rollback()
    finally:
        db.close()


# --- Pipeline partial-failure resilience ---


def test_later_step_failure_does_not_erase_earlier_steps_work(monkeypatch):
    """
    If object detection (a late pipeline step) fails, the EXIF/thumbnail/
    embedding work that already succeeded and committed earlier in the
    same pipeline run must survive -- the photo should still be 'ready'
    with a real thumbnail and capture_date, not silently lose that data.
    """
    import app.services.photo_processor as pp

    monkeypatch.setattr(
        pp, "get_object_detector", lambda: (_ for _ in ()).throw(RuntimeError("simulated detector crash"))
    )

    token = _register_and_login()
    files = [("files", ("dated.jpg", _jpeg(date_str="2025:08:15 10:00:00"), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert detail["processing_status"] == "ready"  # the object-detection failure didn't revert this
    assert detail["photo_metadata"]["capture_date"] == "2025-08-15"

    thumb = client.get(f"/api/photos/{photo_id}/thumbnail", headers=_auth(token))
    assert thumb.status_code == 200

    failed_jobs = client.get("/api/jobs", headers=_auth(token), params={"status_filter": "failed"}).json()
    assert any(j["photo_id"] == photo_id and j["job_type"] == "object" for j in failed_jobs)
