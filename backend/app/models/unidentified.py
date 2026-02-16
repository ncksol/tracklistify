"""UnidentifiedSegment model for storing unidentified audio segments."""

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UnidentifiedSegment(Base):
    """Represents an unidentified segment in a DJ mix that couldn't be matched."""

    __tablename__ = "unidentified_segments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    start_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
