from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DetectedFace:
    x: int
    y: int
    width: int
    height: int
    confidence: float


class FaceDetector(ABC):
    @abstractmethod
    def detect_faces(self, content: bytes) -> list[DetectedFace]:
        """Returns bounding boxes for every face found in the image bytes."""
