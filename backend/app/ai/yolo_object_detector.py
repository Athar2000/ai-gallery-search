"""
Real object detection using YOLOv8n (via the `ultralytics` package).

Unlike OpenCLIPEmbedder and ArcFaceEmbedder, THIS ONE ACTUALLY RUNS HERE.
The reason: Ultralytics hosts YOLO checkpoints as plain GitHub Release
assets (`github.com/ultralytics/assets/releases/download/...`), which this
sandbox's network allow-list permits — unlike huggingface.co and
openaipublic.azureedge.net, which don't. `pip install torch` also
succeeded this time (it failed with "No space left on device" during
Phase 3 at ~2.8GB free; by Phase 7 enough space had been freed up that the
554MB CPU wheel fit). So both blockers that stopped CLIP/ArcFace happened
not to apply here.

Verified live during development: `YOLO("yolov8n.pt")` auto-downloaded its
weights through this exact code path and correctly detected "4 persons, 1
bus, 1 stop sign" on Ultralytics' own bundled test image and "2 persons, 1
tie" on another — real detections with correct class names, not a stub.

`YOLO("yolov8n.pt")` (the bare model name, not a path) is exactly what
triggers ultralytics' own auto-download/cache logic — first use downloads
to a local cache directory; every call after that is local and instant.
"""
from functools import lru_cache

from app.ai.object_detector import DetectedObject, ObjectDetector
from app.core.config import settings


class YoloObjectDetector(ObjectDetector):
    def __init__(self) -> None:
        from ultralytics import YOLO

        self._model = YOLO("yolov8n.pt")

    def detect_objects(self, content: bytes) -> list[DetectedObject]:
        import io

        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(content)) as img:
            rgb = np.array(img.convert("RGB"))

        results = self._model.predict(rgb, verbose=False)[0]
        detections: list[DetectedObject] = []
        for box in results.boxes:
            confidence = float(box.conf[0])
            if confidence < settings.OBJECT_MIN_CONFIDENCE:
                continue
            class_id = int(box.cls[0])
            name = results.names[class_id]
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append(
                DetectedObject(name=name, confidence=confidence, x=x1, y=y1, width=x2 - x1, height=y2 - y1)
            )
        return detections


@lru_cache(maxsize=1)
def get_yolo_detector() -> YoloObjectDetector:
    """Loading the model is expensive — do it once per process."""
    return YoloObjectDetector()
