"""JobEvent model for tracking job progress events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class JobEvent(Base):
    """Represents a progress event for a job."""

    __tablename__ = "job_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (Index("ix_job_events_job_id_timestamp", "job_id", "timestamp"),)
