"""Unit tests for the knowledge base (Module 8). No database, network or LLM needed.

Run from backend/:  python -m pytest tests -q
"""
import io
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.knowledge import MAT_ERROR, MAT_INDEXED, MAT_NO_TEXT, MAT_UNSUPPORTED  # noqa: E402
from app.services.kb.assistant import SOURCE_COURSE, SOURCE_GENERAL, parse_answer  # noqa: E402
from app.services.kb.chunker import chunk_units, count_tokens  # noqa: E402
from app.services.kb.moodle_client import MoodleFile  # noqa: E402
from app.services.kb.parsers import Unit, _repeated_lines, parse_file  # noqa: E402
from app.services.kb.search import Passage  # noqa: E402
from app.services.kb.sync import plan_sync  # noqa: E402


# ── fixtures built in memory ──────────────────────────────────────────────────

def make_pdf(pages: list[str]) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def make_pptx(slides: list[tuple[str, str, str | None]]) -> bytes:
    from pptx import Presentation
    prs = Presentation()
    for title, body, notes in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def make_docx() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("Course overview paragraph that has enough words to be kept as text.")
    doc.add_heading("Equivalence Partitioning", level=1)
    doc.add_paragraph("Divide inputs into classes that the system should treat the same way.")
    doc.add_heading("Boundary Value Analysis", level=1)
    doc.add_paragraph("Test the values at the edges of each equivalence class.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── parsers ───────────────────────────────────────────────────────────────────

def test_pdf_keeps_page_numbers_and_skips_empty_pages():
    data = make_pdf(["Verification checks we built the product right, against the specification.",
                     "", "Validation checks we built the right product, against user needs."])
    result = parse_file("Week 1.pdf", data)
    assert result.status == MAT_INDEXED
    assert result.unit_count == 3
    assert [u.number for u in result.units] == [1, 3]  # page 2 had no text
    assert all(u.location_type == "page" for u in result.units)


def test_pdf_without_text_is_no_text_not_error():
    result = parse_file("PYQ 2018.pdf", make_pdf(["", ""]))
    assert result.status == MAT_NO_TEXT
    assert result.unit_count == 2


def test_pptx_reads_title_body_and_speaker_notes():
    data = make_pptx([("Black-box testing", "Tests behaviour without seeing code", "Mention EP and BVA"),
                      ("White-box testing", "Tests internal structure", None)])
    result = parse_file("Lecture 4.pptx", data)
    assert result.status == MAT_INDEXED
    first = result.units[0]
    assert (first.location_type, first.number, first.heading) == ("slide", 1, "Black-box testing")
    assert "Speaker notes: Mention EP and BVA" in first.text


def test_docx_splits_on_headings():
    result = parse_file("Notes.docx", make_docx())
    headings = [u.heading for u in result.units]
    assert "Equivalence Partitioning" in headings and "Boundary Value Analysis" in headings
    assert all(u.location_type == "section" for u in result.units)


def test_legacy_formats_are_unsupported():
    assert parse_file("old.ppt", b"x").status == MAT_UNSUPPORTED
    assert parse_file("old.doc", b"x").status == MAT_UNSUPPORTED


def test_repeated_header_lines_are_detected():
    pages = [f"Chapter 4\nTopic {i} content line\n(c) Copyright 2012 MSTB" for i in range(10)]
    assert _repeated_lines(pages) == {"Chapter 4", "(c) Copyright 2012 MSTB"}


# ── chunker ───────────────────────────────────────────────────────────────────

def test_short_slides_merge_and_keep_range():
    units = [Unit("slide", i, "word " * 40, f"Slide {i}") for i in range(1, 6)]  # ~50 tokens each
    chunks = chunk_units(units, target=120, max_tokens=200, overlap=0)
    assert (chunks[0].location_start, chunks[0].location_end) == (1, 2)
    assert chunks[-1].location_end == 5
    assert all(c.token_count <= 200 for c in chunks)


def test_long_page_is_split_with_overlap():
    sentences = " ".join(f"Sentence number {i} explains a testing idea in detail." for i in range(60))
    chunks = chunk_units([Unit("page", 7, sentences)], target=100, max_tokens=150, overlap=20)
    assert len(chunks) > 1
    assert all(c.location_start == c.location_end == 7 for c in chunks)
    # the end of one piece reappears at the start of the next
    assert chunks[0].text.split(". ")[-1].split()[0:3] == chunks[1].text.split()[0:3] or \
        chunks[1].text.startswith(chunks[0].text.split(". ")[-1][:20])


def test_count_tokens_is_rough_chars_over_four():
    assert count_tokens("a" * 400) == 100


# ── sync diff ─────────────────────────────────────────────────────────────────

def _mf(module_id: int, name: str, modified: int) -> MoodleFile:
    return MoodleFile(module_id, name, "Week 1", name, "/", f"http://m/{name}", modified, 10, None)


def test_plan_sync_detects_new_changed_and_deleted():
    existing = {
        _mf(1, "a.pdf", 100).source_key: SimpleNamespace(moodle_timemodified=100, status=MAT_INDEXED, source="moodle"),
        _mf(2, "b.pdf", 100).source_key: SimpleNamespace(moodle_timemodified=100, status=MAT_INDEXED, source="moodle"),
        _mf(3, "c.pdf", 100).source_key: SimpleNamespace(moodle_timemodified=100, status=MAT_ERROR, source="moodle"),
        _mf(4, "gone.pdf", 100).source_key: SimpleNamespace(moodle_timemodified=100, status=MAT_INDEXED, source="moodle"),
        "local:x.pdf": SimpleNamespace(moodle_timemodified=None, status=MAT_INDEXED, source="local"),
    }
    moodle = [_mf(1, "a.pdf", 100), _mf(2, "b.pdf", 200), _mf(3, "c.pdf", 100), _mf(5, "new.pdf", 100)]
    new, changed, gone = plan_sync(moodle, existing)
    assert [f.file_name for f in new] == ["new.pdf"]
    assert sorted(f.file_name for f in changed) == ["b.pdf", "c.pdf"]  # modified, and retry after error
    assert gone == [_mf(4, "gone.pdf", 100).source_key]                # local materials are never deleted


# ── answer parsing ────────────────────────────────────────────────────────────

def _passage(n: int) -> Passage:
    return Passage(n, 100 + n, f"Lecture {n}", "Week 4", "slide", n, n + 1, None, f"text {n}", 0.03, 0.7)


def test_parse_answer_maps_citations_in_order_and_drops_invalid():
    raw = "BVA tests edges [2]. It pairs with EP [1][2]. Made up [9]."
    text, citations, source = parse_answer(raw, [_passage(1), _passage(2)])
    assert "[9]" not in text
    assert [c["n"] for c in citations] == [2, 1]
    assert citations[0]["location"] == "slides 2-3" and citations[0]["material_id"] == 102
    assert source == SOURCE_COURSE


def test_uncited_answer_is_general():
    raw = "This isn't covered in your course materials, so here's a general explanation: ..."
    text, citations, source = parse_answer(raw, [_passage(1)])
    assert citations == [] and source == SOURCE_GENERAL
