from functools import lru_cache

from app.ai.object_detector import ObjectDetector
from app.core.config import settings


@lru_cache(maxsize=1)
def get_object_detector() -> ObjectDetector:
    if settings.OBJECT_DETECTION_BACKEND == "yolo":
        from app.ai.yolo_object_detector import get_yolo_detector

        return get_yolo_detector()
    if settings.OBJECT_DETECTION_BACKEND == "none":
        from app.ai.object_detector_noop import NoopObjectDetector

        return NoopObjectDetector()
    raise ValueError(f"Unknown OBJECT_DETECTION_BACKEND: {settings.OBJECT_DETECTION_BACKEND!r}")
