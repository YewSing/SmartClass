"""Ingest one course file: parse -> chunk -> embed -> store.

Independent of where the bytes come from (Moodle sync or a local folder in dev).
Re-ingesting identical bytes is a no-op (same sha256), so syncs are cheap.
"""
import hashlib
from dataclasses import dataclass
from pathlib import PurePath

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import now_myt
from app.models.knowledge import (
    FINAL_STATUSES, MAT_ERROR, MAT_INDEXED, KbChunk, KbMaterial,
)
from app.services.kb.chunker import chunk_units
from app.services.kb.embedder import embed_passages
from app.services.kb.parsers import parse_file


@dataclass
class MaterialMeta:
    """Where a file came from. `source_key` must be stable for the same file."""
    source_key: str
    source: str               # moodle | local
    file_name: str
    file_path: str = "/"
    title: str | None = None
    section_name: str | None = None
    moodle_module_id: int | None = None
    file_url: str | None = None
    mimetype: str | None = None
    size_bytes: int | None = None
    moodle_timemodified: int | None = None


def embedding_text(title: str, heading: str | None, text: str) -> str:
    """What we actually embed: the passage plus its document title and heading.

    A slide that just says "Advantages: fast, cheap" is meaningless alone; with
    "Boundary Value Analysis" in front, its vector lands near BVA questions.
    """
    head = f"{title}\n{heading}\n" if heading and heading != title else f"{title}\n"
    return head + text


async def ingest_file(db: AsyncSession, course_id: int, meta: MaterialMeta, data: bytes) -> KbMaterial:
    sha = hashlib.sha256(data).hexdigest()
    material = (await db.execute(
        select(KbMaterial).where(KbMaterial.course_id == course_id, KbMaterial.source_key == meta.source_key)
    )).scalar_one_or_none()

    if material is None:
        material = KbMaterial(course_id=course_id, source_key=meta.source_key, source=meta.source,
                              file_name=meta.file_name, title="")
        db.add(material)

    # Metadata always refreshes (a lecturer may rename a section without changing the file)
    material.file_name = meta.file_name
    material.file_path = meta.file_path
    material.title = meta.title or PurePath(meta.file_name).stem
    material.section_name = meta.section_name
    material.moodle_module_id = meta.moodle_module_id
    material.file_url = meta.file_url
    material.mimetype = meta.mimetype
    material.size_bytes = meta.size_bytes if meta.size_bytes is not None else len(data)
    material.moodle_timemodified = meta.moodle_timemodified

    if material.content_sha256 == sha and material.status in FINAL_STATUSES:
        await db.flush()
        return material  # unchanged content: nothing to re-index

    material.content_sha256 = sha
    try:
        parsed = parse_file(meta.file_name, data)
        await db.flush()  # make sure material.id exists
        await db.execute(delete(KbChunk).where(KbChunk.material_id == material.id))

        material.unit_count = parsed.unit_count
        material.error_text = parsed.detail
        material.status = parsed.status
        material.chunk_count = 0

        if parsed.status == MAT_INDEXED:
            chunks = chunk_units(parsed.units)
            vectors = await embed_passages([embedding_text(material.title, c.heading, c.text) for c in chunks])
            db.add_all([
                KbChunk(
                    material_id=material.id, course_id=course_id, chunk_index=i, text=c.text,
                    location_type=c.location_type, location_start=c.location_start,
                    location_end=c.location_end, heading=(c.heading or "")[:512] or None,
                    token_count=c.token_count, embedding=vec,
                )
                for i, (c, vec) in enumerate(zip(chunks, vectors))
            ])
            material.chunk_count = len(chunks)
        material.indexed_at = now_myt()
    except Exception as exc:  # a corrupt file must not stop the rest of the sync
        material.status = MAT_ERROR
        material.error_text = f"{type(exc).__name__}: {exc}"[:2000]
        material.chunk_count = 0

    await db.flush()
    return material
