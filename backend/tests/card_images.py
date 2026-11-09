"""Generated matric card photos and selfies for the card verification tests (T15).

No real card or face images are committed (PDPA): faces come from InsightFace's bundled
sample photo `t1.jpg` (six different people), and the card is drawn with PIL.
"""
from __future__ import annotations

import io
import os
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

CARD_W, CARD_H = 856, 540           # ID-1 card at ~10 px/mm
PHOTO_W, PHOTO_H = 1280, 960        # the "phone photo" the card sits in
TEXT = (235, 235, 235)              # printed white, not blown out


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


@lru_cache(maxsize=1)
def _sample_photo() -> np.ndarray:
    import insightface

    path = os.path.join(os.path.dirname(insightface.__file__), "data", "images", "t1.jpg")
    return cv2.imread(path)


def people(face_app) -> list[Image.Image]:
    """One head-and-shoulders crop per person in t1.jpg, largest faces first."""
    photo = _sample_photo()
    faces = sorted(face_app.get(photo), key=lambda f: -(f.bbox[2] - f.bbox[0]))
    crops = []
    for f in faces:
        x0, y0, x1, y1 = (int(v) for v in f.bbox)
        pad = (x1 - x0) // 3
        crop = photo[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
        crops.append(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))
    return crops


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def selfies(person: Image.Image, n: int = 3) -> list[bytes]:
    """n selfie-like photos of one person: different sizes, positions and lighting."""
    out = []
    for i in range(n):
        canvas = Image.new("RGB", (720, 960), (200 - 20 * i, 190, 180))
        size = 360 + 60 * i
        face = person.resize((size, round(size * person.height / person.width)))
        face = ImageEnhance.Brightness(face).enhance(0.9 + 0.1 * i)
        if i == 1:
            face = face.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        canvas.paste(face, ((720 - face.width) // 2, 200 - 30 * i))
        out.append(_png(canvas))
    return out


def card_photo(
    person: Image.Image | None,
    name: str = "TAN YEW SING",
    matric: str = "23004976",
    *,
    glare: str | None = None,   # "corner" (text still readable) or "text" (covers name + matric)
    blur: float = 0,
    brightness: float = 1.0,
    scale: float = 1.0,
    angle: float = 0,
) -> bytes:
    """A phone photo of a UM-style matric card on a grey table."""
    card = Image.new("RGB", (CARD_W, CARD_H), (40, 70, 140))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, CARD_W, 90], fill=(20, 40, 100))
    d.text((40, 25), "UNIVERSITI MALAYA", fill=TEXT, font=_font(36))
    d.text((300, 200), name, fill=TEXT, font=_font(34))
    d.text((300, 270), matric, fill=TEXT, font=_font(34))
    d.text((300, 340), "FACULTY OF COMPUTER SCIENCE", fill=TEXT, font=_font(22))
    d.text((300, 380), "AND INFORMATION TECHNOLOGY", fill=TEXT, font=_font(22))
    if person is not None:
        card.paste(person.resize((220, 280)), (40, 140))
    if glare:
        layer = Image.new("L", card.size, 0)
        box = [520, 330, 856, 540] if glare == "corner" else [260, 170, 760, 330]
        ImageDraw.Draw(layer).ellipse(box, fill=255)
        layer = layer.filter(ImageFilter.GaussianBlur(6))
        card = Image.composite(Image.new("RGB", card.size, (255, 255, 255)), card, layer)

    if scale != 1.0:
        card = card.resize((round(CARD_W * scale), round(CARD_H * scale)))
    if angle:
        card = card.convert("RGBA").rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    photo = Image.new("RGB", (PHOTO_W, PHOTO_H), (110, 110, 105))
    photo.paste(card, ((PHOTO_W - card.width) // 2, (PHOTO_H - card.height) // 2),
                card if card.mode == "RGBA" else None)
    if blur:
        photo = photo.filter(ImageFilter.GaussianBlur(blur))
    if brightness != 1.0:
        photo = ImageEnhance.Brightness(photo).enhance(brightness)
    return _png(photo)
