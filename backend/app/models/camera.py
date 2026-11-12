from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.session import AttendanceSession


class Camera(Base):
    """A camera device at a room's door (FR-408). Online/offline comes from `last_heartbeat_at`."""
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    room: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    # SHA-256 of the device key (NFR-07); null until an admin issues a key
    key_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    key_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="camera")
