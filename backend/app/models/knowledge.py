"""Knowledge base for the AI Learning Assistant (Module 8).

kb_materials: one row per course file (from Moodle, or a local folder in dev).
kb_chunks:    retrievable passages of a material, with a 384-d embedding and a
              generated tsvector for keyword search.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Computed, ForeignKey, Index, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base

EMBEDDING_DIM = 384

# Material status values
MAT_PENDING = "pending"
MAT_INDEXED = "indexed"
MAT_NO_TEXT = "no_text"          # PDF without a text layer (no OCR, by design)
MAT_UNSUPPORTED = "unsupported"  # legacy .ppt/.doc
MAT_ERROR = "error"
FINAL_STATUSES = (MAT_INDEXED, MAT_NO_TEXT, MAT_UNSUPPORTED)


class KbMaterial(Base):
    __tablename__ = "kb_materials"
    __table_args__ = (
        UniqueConstraint("course_id", "source_key", name="uq_kb_materials_course_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Stable identity within a course:
    #   "moodle:<cmid>:<filepath><filename>"  or  "local:<relative path>"
    source_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="moodle")  # moodle | local

    # Moodle identity
    moodle_module_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, server_default="/")
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    section_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Week 3"
    mimetype: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    moodle_timemodified: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # unix ts
    content_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=MAT_PENDING)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_count: Mapped[Optional[int]] = mapped_column(nullable=True)  # pages / slides / sections
    chunk_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    indexed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["KbChunk"]] = relationship(
        back_populates="material", cascade="all, delete-orphan", passive_deletes=True
    )


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        Index(
            "ix_kb_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_kb_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(
        ForeignKey("kb_materials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )  # denormalised for filtering
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location_type: Mapped[str] = mapped_column(String(10), nullable=False)  # page | slide | section
    location_start: Mapped[int] = mapped_column(nullable=False)
    location_end: Mapped[int] = mapped_column(nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    token_count: Mapped[int] = mapped_column(nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    tsv = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    material: Mapped["KbMaterial"] = relationship(back_populates="chunks")
