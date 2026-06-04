from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    old_val: Mapped[Optional[str]] = mapped_column(Text)
    new_val: Mapped[Optional[str]] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    actor: Mapped["User"] = relationship(back_populates="audit_logs", foreign_keys=[actor_id])
