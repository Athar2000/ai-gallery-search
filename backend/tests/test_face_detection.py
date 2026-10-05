"""
Tests app.ai.haar_face_detector.HaarCascadeFaceDetector directly -- this is
real OpenCV Haar Cascade detection, not a stub (see that module's
docstring). We deliberately don't ship a photo of a real person in this
test suite (attribution/privacy reasons), so this only covers the
true-negative path automatically. The true-positive path (it correctly
finds a face in an actual photograph) was manually verified during
development against a real JPEG and is documented in the README --
anyone can re-verify by dropping a real face photo into a local script
and calling HaarCascadeFaceDetector().detect_faces() on it.
"""
import io

from PIL import Image

from app.ai.haar_face_detector import HaarCascadeFaceDetector


def _solid_color_jpeg(color=(120, 120, 120), size=(400, 300)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, "jpeg")
    return buf.getvalue()


def test_no_false_positive_on_blank_image():
    detector = HaarCascadeFaceDetector()
    faces = detector.detect_faces(_solid_color_jpeg())
    assert faces == []


def test_detector_loads_cascade_successfully():
    """Confirms the bundled cascade XML actually loads -- if OpenCV's data
    path ever changed, this would fail loudly instead of silently finding
    zero faces on every image."""
    detector = HaarCascadeFaceDetector()
    assert not detector._cascade.empty()
