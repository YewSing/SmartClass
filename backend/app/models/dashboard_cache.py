from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DashboardCache(Base):
    """Read-only Moodle snapshot scoped to the authenticated Moodle user."""
    __tablename__ = "dashboard_moodle_cache"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
