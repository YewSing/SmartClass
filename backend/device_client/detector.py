"""Local face detection: OpenCV's bundled Haar cascade (no model download, Pi-friendly)."""
from typing import Protocol

import cv2
import numpy as np

Box = tuple[int, int, int, int]   # x, y, w, h in frame pixels


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Box]: ...


class HaarDetector:
    """OpenCV's bundled frontal-face Haar cascade: no model download, a few ms per frame on a Pi."""

    def __init__(self, min_face: int = 60):
        path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(path)
        if self._cascade.empty():
            raise RuntimeError(f"Cannot load face detector {path}")
        self._min = (min_face, min_face)

    def detect(self, frame: np.ndarray) -> list[Box]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        found = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=self._min)
        return [tuple(int(v) for v in box) for box in found]
