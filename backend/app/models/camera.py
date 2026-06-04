from typing import Optional, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.session import AttendanceSession


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    room: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="online")  # online | offline
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))

    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="camera")
