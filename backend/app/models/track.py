"""Track model for storing extracted track information from audio files."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class Track(Base):
    """Represents a music track extracted from an audio file."""

    __tablename__ = "tracks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    start_time_ms: Mapped[int] = mapped_column(nullable=False)
    end_time_ms: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(nullable=True)
    artist: Mapped[str | None] = mapped_column(nullable=True)
    album: Mapped[str | None] = mapped_column(nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(nullable=True)
    is_transition: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_manual_edit: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationship back to Job
    job: Mapped[Job] = relationship(back_populates="tracks")
