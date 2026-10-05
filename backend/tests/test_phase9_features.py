"""
Phase 9 tests: rate limiting on auth endpoints, the jobs API (spec section
23), and retrying a failed processing pipeline (spec section 27).
"""
import io
import uuid

from PIL import Image

from .test_auth import client, fresh_schema  # noqa: F401
from .test_photos import _auth, _register_and_login, isolated_storage  # noqa: F401


def _jpeg() -> bytes:
    img = Image.new("RGB", (300, 200), color=(150, 150, 150))
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


# --- Rate limiting ---


def test_rate_limiter_actually_enforces_a_limit():
    """
    Confirms the limiter mechanism genuinely rejects excess requests, not
    just that a decorator is present. Uses a throwaway route with a tight
    limit on the *same* shared `limiter` instance that auth.py's
    register/login use, rather than fighting with settings.RATE_LIMIT_AUTH
    being baked into those decorators at import time (which is why this
    can't just monkeypatch the setting for a quick per-test override).

    This is a real confirmation the limiter works: the production default
    (5/minute on register/login, see app/core/config.py) is exactly what
    broke this test suite the first time it was added -- the suite
    registers accounts dozens of times per run from the same test-client
    "IP", which is why the sandbox's own .env raises the limit to
    10000/minute for every other test in this file.
    """
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.core.rate_limit import limiter

    probe_app = FastAPI()
    probe_app.state.limiter = limiter
    probe_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @probe_app.get("/probe")
    @limiter.limit("3/minute")
    def probe(request: Request):
        return {"ok": True}

    probe_client = TestClient(probe_app)
    statuses = [probe_client.get("/probe").status_code for _ in range(5)]
    limiter.reset()

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:], f"expected a 429 after exceeding the limit, got {statuses}"


# --- Jobs API ---


def test_jobs_listed_after_upload():
    token = _register_and_login()
    files = [("files", ("a.jpg", _jpeg(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    jobs = client.get("/api/jobs", headers=_auth(token)).json()
    assert len(jobs) > 0
    assert all(j["photo_id"] == photo_id for j in jobs)
    job_types = {j["job_type"] for j in jobs}
    assert "exif" in job_types and "thumbnail" in job_types and "embedding" in job_types


def test_job_detail_and_isolation():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    files = [("files", ("a.jpg", _jpeg(), "image/jpeg"))]
    client.post("/api/photos/upload", headers=_auth(token_a), files=files)

    jobs_a = client.get("/api/jobs", headers=_auth(token_a)).json()
    job_id = jobs_a[0]["id"]

    assert client.get(f"/api/jobs/{job_id}", headers=_auth(token_a)).status_code == 200
    assert client.get(f"/api/jobs/{job_id}", headers=_auth(token_b)).status_code == 404
    assert client.get("/api/jobs", headers=_auth(token_b)).json() == []


def test_jobs_filterable_by_status():
    token = _register_and_login()
    files = [("files", ("a.jpg", _jpeg(), "image/jpeg"))]
    client.post("/api/photos/upload", headers=_auth(token), files=files)

    done_jobs = client.get("/api/jobs", headers=_auth(token), params={"status_filter": "done"}).json()
    assert len(done_jobs) > 0
    assert all(j["status"] == "done" for j in done_jobs)

    failed_jobs = client.get("/api/jobs", headers=_auth(token), params={"status_filter": "failed"}).json()
    assert failed_jobs == []


# --- Retry / reprocess ---


def test_reprocess_a_failed_photo_recovers_it(monkeypatch):
    """
    Simulates a real pipeline failure (the embedder raises), confirms the
    photo lands in processing_status='failed' with a failed job row, then
    confirms /reprocess actually recovers it once the failure is gone --
    exercising spec section 27's "mark failed jobs and allow retry".
    """
    import app.services.photo_processor as pp

    token = _register_and_login()
    files = [("files", ("a.jpg", _jpeg(), "image/jpeg"))]

    broken = pp.get_embedder
    monkeypatch.setattr(pp, "get_embedder", lambda: (_ for _ in ()).throw(RuntimeError("simulated embedder outage")))
    res = client.post("/api/photos/upload", headers=_auth(token), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    detail = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert detail["processing_status"] == "failed"

    failed_jobs = client.get("/api/jobs", headers=_auth(token), params={"status_filter": "failed"}).json()
    assert any(j["photo_id"] == photo_id and j["job_type"] == "embedding" for j in failed_jobs)

    # Fix the outage, then retry
    monkeypatch.setattr(pp, "get_embedder", broken)
    retry_res = client.post(f"/api/photos/{photo_id}/reprocess", headers=_auth(token))
    assert retry_res.status_code == 202

    recovered = client.get(f"/api/photos/{photo_id}", headers=_auth(token)).json()
    assert recovered["processing_status"] == "ready"

    # The originally-failed job's retry_count should reflect the attempt
    all_jobs = client.get("/api/jobs", headers=_auth(token)).json()
    embedding_jobs = [j for j in all_jobs if j["photo_id"] == photo_id and j["job_type"] == "embedding"]
    assert any(j["retry_count"] >= 1 for j in embedding_jobs)


def test_cannot_reprocess_another_users_photo():
    token_a = _register_and_login("a@example.com", "password123")
    token_b = _register_and_login("b@example.com", "password123")
    files = [("files", ("a.jpg", _jpeg(), "image/jpeg"))]
    res = client.post("/api/photos/upload", headers=_auth(token_a), files=files)
    photo_id = res.json()["results"][0]["photo_id"]

    assert client.post(f"/api/photos/{photo_id}/reprocess", headers=_auth(token_b)).status_code == 404


def test_reprocess_unknown_photo_404s():
    token = _register_and_login()
    assert client.post(f"/api/photos/{uuid.uuid4()}/reprocess", headers=_auth(token)).status_code == 404
