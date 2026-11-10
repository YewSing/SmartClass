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
    header: str = "UNIVERSITI MALAYA",   # another issuer's name makes a non-UM card
    portrait: bool = False,     # the real MySiswa card: portrait, light blue, dark print
    table: tuple[int, int, int] = (110, 110, 105),
    turn: int = 0,              # the whole photo turned clockwise by this many degrees (0/90/180/270)
    brand: str = "MySISWA",     # portrait card only: the scheme name under the university's
) -> bytes:
    """A phone photo of a UM-style matric card on a table."""
    card = (_portrait_card(person, name, matric, header, brand) if portrait
            else _landscape_card(person, name, matric, header))
    if glare:
        layer = Image.new("L", card.size, 0)
        box = [520, 330, 856, 540] if glare == "corner" else [260, 170, 760, 330]
        ImageDraw.Draw(layer).ellipse(box, fill=255)
        layer = layer.filter(ImageFilter.GaussianBlur(6))
        card = Image.composite(Image.new("RGB", card.size, (255, 255, 255)), card, layer)

    w, h = card.size
    if scale != 1.0:
        card = card.resize((round(w * scale), round(h * scale)))
    if angle:
        card = card.convert("RGBA").rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    photo_size = (PHOTO_H, PHOTO_W) if portrait else (PHOTO_W, PHOTO_H)   # phone held like the card
    photo = Image.new("RGB", photo_size, table)
    photo.paste(card, ((photo.width - card.width) // 2, (photo.height - card.height) // 2),
                card if card.mode == "RGBA" else None)
    if blur:
        photo = photo.filter(ImageFilter.GaussianBlur(blur))
    if brightness != 1.0:
        photo = ImageEnhance.Brightness(photo).enhance(brightness)
    if turn:
        photo = photo.rotate(-turn, expand=True)   # PIL turns anticlockwise
    return _png(photo)


def _landscape_card(person, name, matric, header) -> Image.Image:
    card = Image.new("RGB", (CARD_W, CARD_H), (40, 70, 140))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, CARD_W, 90], fill=(20, 40, 100))
    d.text((40, 25), header, fill=TEXT, font=_font(36))
    d.text((300, 200), name, fill=TEXT, font=_font(34))
    d.text((300, 270), matric, fill=TEXT, font=_font(34))
    d.text((300, 340), "FACULTY OF COMPUTER SCIENCE", fill=TEXT, font=_font(22))
    d.text((300, 380), "AND INFORMATION TECHNOLOGY", fill=TEXT, font=_font(22))
    if person is not None:
        card.paste(person.resize((220, 280)), (40, 140))
    return card


def _portrait_card(person, name, matric, header, brand) -> Image.Image:
    """Like the MySiswa card: 54 x 86 mm, light blue, photo top left, dark print."""
    ink = (20, 30, 50)
    card = Image.new("RGB", (CARD_H, CARD_W), (140, 205, 235))
    d = ImageDraw.Draw(card)
    words = header.split()
    d.text((290, 170), " ".join(words[:1]), fill=ink, font=_font(30))
    d.text((290, 210), " ".join(words[1:]), fill=ink, font=_font(30))
    d.text((290, 300), brand, fill=ink, font=_font(34))
    d.text((30, 420), name, fill=ink, font=_font(28))
    d.text((30, 470), "FACULTY OF COMPUTER SCIENCE", fill=ink, font=_font(20))
    d.text((30, 500), "AND INFORMATION TECHNOLOGY", fill=ink, font=_font(20))
    d.text((200, 800), matric, fill=ink, font=_font(28))
    if person is not None:
        card.paste(person.resize((240, 300)), (25, 100))
    return card
