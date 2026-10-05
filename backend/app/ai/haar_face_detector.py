"""
Real face detection using OpenCV's Haar Cascade classifier (Viola-Jones).

Unlike CLIP (app/ai/clip_embedder.py) and the ArcFace embedder below, this
one actually runs in this sandbox: the cascade is classical computer vision
(no neural network weights to download), and its data file ships inside
the `opencv-python-headless` package itself — no huggingface.co/model-hub
dependency at all.

Verified during development against a real photograph (not shipped with
this repo — see the note in README about why) with `detectMultiScale`
correctly finding exactly one face at the right location. The test suite
covers the true-negative case (no false positives on a blank image)
without needing to ship a photo of a real person.

Trade-off: Haar Cascade is meaningfully weaker than a modern deep-learning
detector (RetinaFace/MTCNN) — it struggles with non-frontal faces, poor
lighting, and small faces, and can false-positive on face-like textures.
It's a genuinely working baseline, not a placeholder, but upgrading to a
deep-learning detector (once weights are reachable) is a reasonable future
improvement, same pattern as the CLIP/stub embedder swap.
"""
import io
from functools import lru_cache

import numpy as np
from PIL import Image

from app.ai.face_detector import DetectedFace, FaceDetector


class HaarCascadeFaceDetector(FaceDetector):
    def __init__(self) -> None:
        import cv2

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(f"Failed to load Haar Cascade from {cascade_path}")
        self._cv2 = cv2

    def detect_faces(self, content: bytes) -> list[DetectedFace]:
        with Image.open(io.BytesIO(content)) as img:
            rgb = np.array(img.convert("RGB"))

        gray = self._cv2.cvtColor(rgb, self._cv2.COLOR_RGB2GRAY)
        # minNeighbors/scaleFactor are OpenCV's standard defaults for this
        # cascade; minSize filters out tiny false-positive detections.
        boxes = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        # Haar Cascade doesn't produce a real confidence score the way a
        # neural detector would -- every detection that survives the
        # minNeighbors threshold is reported at a fixed confidence.
        return [DetectedFace(x=int(x), y=int(y), width=int(w), height=int(h), confidence=0.9) for x, y, w, h in boxes]


@lru_cache(maxsize=1)
def get_haar_detector() -> HaarCascadeFaceDetector:
    return HaarCascadeFaceDetector()
