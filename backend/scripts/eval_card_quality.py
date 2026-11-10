"""Print the card quality scores and OCR result for real matric card photos (T21).

Put photos of your own card in the git-ignored folder backend/eval/cards/ (clean, glare,
blur, angled, dim, ...), then from backend/:

    python scripts/eval_card_quality.py [--matric 23004976] [--name "Tan Yew Sing"] [folder]

For each photo it shows what the enrolment endpoint would decide about the card photo:
the quality reasons, whether they block (only when OCR can't read a matric number
confidently), the raw scores to compare with the CARD_* thresholds, and the OCR read.
Change the thresholds in backend/.env and run it again until good photos pass and bad
ones get the right message. Nothing is written or sent anywhere.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services import face_verification as fv  # noqa: E402

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", default=str(Path(__file__).resolve().parents[1] / "eval" / "cards"))
    parser.add_argument("--matric", help="your matric number, to check the OCR match")
    parser.add_argument("--name", help="your name as in SPeCTRUM, to check the name match")
    args = parser.parse_args()

    photos = sorted(p for p in Path(args.folder).glob("*") if p.suffix.lower() in IMAGE_TYPES)
    if not photos:
        sys.exit(f"No photos in {args.folder}")

    from insightface.app import FaceAnalysis

    face_app = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=-1, det_size=(640, 640))

    print(f"Thresholds: blur>={settings.CARD_BLUR_MIN_VARIANCE} glare<={settings.CARD_GLARE_MAX_FRACTION} "
          f"brightness>{settings.CARD_DARK_MAX_MEAN} area>={settings.CARD_MIN_AREA_FRACTION} "
          f"tilt<={settings.CARD_MAX_TILT_DEGREES} skew<={settings.CARD_MAX_SKEW_RATIO} "
          f"ocr>={settings.CARD_OCR_MIN_CONFIDENCE}")
    print("Decision assumes the selfies match the card face (no selfies here).\n")
    for path in photos:
        img = fv.decode_image(path.read_bytes())
        if img is None:
            print(f"{path.name}: not an image\n")
            continue
        rotation, img, _, lines = fv._best_rotation(face_app, [], img)
        face_found = fv._largest_face_embedding(face_app, img) is not None
        quality = fv.check_quality(img, lines, face_found)
        card = fv.read_card(lines, args.matric, args.name)
        result = fv.CardVerification(
            quality=quality, card=card, rotation=rotation,
            face=fv.FaceMatch(passed=face_found, score=None, card_face_found=face_found,
                              reason=None if face_found else "no_face_on_card",
                              selfie_faces=3, selfie_count=3, selfie_consistency=1.0),
        )
        print(f"{path.name}: {decision(result, bool(args.matric), bool(args.name))}")
        if quality.reasons:
            print(f"  quality reasons: {', '.join(quality.reasons)}")
            if quality.blocking:
                print(f"  student sees: {quality.message}")
        print("  scores: " + ", ".join(f"{k}={v}" for k, v in quality.scores.items()))
        print(f"  rotation: {rotation} degrees, face on card: {'yes' if face_found else 'no'}, "
              f"UM card: {'yes' if card.um_card else 'no'}")
        print(f"  OCR matric: {card.matric or '-'} (confidence {card.matric_confidence})"
              + (f", matches: {card.matric_match}" if args.matric else ""))
        if args.name:
            print(f"  name score: {card.name_score}, matches: {card.name_match}")
        print(f"  OCR lines: {card.lines}\n")


def decision(result: "fv.CardVerification", with_matric: bool, with_name: bool) -> str:
    """What enrolment would do with this card photo: BLOCKED, REVIEW (reasons) or AUTO-APPROVE.
    Without --matric / --name those checks are left out."""
    if result.quality.blocking:
        return "BLOCKED"
    skip = set()
    if not with_matric:
        skip |= {"matric_mismatch", "matric_unreadable"}
    if not with_name:
        skip.add("name_mismatch")
    # Quality warnings don't stop auto-approval once OCR reads the card (they aren't blocking).
    reasons = [r for r in result.review_reasons()
               if r not in skip and (r not in result.quality.reasons or r == result.face.reason)]
    if reasons:
        return f"REVIEW ({', '.join(reasons)})"
    warnings = f" (warnings: {', '.join(result.quality.reasons)})" if result.quality.reasons else ""
    return "AUTO-APPROVE" + warnings


if __name__ == "__main__":
    main()
