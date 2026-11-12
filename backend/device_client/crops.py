"""Face boxes to JPEG crops for POST /device/faces (FR-402).

The server upscales crops under 320 px and pads tight ones, so a 30 % margin and a longest side of
at most 320 px are what it wants. Crops live in memory only (NFR-01).
"""
import cv2
import numpy as np

from device_client.detector import Box


def expand_box(box: Box, frame_w: int, frame_h: int, margin: float = 0.3) -> Box:
    """The box plus `margin` of its width/height on each side, clipped to the frame."""
    x, y, w, h = box
    dx = round(w * margin)
    dy = round(h * margin)
    x0 = max(0, x - dx)
    y0 = max(0, y - dy)
    x1 = min(frame_w, x + w + dx)
    y1 = min(frame_h, y + h + dy)
    return (x0, y0, x1 - x0, y1 - y0)


def crop_faces(frame: np.ndarray, boxes: list[Box], margin: float = 0.3,
               max_crops: int = 10, max_side: int = 320) -> list[bytes]:
    """JPEG bytes for the largest `max_crops` faces of one frame, largest first."""
    valid = [box for box in boxes if box[2] > 0 and box[3] > 0]
    valid.sort(key=lambda box: box[2] * box[3], reverse=True)
    frame_h, frame_w = frame.shape[:2]

    crops: list[bytes] = []
    for box in valid[:max_crops]:
        x, y, w, h = expand_box(box, frame_w, frame_h, margin)
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            continue
        if max(h, w) > max_side:
            scale = max_side / max(h, w)
            crop = cv2.resize(crop, (max(1, round(w * scale)), max(1, round(h * scale))),
                              interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            continue
        crops.append(buf.tobytes())
    return crops
