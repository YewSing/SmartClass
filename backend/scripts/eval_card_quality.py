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
          f"ocr>={settings.CARD_OCR_MIN_CONFIDENCE}\n")
    for path in photos:
        img = fv.decode_image(path.read_bytes())
        if img is None:
            print(f"{path.name}: not an image\n")
            continue
        face_found = fv._largest_face_embedding(face_app, img) is not None
        lines = fv.run_ocr(img)
        quality = fv.check_quality(img, lines, face_found)
        card = fv.read_card(lines, args.matric, args.name)

        verdict = "BLOCKED" if quality.blocking else ("accepted with warnings" if quality.reasons else "OK")
        print(f"{path.name}: {verdict}")
        if quality.reasons:
            print(f"  reasons: {', '.join(quality.reasons)}")
            if quality.blocking:
                print(f"  student sees: {quality.message}")
        print("  scores: " + ", ".join(f"{k}={v}" for k, v in quality.scores.items()))
        print(f"  face on card: {'yes' if face_found else 'no'}")
        print(f"  OCR matric: {card.matric or '-'} (confidence {card.matric_confidence})"
              + (f", matches: {card.matric_match}" if args.matric else ""))
        if args.name:
            print(f"  name score: {card.name_score}, matches: {card.name_match}")
        print(f"  OCR lines: {card.lines}\n")


if __name__ == "__main__":
    main()
