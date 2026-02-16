"""Job model for tracking DJ set processing jobs."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.unidentified import UnidentifiedSegment


class JobStatus(enum.Enum):
    """Enum for job processing status."""

    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    SEGMENTING = "SEGMENTING"
    FINGERPRINTING = "FINGERPRINTING"
    AGGREGATING = "AGGREGATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Job(Base):
    """Represents a DJ set processing job."""

    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    youtube_url: Mapped[str] = mapped_column(String, nullable=False)
    video_title: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    confidence_threshold: Mapped[float] = mapped_column(default=0.5, nullable=False)
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.QUEUED, nullable=False)
    progress: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    share_slug: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    tracks: Mapped[list[Track]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    unidentified_segments: Mapped[list[UnidentifiedSegment]] = relationship(
        cascade="all, delete-orphan"
    )
