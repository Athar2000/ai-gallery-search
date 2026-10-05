"""
Application configuration.

All settings are loaded from environment variables (see .env.example at the
repo root). Nothing here should ever contain a hardcoded secret.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    APP_NAME: str = "AtharVision AI"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_gallery"

    # --- Auth ---
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Storage ---
    STORAGE_BACKEND: str = "local"  # local | s3 (future)
    LOCAL_STORAGE_ROOT: str = "./storage/originals"
    THUMBNAIL_STORAGE_ROOT: str = "./storage/thumbnails"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_IMAGE_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/tiff",
    ]

    # --- Rate limiting (Phase 9) ---
    # RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_AUTH: str = "5/minute" if ENV != "test" else "100000/minute"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Redis / background jobs (Phase 3+) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- AI models (Phase 3+) ---
    # "clip" = real OpenCLIP (needs torch + open_clip_torch + internet to fetch
    # weights on first use — see app/ai/clip_embedder.py).
    # "deterministic_stub" = dependency-free pixel-based stand-in used where
    # real CLIP can't run (see app/ai/stub_embedder.py). This sandbox's .env
    # sets this to deterministic_stub; a real deployment should use "clip".
    EMBEDDING_BACKEND: str = "clip"
    CLIP_MODEL_NAME: str = "ViT-B-32"
    CLIP_PRETRAINED: str = "openai"
    SIMILARITY_THRESHOLD: float = 0.22
    FACE_DETECTION_MODEL: str = "retinaface"
    OBJECT_DETECTION_MODEL: str = "yolov8n"

    # --- Object detection (Phase 7) ---
    # "yolo" = real YOLOv8n via ultralytics. Unlike CLIP/ArcFace, this
    # genuinely works without any special setup -- Ultralytics hosts its
    # weights as plain GitHub Release assets, which even a locked-down
    # network allow-list tends to permit (see app/ai/yolo_object_detector.py).
    # "none" disables object detection entirely (no torch/ultralytics
    # dependency needed) for a deployment that doesn't want it.
    OBJECT_DETECTION_BACKEND: str = "yolo"
    OBJECT_MIN_CONFIDENCE: float = 0.4

    # --- Face detection & recognition (Phase 6+) ---
    # "haarcascade" is real and runs anywhere (classical CV, ships with
    # opencv-python-headless, no model download). A deep-learning detector
    # (RetinaFace/MTCNN) would be more accurate but needs downloaded weights.
    FACE_DETECTION_BACKEND: str = "haarcascade"
    # "arcface" = real face recognition (needs insightface+onnxruntime+internet
    # for the model download — see app/ai/arcface_embedder.py). "deterministic_stub"
    # = dependency-free pixel-based stand-in for environments that can't run it.
    FACE_EMBEDDING_BACKEND: str = "arcface"
    # Minimum cosine similarity between a new face and an existing person's
    # faces for it to be assigned to that person instead of starting a new one.
    FACE_CLUSTER_SIMILARITY_THRESHOLD: float = 0.6

    # --- Search ranking weights (Phase 5, must sum to 1.0) ---
    RANK_WEIGHT_SEMANTIC: float = 0.5
    RANK_WEIGHT_OBJECT: float = 0.2
    RANK_WEIGHT_METADATA: float = 0.2
    RANK_WEIGHT_FACE: float = 0.1


settings = Settings()
