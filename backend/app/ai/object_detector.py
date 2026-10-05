from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DetectedObject:
    name: str
    confidence: float
    x: int
    y: int
    width: int
    height: int


class ObjectDetector(ABC):
    @abstractmethod
    def detect_objects(self, content: bytes) -> list[DetectedObject]:
        """Returns every object found in the image, with its class name,
        confidence, and bounding box."""
