"""T105: the AP2 slide deck (`docs/ap2-slides.pptx`, built by `docs/slides/build_slides.js`).

Checks that the deck covers each item of the AP2 brief, that every slide carries speaker notes
with likely questions, that its numbers agree with the T104 report, and that it holds only the
T103 diagrams (no screenshots of private data, no secrets).
"""
import hashlib
import re
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

ROOT = Path(__file__).resolve().parents[2]
DECK = ROOT / "docs" / "ap2-slides.pptx"
REPORT = ROOT / "docs" / "report" / "ap2-report.html"
DIAGRAMS = ROOT / "docs" / "diagrams"

BRIEF = ["Objectives progress", "Requirements progress", "Methodology", "System development",
         "Testing and evaluation", "AP1 feedback"]


def _deck() -> Presentation:
    assert DECK.is_file(), "run: npm --prefix docs/slides run build"
    return Presentation(str(DECK))


def _sections() -> list[str]:
    """Section names in order, from the presentation part's section list."""
    xml = _deck().part.blob.decode("utf-8")
    return re.findall(r'<p14:section name="([^"]+)"', xml)


def _slide_text(slide) -> str:
    parts = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            parts.append(sh.text_frame.text)
        if sh.has_table:
            parts += [c.text for row in sh.table.rows for c in row.cells]
    return "\n".join(parts)


def _all_text() -> str:
    return "\n".join(_slide_text(s) for s in _deck().slides)


def test_one_section_per_brief_item_in_order():
    sections = _sections()
    assert [s for s in sections if s in BRIEF] == BRIEF, sections


def test_every_section_has_slides():
    xml = _deck().part.blob.decode("utf-8")
    for name in BRIEF:
        block = re.search(rf'<p14:section name="{name}"[^>]*>(.*?)</p14:section>', xml, re.S)
        assert block and "<p14:sldId " in block.group(1), name


def test_every_slide_has_notes_with_likely_questions():
    for i, slide in enumerate(_deck().slides, 1):
        assert slide.has_notes_slide, f"slide {i} has no notes"
        notes = slide.notes_slide.notes_text_frame.text
        assert "Likely questions:" in notes, f"slide {i}"
        assert re.search(r"^Q: .+\nA: .+", notes, re.M), f"slide {i} has no Q/A pair"


def test_module_split_names_both_students_and_all_eight_modules():
    text = _all_text()
    assert "Yong Yew Sing" in text and "Chow Shino" in text
    for mod in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"):
        assert mod in text, mod


def test_fr_counts_match_the_report():
    m = re.search(r"(\d+) functional requirements in my modules\. (\d+) Done, (\d+) Partly .*?"
                  r"(\d+) Not done .*?(\d+) Deferred on M6", REPORT.read_text(encoding="utf-8"))
    assert m, "report summary line not found"
    total, done, partly, not_done, deferred = m.groups()
    text = _all_text()
    assert f"{done} of {total} functional requirements done" in text
    fr_chart = next(sh for s in _deck().slides for sh in s.shapes if sh.name == "fr-chart")
    series = {s.name: sum(s.values) for s in fr_chart.chart.plots[0].series}
    assert series == {"Done": int(done), "Partly": int(partly), "Not done": int(not_done),
                      "Deferred on M6": int(deferred)}


def test_test_counts_match_the_report():
    report = REPORT.read_text(encoding="utf-8")
    total = re.search(r"Backend total: (\d+) tests", report).group(1)
    flows = re.search(r"(\d+) flows \(student \d+, lecturer \d+\)", report).group(1)
    specs = re.search(r"(\d+) spec files", report).group(1)
    text = _all_text()
    for n in (total, flows, specs):
        assert re.search(rf"^{n}$", text, re.M), n
    chart = next(sh for s in _deck().slides for sh in s.shapes if sh.name == "test-chart")
    values = list(chart.chart.plots[0].series[0].values)
    # backend unit + API/database + Moodle + live = the backend total; app unit is separate
    assert values[0] + values[2] + values[3] + values[4] == int(total)


def test_all_t103_diagrams_are_in_the_deck_and_nothing_else():
    wanted = {hashlib.sha256(p.read_bytes()).hexdigest() for p in DIAGRAMS.glob("*.png")}
    assert len(wanted) == 11
    found = set()
    for slide in _deck().slides:
        for sh in slide.shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                found.add(hashlib.sha256(sh.image.blob).hexdigest())
    # Only the diagrams: app screenshots are added by hand (test accounts, no face or card).
    assert found == wanted


def test_no_secrets():
    text = _all_text() + "\n".join(
        s.notes_slide.notes_text_frame.text for s in _deck().slides if s.has_notes_slide)
    for marker in ("MOODLE_TOKEN=", "API_KEY=", "SECRET_KEY", "password:", "DEVICE_KEY="):
        assert marker not in text


def test_shapes_stay_on_the_slide():
    deck = _deck()
    for i, slide in enumerate(deck.slides, 1):
        for sh in slide.shapes:
            assert sh.left >= 0 and sh.top >= 0, (i, sh.name)
            assert sh.left + sh.width <= deck.slide_width, (i, sh.name)
            assert sh.top + sh.height <= deck.slide_height, (i, sh.name)
