"""
Matric card verification for face self-enrolment (FR-111).

(a) the face on the card is compared with the student's selfies (InsightFace);
(b) the matric number and name are read from the card with a local OCR model (RapidOCR,
    ONNX on CPU) — card images never leave the server (PDPA);
(c) the card photo gets a quality check with specific, fixable reasons. A quality problem
    only blocks the photo when OCR also fails to read a valid matric number with high
    confidence, so a readable card is never rejected for, say, a little glare.

Images are only held in memory here; nothing is written to disk (NFR-01).
Thresholds live in config (CARD_*) so they can be tuned on real photos (T21).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

from app.core.config import settings

if TYPE_CHECKING:
    from insightface.app import FaceAnalysis

# Order matters: the first reason is the one the student is told about.
QUALITY_MESSAGES: dict[str, str] = {
    "too_dark": "The photo is too dark. Move somewhere brighter and retake.",
    "no_card_found": "We couldn't find your matric card in the photo. Place the whole card inside the outline and retake.",
    "card_too_small": "Your card is too far away. Move closer so the card fills the outline, then retake.",
    "angled": "Your card is at an angle. Hold the phone straight above the card and retake.",
    "blurry": "The photo is blurry. Hold still, let the camera focus, and retake.",
    "glare": "Glare is covering your card details. Tilt the card away from the light and retake.",
    "no_face_on_card": "We couldn't see the photo on your card. Make sure the whole card is visible and retake.",
}

_NORM_WIDTH = 856  # card crops with a longer side are shrunk to this (ID-1 at ~10 px/mm) before measuring
# Characters OCR commonly confuses with digits inside a number.
_TO_DIGIT = str.maketrans({"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "|": "1",
                           "Z": "2", "S": "5", "B": "8", "G": "6"})


@dataclass
class OcrLine:
    text: str
    confidence: float


@dataclass
class CardRead:
    matric: str | None              # the matric number read from the card, if any
    matric_confidence: float        # OCR confidence of the line it came from
    matric_match: bool              # equals the account's matric number
    name_score: float               # share of the account's name words found on the card
    name_match: bool
    lines: list[str] = field(default_factory=list)
    um_card: bool = True            # UM card text (CARD_UM_KEYWORDS) was read on the card


@dataclass
class FaceMatch:
    passed: bool
    score: float | None             # cosine similarity, None when a face is missing
    reason: str | None = None       # no_face_on_card / no_face_in_selfies
    card_face_found: bool = False
    selfie_embedding: np.ndarray | None = None   # averaged selfie faces, what enrolment stores
    selfie_faces: int = 0           # selfies in which a face was found
    selfie_count: int = 0           # selfies checked
    selfie_consistency: float | None = None      # lowest cosine between any two selfies

    @property
    def selfies_consistent(self) -> bool:
        """Every selfie has a face and they all look like the same person."""
        return (self.selfie_faces == self.selfie_count
                and self.selfie_consistency is not None
                and self.selfie_consistency >= settings.FACE_SELFIE_CONSISTENCY_THRESHOLD)


@dataclass
class QualityResult:
    reasons: list[str]
    blocking: bool
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def message(self) -> str | None:
        return QUALITY_MESSAGES[self.reasons[0]] if self.reasons else None


@dataclass
class CardVerification:
    quality: QualityResult
    face: FaceMatch
    card: CardRead

    rotation: int = 0               # degrees the card photo was turned (clockwise) before the checks

    @property
    def passed(self) -> bool:
        """Both FR-111 checks pass, so the submission can be auto-approved (FR-112)."""
        return (not self.quality.blocking and self.face.passed and self.face.selfies_consistent
                and self.card.matric_match and self.card.name_match and self.card.um_card)

    def review_reasons(self) -> list[str]:
        """Why a submission wasn't auto-approved, for the lecturer's review (FR-113)."""
        reasons = []
        if not self.face.passed:
            reasons.append(self.face.reason or "face_mismatch")
        if self.face.selfie_faces < self.face.selfie_count:
            reasons.append("selfie_without_face")
        elif not self.face.selfies_consistent:
            reasons.append("selfies_inconsistent")
        if not self.card.matric_match:
            reasons.append("matric_unreadable" if self.card.matric is None else "matric_mismatch")
        if not self.card.name_match:
            reasons.append("name_mismatch")
        if not self.card.um_card:
            reasons.append("not_um_card")
        return reasons + [r for r in self.quality.reasons if r not in reasons]


# ── images ───────────────────────────────────────────────────────────────────

def decode_image(image_bytes: bytes) -> np.ndarray | None:
    """Decode to BGR and downscale so the longest side is at most CARD_MAX_SIDE_PX."""
    import cv2

    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = settings.CARD_MAX_SIDE_PX / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return img


# ── (a) face on the card vs selfies ──────────────────────────────────────────

def _largest_face(face_app: "FaceAnalysis", img: np.ndarray):
    faces = [f for f in face_app.get(img) if f.normed_embedding is not None]
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def _largest_face_embedding(face_app: "FaceAnalysis", img: np.ndarray) -> np.ndarray | None:
    face = _largest_face(face_app, img)
    return face.normed_embedding if face is not None else None


def _is_upright(face) -> bool:
    """The eyes are above the mouth: the line from between the eyes to the middle of the mouth
    points down within 45 degrees. The detector also finds sideways and upside-down faces, but
    their embeddings don't match the selfies."""
    kps = getattr(face, "kps", None)
    if kps is None:
        return True
    eyes, mouth = (kps[0] + kps[1]) / 2, (kps[3] + kps[4]) / 2
    dx, dy = mouth - eyes
    return dy > abs(dx)


def match_faces(face_app: "FaceAnalysis", selfies: list[np.ndarray], card: np.ndarray) -> FaceMatch:
    """Cosine similarity between the card face and the averaged selfie faces, plus how alike the
    selfies are to each other, so a set mixing two people is never auto-approved."""
    from app.services.face_service import average_embeddings

    selfie_embs = [e for e in (_largest_face_embedding(face_app, s) for s in selfies) if e is not None]
    selfie_emb = average_embeddings(selfie_embs) if selfie_embs else None
    pairs = [float(np.dot(a, b)) for i, a in enumerate(selfie_embs) for b in selfie_embs[i + 1:]]
    selfie_info = {
        "selfie_embedding": selfie_emb, "selfie_faces": len(selfie_embs), "selfie_count": len(selfies),
        "selfie_consistency": round(min(pairs), 4) if pairs else None,
    }
    card_emb = _largest_face_embedding(face_app, card)
    if card_emb is None:
        return FaceMatch(passed=False, score=None, reason="no_face_on_card", **selfie_info)
    if selfie_emb is None:
        return FaceMatch(passed=False, score=None, reason="no_face_in_selfies", card_face_found=True,
                         **selfie_info)
    score = float(np.dot(selfie_emb, card_emb))
    return FaceMatch(passed=score >= settings.CARD_FACE_MATCH_THRESHOLD, score=round(score, 4),
                     card_face_found=True, **selfie_info)


# ── (b) OCR: matric number + name ────────────────────────────────────────────

@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def run_ocr(img: np.ndarray) -> list[OcrLine]:
    result, _ = _ocr_engine()(img)
    return [OcrLine(text=str(text), confidence=float(conf)) for _box, text, conf in (result or [])]


def _matric_candidates(text: str) -> list[str]:
    """Matric-shaped tokens in one OCR line, with digit look-alikes fixed (O→0, I→1, …)."""
    pattern = re.compile(settings.CARD_MATRIC_REGEX)
    # A label stuck to the number ("NO23004976") still counts.
    tail = re.compile(rf"(?<![0-9])({settings.CARD_MATRIC_REGEX})$")
    found = []
    for token in re.findall(r"[A-Z0-9|]+", text.upper()):
        if not any(ch.isdigit() for ch in token):
            continue
        # Keep a 1–3 letter prefix as letters; everything after it should be digits.
        prefix, rest = re.match(r"([A-Z]{0,3})(.*)", token).groups()
        for candidate in (token, prefix + rest.translate(_TO_DIGIT), token.translate(_TO_DIGIT)):
            if pattern.fullmatch(candidate):
                found.append(candidate)
                break
            if m := tail.search(candidate):
                found.append(m.group(1))
                break
    return found


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper())


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _has_um_text(lines: list[OcrLine]) -> bool:
    """Any UM card word (CARD_UM_KEYWORDS) on any line, in any order. OCR splits and misreads
    them ("UNTVERSIT", "MIyEISWA"), so a word within 1 edit (2 for 7+ letters) counts, as does
    a keyword inside a run-together line ("UNIVERSITIMALAYA")."""
    keywords = [k for k in (_letters(k) for k in settings.CARD_UM_KEYWORDS.split(",")) if k]
    words = [w for line in lines for w in re.findall(r"[A-Z]+", line.text.upper())]
    for k in keywords:
        allowed = 2 if len(k) >= 7 else 1
        if any(k in w or (abs(len(w) - len(k)) <= allowed and _edit_distance(w, k) <= allowed)
               for w in words):
            return True
    extra = settings.CARD_UM_TEXT_REGEX
    return bool(extra) and re.search(extra, "".join(_letters(line.text) for line in lines)) is not None


def read_card(lines: list[OcrLine], account_matric: str | None, account_name: str | None) -> CardRead:
    expected = (account_matric or "").upper().replace(" ", "")
    best: tuple[str, float] | None = None
    for line in lines:
        for cand in _matric_candidates(line.text):
            # Prefer the account's own number, then the most confident read.
            key = (cand == expected, line.confidence)
            if best is None or key > (best[0] == expected, best[1]):
                best = (cand, line.confidence)

    # OCR often drops the spaces in names ("TANYEW SING"), so compare letters only.
    card_letters = "".join(_letters(line.text) for line in lines)
    words = [w for w in (_letters(w) for w in (account_name or "").split()) if len(w) >= 2]
    name_score = sum(w in card_letters for w in words) / len(words) if words else 0.0

    return CardRead(
        matric=best[0] if best else None,
        matric_confidence=round(best[1], 4) if best else 0.0,
        matric_match=bool(best and expected and best[0] == expected),
        name_score=round(name_score, 4),
        name_match=name_score >= settings.CARD_NAME_MIN_MATCH,
        lines=[line.text for line in lines],
        um_card=_has_um_text(lines),
    )


# ── (c) photo quality ────────────────────────────────────────────────────────

def _find_card(img: np.ndarray):
    """The card's outline, in either orientation, or None. A printed card is more colourful than
    the white or grey table under it, so look for the largest card-shaped area of one colour
    first (one hue at a time, so a hand holding the card isn't merged with it); edge outlines
    are the fallback (they missed the light-blue MySiswa card on a white table and picked small
    rectangles inside it)."""
    import cv2

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hue = hsv[..., 0].astype(np.int16)
    sat = cv2.GaussianBlur(hsv[..., 1], (5, 5), 0)
    otsu, _ = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coloured = (sat >= max(otsu, settings.CARD_MIN_SATURATION)) & (hsv[..., 2] >= 50)
    k = max(5, round(min(coloured.shape) * 0.02)) | 1   # fills the card's text, photo and fingers
    best = None
    for peak in _hue_peaks(hue[coloured]):
        dist = np.abs(hue - peak)
        mask = (coloured & (np.minimum(dist, 180 - dist) <= 15)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        found = _largest_card_shape(contours, mask.size, min_fill=0.7, hull=True)
        if found is not None and (best is None or found[0] > best[0]):
            best = found
    if best is not None:
        return best

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 30, 90)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _largest_card_shape(contours, gray.size)


def _hue_peaks(hues: np.ndarray) -> list[int]:
    """Main colours (OpenCV hue 0-179, circular) among the saturated pixels, each at least 5%."""
    if hues.size == 0:
        return []
    hist = np.bincount(hues.ravel(), minlength=180).astype(float)
    smooth = np.convolve(np.concatenate([hist[-10:], hist, hist[:10]]), np.ones(11), "same")[10:-10]
    peaks = []
    for h in range(180):
        window = smooth[np.arange(h - 12, h + 13) % 180]
        if smooth[h] > 0.05 * hues.size and smooth[h] == window.max() and all(
                min(abs(h - p), 180 - abs(h - p)) > 12 for p in peaks):
            peaks.append(h)
    return peaks


def _largest_card_shape(contours, img_area: int, min_fill: float = 0.8, hull: bool = False):
    """The largest outline that fills most of its bounding rectangle, as (area, contour, rect).
    With `hull`, the outline's convex hull is used, so fingers over the edge don't count."""
    import cv2

    best = None
    for c in contours:
        if hull:
            c = cv2.convexHull(c)
        area = cv2.contourArea(c)
        if area < 0.02 * img_area:
            continue
        rect = cv2.minAreaRect(c)
        rect_area = rect[1][0] * rect[1][1]
        if rect_area <= 0 or area / rect_area < min_fill:     # not card-shaped
            continue
        if best is None or area > best[0]:
            best = (area, c, rect)
    return best


def _tilt_and_skew(contour, rect) -> tuple[float, float]:
    import cv2

    angle = rect[2] % 90
    tilt = min(angle, 90 - angle)
    skew = 0.0
    quad = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
    if len(quad) == 4:
        p = quad.reshape(4, 2).astype(float)
        sides = [np.linalg.norm(p[i] - p[(i + 1) % 4]) for i in range(4)]
        skew = max(abs(sides[0] - sides[2]) / max(sides[0], sides[2]),
                   abs(sides[1] - sides[3]) / max(sides[1], sides[3]))
    return float(tilt), float(skew)


def check_quality(img: np.ndarray, lines: list[OcrLine], card_face_found: bool) -> QualityResult:
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    reasons: set[str] = set()
    scores: dict[str, float] = {}

    found = _find_card(img)
    region = (0, 0, gray.shape[1], gray.shape[0])
    if found is None:
        reasons.add("no_card_found")
    else:
        area, contour, rect = found
        scores["card_area_fraction"] = round(area / (gray.shape[0] * gray.shape[1]), 4)
        if scores["card_area_fraction"] < settings.CARD_MIN_AREA_FRACTION:
            reasons.add("card_too_small")
        scores["tilt_degrees"], scores["skew"] = (round(v, 3) for v in _tilt_and_skew(contour, rect))
        if scores["tilt_degrees"] > settings.CARD_MAX_TILT_DEGREES or scores["skew"] > settings.CARD_MAX_SKEW_RATIO:
            reasons.add("angled")
        region = cv2.boundingRect(contour)

    x, y, w, h = region
    card_gray, card_hsv = gray[y:y + h, x:x + w], hsv[y:y + h, x:x + w]
    if max(w, h) > _NORM_WIDTH:  # only shrink: enlarging a small card would make it look blurry
        scale = _NORM_WIDTH / max(w, h)   # long side, so a portrait card is measured like a landscape one
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        card_gray = cv2.resize(card_gray, size, interpolation=cv2.INTER_AREA)
        card_hsv = cv2.resize(card_hsv, size, interpolation=cv2.INTER_AREA)

    scores["brightness"] = round(float(card_hsv[..., 2].mean()), 2)
    if scores["brightness"] <= settings.CARD_DARK_MAX_MEAN:
        reasons.add("too_dark")

    scores["blur_variance"] = round(float(cv2.Laplacian(card_gray, cv2.CV_64F).var()), 2)
    if scores["blur_variance"] < settings.CARD_BLUR_MIN_VARIANCE:
        reasons.add("blurry")

    # Glare = one big blown-out patch. Opening removes thin white print (text, lines).
    clipped = ((card_hsv[..., 2] >= 245) & (card_hsv[..., 1] <= 40)).astype(np.uint8)
    clipped = cv2.morphologyEx(clipped, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(clipped)
    biggest = int(stats[1:, cv2.CC_STAT_AREA].max()) if n > 1 else 0
    scores["glare_fraction"] = round(biggest / clipped.size, 4)
    if scores["glare_fraction"] > settings.CARD_GLARE_MAX_FRACTION:
        reasons.add("glare")

    if not card_face_found:
        reasons.add("no_face_on_card")

    ordered = [r for r in QUALITY_MESSAGES if r in reasons]
    readable = read_card(lines, None, None)
    ocr_ok = readable.matric is not None and readable.matric_confidence >= settings.CARD_OCR_MIN_CONFIDENCE
    return QualityResult(reasons=ordered, blocking=bool(ordered) and not ocr_ok, scores=scores)


# ── all together ─────────────────────────────────────────────────────────────

def verify_card(
    face_app: "FaceAnalysis",
    selfies: list[bytes],
    card: bytes,
    account_matric: str | None,
    account_name: str | None,
) -> CardVerification:
    """Run the quality check, the face comparison and OCR on one submission."""
    card_img = decode_image(card)
    if card_img is None:
        return CardVerification(
            quality=QualityResult(reasons=["no_card_found"], blocking=True),
            face=FaceMatch(passed=False, score=None, reason="no_face_on_card"),
            card=read_card([], account_matric, account_name),
        )
    selfie_imgs = [img for img in (decode_image(s) for s in selfies) if img is not None]
    rotation, card_img, face, lines = _best_rotation(face_app, selfie_imgs, card_img)
    face.selfie_count = len(selfies)  # a selfie that can't be decoded counts as one without a face
    quality = check_quality(card_img, lines, face.card_face_found)
    quality.scores["rotation_degrees"] = rotation
    return CardVerification(
        quality=quality,
        face=face,
        card=read_card(lines, account_matric, account_name),
        rotation=rotation,
    )


_TURNS = {0: None, 90: "ROTATE_90_CLOCKWISE", 180: "ROTATE_180", 270: "ROTATE_90_COUNTERCLOCKWISE"}


def _best_rotation(face_app: "FaceAnalysis", selfies: list[np.ndarray], card: np.ndarray):
    """Turn the card photo 0/90/180/270 degrees and keep the turn where the card's face is upright,
    so an upside-down or sideways card isn't reported as faceless or not UM. Without an upright
    face (no photo on the card), the turn where OCR reads best. Stops at the first upright face,
    so an upright card is only read once."""
    import cv2

    best = None
    for degrees, turn in _TURNS.items():
        img = card if turn is None else cv2.rotate(card, getattr(cv2, turn))
        face = _largest_face(face_app, img)
        upright = face is not None and _is_upright(face)
        lines = run_ocr(img)
        read = read_card(lines, None, None)
        ocr_ok = read.matric is not None and read.matric_confidence >= settings.CARD_OCR_MIN_CONFIDENCE
        mean_conf = sum(line.confidence for line in lines) / len(lines) if lines else 0.0
        key = (upright, ocr_ok, read.um_card, face is not None, read.matric_confidence, mean_conf)
        if best is None or key > best[0]:
            best = (key, degrees, img, lines)
        if upright:
            break
    _, degrees, img, lines = best
    return degrees, img, match_faces(face_app, selfies, img), lines
