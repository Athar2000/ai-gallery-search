from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import albums, auth, jobs, locations, people, photos, search, settings as settings_routes, stats
from app.core.config import settings
from app.core.rate_limit import limiter

# Schema is managed by Alembic migrations from Phase 3 onward — run
# `alembic upgrade head` before starting the app (see README). Phase 1/2's
# `Base.metadata.create_all()` auto-creation is gone: silently letting the
# app create tables is fine for a weekend project, not for a codebase with
# a real migration history.
import app.models  # noqa: F401  (ensures every model is registered on Base)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered personal photo gallery search — index your photos and "
    "search them by date, location, people, objects, scenes, or natural language.",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(photos.router)
app.include_router(jobs.router)
app.include_router(people.router)
app.include_router(albums.router)
app.include_router(locations.router)
app.include_router(search.router)
app.include_router(settings_routes.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
