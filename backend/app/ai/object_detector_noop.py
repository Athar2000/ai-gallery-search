from app.ai.object_detector import DetectedObject, ObjectDetector


class NoopObjectDetector(ObjectDetector):
    """Always reports zero objects. Lets object detection be turned off
    entirely (OBJECT_DETECTION_BACKEND=none) for a deployment that doesn't
    want the torch/ultralytics dependency at all, without needing a fake
    stub that pretends to find things."""

    def detect_objects(self, content: bytes) -> list[DetectedObject]:
        return []
