"""
InsightFace wrapper for embedding extraction.
The FaceAnalysis object is loaded once at startup and stored in app.state.face_app.
Never write raw image bytes to disk — only the extracted embedding is kept (NFR-01).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis


def extract_embeddings(face_app: "FaceAnalysis", image_bytes: bytes) -> list[np.ndarray]:
    """
    Decode image bytes, run InsightFace detection, return a list of L2-normalised
    512-dimensional embedding vectors — one per detected face.
    Returns an empty list if no face is detected.
    Raw image bytes are never persisted.
    """
    import cv2

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    faces = face_app.get(img)
    return [face.normed_embedding for face in faces if face.normed_embedding is not None]


def average_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    """Average multiple embeddings and re-normalise to unit length."""
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm == 0:
        return avg
    return avg / norm
