"""Synthetic test course for the live AI suite (T82).

Three short, original software-testing notes (no real course material, no copyright)
live in `tests/fixtures/course/*.md`. They are turned into PDFs and indexed through the
real parser → chunker → embedder path, so the live tests and the replay tests run
against a stable, self-contained knowledge base.
"""
from pathlib import Path

from app.services.kb.ingest import MaterialMeta, ingest_file
from app.services.kb.search import Passage

FIXTURE_DIR = Path(__file__).resolve().parent / "course"

# (file stem, human title). Order matters: the citation mapping is by retrieved passage.
DOCS = [
    ("boundary-value-analysis", "Boundary Value Analysis"),
    ("equivalence-partitioning", "Equivalence Partitioning"),
    ("statement-and-branch-coverage", "Statement and Branch Coverage"),
]


def doc_pages(stem: str) -> list[str]:
    """The markdown document split into page-sized blocks on blank lines."""
    text = (FIXTURE_DIR / f"{stem}.md").read_text(encoding="utf-8").strip()
    return [part.strip() for part in text.split("\n\n") if part.strip()]


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


async def index_synthetic_course(db, course_id: int) -> dict[str, int]:
    """Index the three synthetic docs into `course_id`. Returns {stem: material_id}."""
    ids: dict[str, int] = {}
    for stem, title in DOCS:
        meta = MaterialMeta(
            source_key=f"synthetic:{stem}", source="local", file_name=f"{stem}.pdf",
            title=title, section_name="Synthetic test course",
        )
        mat = await ingest_file(db, course_id, meta, make_pdf(doc_pages(stem)))
        await db.flush()
        ids[stem] = mat.id
    await db.commit()
    return ids


def passage_to_dict(p: Passage) -> dict:
    return {
        "chunk_id": p.chunk_id, "material_id": p.material_id, "title": p.title,
        "section_name": p.section_name, "location_type": p.location_type,
        "location_start": p.location_start, "location_end": p.location_end,
        "heading": p.heading, "text": p.text, "score": p.score,
        "vector_similarity": p.vector_similarity,
    }


def passage_from_dict(d: dict) -> Passage:
    return Passage(
        chunk_id=d["chunk_id"], material_id=d["material_id"], title=d["title"],
        section_name=d["section_name"], location_type=d["location_type"],
        location_start=d["location_start"], location_end=d["location_end"],
        heading=d["heading"], text=d["text"], score=d["score"],
        vector_similarity=d["vector_similarity"],
    )
