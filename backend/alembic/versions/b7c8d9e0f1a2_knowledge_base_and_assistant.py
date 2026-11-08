"""knowledge_base_and_assistant

Module 8 (AI Learning Assistant):
- kb_materials: one row per course file synced from Moodle (or a local folder in dev)
- kb_chunks: retrievable passages with a 384-d embedding (HNSW) and a tsvector (GIN)
- ai_chat_sessions / ai_chat_messages: per-course student chats
- courses.moodle_course_id: mapping to the Moodle (SPeCTRUM) course

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("moodle_course_id", sa.Integer(), nullable=True))

    op.create_table(
        "kb_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(1024), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="moodle"),
        sa.Column("moodle_module_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False, server_default="/"),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("section_name", sa.String(255), nullable=True),
        sa.Column("mimetype", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("moodle_timemodified", sa.BigInteger(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("unit_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("course_id", "source_key", name="uq_kb_materials_course_source"),
    )
    op.create_index("ix_kb_materials_course_id", "kb_materials", ["course_id"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("kb_materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location_type", sa.String(10), nullable=False),
        sa.Column("location_start", sa.Integer(), nullable=False),
        sa.Column("location_end", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(512), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(heading, '') || ' ' || text)", persisted=True),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_kb_chunks_material_id", "kb_chunks", ["material_id"])
    op.create_index("ix_kb_chunks_course_id", "kb_chunks", ["course_id"])
    op.create_index(
        "ix_kb_chunks_embedding_hnsw", "kb_chunks", ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_kb_chunks_tsv", "kb_chunks", ["tsv"], postgresql_using="gin")

    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_chat_sessions_student_id", "ai_chat_sessions", ["student_id"])
    op.create_index("ix_ai_chat_sessions_course_id", "ai_chat_sessions", ["course_id"])

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=True),
        sa.Column("retrieval_query", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_chat_messages_session_id", "ai_chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("ai_chat_messages")
    op.drop_table("ai_chat_sessions")
    op.drop_table("kb_chunks")
    op.drop_table("kb_materials")
    op.drop_column("courses", "moodle_course_id")
