from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import Student


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    student: Mapped["Student"] = relationship(back_populates="face_embeddings")
