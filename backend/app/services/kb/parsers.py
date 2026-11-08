"""Turn a course file into text units that keep their location (page / slide / section).

The location is what later becomes a citation such as "Week 3 slides, slide 12",
so every unit carries the number it came from.
"""
import io
import re
from dataclasses import dataclass, field
from pathlib import PurePath

from app.models.knowledge import MAT_INDEXED, MAT_NO_TEXT, MAT_UNSUPPORTED

SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".docx"}

# A PDF page with fewer characters than this is treated as having no text layer
# (a scanned page or a picture-only slide).
_MIN_PAGE_CHARS = 40


@dataclass
class Unit:
    location_type: str  # page | slide | section
    number: int         # 1-based page / slide / section number
    text: str
    heading: str | None = None


@dataclass
class ParseResult:
    status: str                       # indexed | no_text | unsupported
    units: list[Unit] = field(default_factory=list)
    unit_count: int = 0               # total pages / slides / sections in the file
    detail: str | None = None


def clean_text(text: str) -> str:
    """Collapse runs of spaces, drop empty lines, keep line breaks (they separate bullets)."""
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def parse_file(file_name: str, data: bytes) -> ParseResult:
    ext = PurePath(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return ParseResult(MAT_UNSUPPORTED, detail=f"{ext or 'no extension'} files are not supported")
    parser = {".pdf": _parse_pdf, ".pptx": _parse_pptx, ".docx": _parse_docx}[ext]
    units, unit_count = parser(data)
    if not units:
        return ParseResult(MAT_NO_TEXT, unit_count=unit_count, detail="No readable text (scanned or image-only)")
    return ParseResult(MAT_INDEXED, units=units, unit_count=unit_count)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _parse_pdf(data: bytes) -> tuple[list[Unit], int]:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [clean_text(page.get_text("text")) for page in doc]
        page_count = doc.page_count

    boilerplate = _repeated_lines(pages)
    units: list[Unit] = []
    for i, page_text in enumerate(pages, start=1):
        text = "\n".join(line for line in page_text.split("\n") if line not in boilerplate)
        if len(text) < _MIN_PAGE_CHARS:
            continue
        units.append(Unit("page", i, text, heading=_first_line(text)))
    return units, page_count


def _repeated_lines(pages: list[str], min_pages: int = 5, share: float = 0.4) -> set[str]:
    """Running headers/footers ("Chapter 4", "(c) Copyright 2012 MSTB") repeat on most
    pages. They add noise to every chunk and make useless headings, so drop them."""
    if len(pages) < min_pages:
        return set()
    counts: dict[str, int] = {}
    for page in pages:
        for line in set(page.split("\n")):
            counts[line] = counts.get(line, 0) + 1
    return {line for line, n in counts.items() if n >= share * len(pages)}


# ── PPTX ──────────────────────────────────────────────────────────────────────

def _parse_pptx(data: bytes) -> tuple[list[Unit], int]:
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    units: list[Unit] = []
    for i, slide in enumerate(prs.slides, start=1):
        title = None
        if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
            title = clean_text(slide.shapes.title.text_frame.text) or None

        parts: list[str] = []
        for shape in slide.shapes:
            parts.extend(_shape_texts(shape))
        if slide.has_notes_slide:
            notes = clean_text(slide.notes_slide.notes_text_frame.text)
            if notes:
                parts.append(f"Speaker notes: {notes}")

        text = clean_text("\n".join(parts))
        if text:
            units.append(Unit("slide", i, text, heading=title or _first_line(text)))
    return units, len(prs.slides)


def _shape_texts(shape) -> list[str]:
    """Text from a shape, including grouped shapes and table cells."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        return [t for s in shape.shapes for t in _shape_texts(s)]
    if getattr(shape, "has_table", False) and shape.has_table:
        rows = [" | ".join(c.text.strip() for c in row.cells) for row in shape.table.rows]
        return ["\n".join(rows)]
    if shape.has_text_frame and shape.text_frame.text.strip():
        return [shape.text_frame.text]
    return []


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _parse_docx(data: bytes) -> tuple[list[Unit], int]:
    """Split a Word document into sections at each heading paragraph."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(data))
    sections: list[tuple[str | None, list[str]]] = [(None, [])]

    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(block, doc)
            text = para.text.strip()
            if not text:
                continue
            if (para.style.name or "").lower().startswith(("heading", "title")):
                sections.append((text, []))
            else:
                sections[-1][1].append(text)
        elif tag == "tbl":
            table = Table(block, doc)
            rows = [" | ".join(c.text.strip() for c in row.cells) for row in table.rows]
            sections[-1][1].append("\n".join(rows))

    units: list[Unit] = []
    for heading, paras in sections:
        text = clean_text("\n".join(([heading] if heading else []) + paras))
        if text:
            units.append(Unit("section", len(units) + 1, text, heading=heading or _first_line(text)))
    return units, len(units)


def _first_line(text: str, limit: int = 120) -> str | None:
    line = text.split("\n", 1)[0].strip()
    return line[:limit] or None
