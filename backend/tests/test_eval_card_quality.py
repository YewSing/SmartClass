"""T16: scripts/eval_card_quality.py (used in T21) runs on a folder of card photos."""
import runpy
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "eval_card_quality.py"


@pytest.mark.face
def test_prints_verdict_scores_and_ocr_per_photo(tmp_path, monkeypatch, capsys):
    from insightface.app import FaceAnalysis

    from app.core.config import settings
    from tests import card_images

    fa = FaceAnalysis(name=settings.INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    fa.prepare(ctx_id=-1, det_size=(640, 640))
    person = card_images.people(fa)[0]
    (tmp_path / "clean.png").write_bytes(card_images.card_photo(person))
    (tmp_path / "glare.png").write_bytes(card_images.card_photo(person, glare="text"))
    (tmp_path / "notes.txt").write_text("ignored")

    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--matric", "23004976", "--name", "Tan Yew Sing", str(tmp_path)])
    runpy.run_path(str(SCRIPT), run_name="__main__")
    out = capsys.readouterr().out

    clean, glare = out.split("clean.png: ")[1].split("glare.png: ")
    assert clean.startswith("OK") and "OCR matric: 23004976" in clean and "matches: True" in clean
    assert glare.startswith("BLOCKED") and "glare" in glare and "student sees: Glare" in glare
    assert "notes.txt" not in out


def test_empty_folder_exits_with_a_message(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(tmp_path)])
    with pytest.raises(SystemExit, match="No photos"):
        runpy.run_path(str(SCRIPT), run_name="__main__")
