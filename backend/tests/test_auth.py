"""
Phase 1 test suite: auth + user isolation.

Uses a separate test database so it never touches dev data. Run with:
    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ai_gallery_test \
        pytest -q
(see README for full setup)
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = settings.DATABASE_URL.rsplit("/", 1)[0] + "/ai_gallery_test"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


client = TestClient(app)


def register(email="user1@example.com", password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def test_register_returns_tokens():
    res = register()
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body and "refresh_token" in body


def test_duplicate_registration_rejected():
    register()
    res = register()
    assert res.status_code == 409


def test_login_wrong_password_rejected():
    register()
    res = client.post("/api/auth/login", json={"email": "user1@example.com", "password": "wrong"})
    assert res.status_code == 401


def test_login_success():
    register()
    res = client.post("/api/auth/login", json={"email": "user1@example.com", "password": "password123"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_protected_route_requires_token():
    res = client.get("/api/auth/me")
    assert res.status_code in (401, 403)


def test_protected_route_with_valid_token():
    tokens = register().json()
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert res.status_code == 200
    assert res.json()["email"] == "user1@example.com"


def test_refresh_token_cannot_be_used_as_access_token():
    tokens = register().json()
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert res.status_code == 401


def test_refresh_issues_new_access_token():
    tokens = register().json()
    res = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_stats_isolated_per_user():
    tokens_a = register("a@example.com", "password123").json()
    tokens_b = register("b@example.com", "password123").json()

    res_a = client.get("/api/stats", headers={"Authorization": f"Bearer {tokens_a['access_token']}"})
    res_b = client.get("/api/stats", headers={"Authorization": f"Bearer {tokens_b['access_token']}"})
    assert res_a.status_code == 200 and res_b.status_code == 200
    # Both start at zero photos; the real isolation test continues in Phase 2
    # once photo upload exists (user A's photos must never appear for user B).
    assert res_a.json()["total_photos"] == 0
    assert res_b.json()["total_photos"] == 0
