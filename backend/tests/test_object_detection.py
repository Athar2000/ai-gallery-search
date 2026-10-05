"""
Tests app.ai.yolo_object_detector.YoloObjectDetector directly -- this is
real YOLOv8n inference via ultralytics, not a stub (see that module's
docstring for why it genuinely runs here, unlike CLIP/ArcFace).

This test needs network access on first run (to fetch yolov8n.pt from its
GitHub Release, cached locally afterward) -- unlike the rest of the suite,
which is fully offline. That's a deliberate, documented exception: it's
the price of testing a real detector instead of a stub.

We don't ship a real object photo in this repo (same reasoning as
test_face_detection.py), so this only covers the true-negative path
automatically. The true-positive path was manually verified during
development against Ultralytics' own bundled test images
(4 persons + 1 bus + 1 stop sign, and 2 persons + 1 tie -- both correct)
and is documented in the README.
"""
import io

from PIL import Image

from app.ai.yolo_object_detector import YoloObjectDetector


def _solid_color_jpeg(color=(120, 120, 120), size=(400, 300)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


def test_no_detections_on_blank_image():
    detector = YoloObjectDetector()
    objects = detector.detect_objects(_solid_color_jpeg())
    assert objects == []
