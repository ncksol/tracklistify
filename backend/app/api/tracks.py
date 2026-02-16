"""Tracks API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.job import Job
from app.models.track import Track

router = APIRouter(prefix="/api/jobs/{job_id}/tracks", tags=["tracks"])


# Request schemas
class TrackUpdateRequest(BaseModel):
    """Request schema for updating a track."""

    artist: str | None = None
    title: str | None = None
    start_time_ms: int | None = None
    end_time_ms: int | None = None


class TrackCreateRequest(BaseModel):
    """Request schema for creating a track."""

    position: int
    start_time_ms: int
    end_time_ms: int
    title: str
    artist: str


# Response schemas
class TrackResponse(BaseModel):
    """Response schema for track details."""

    id: UUID
    position: int
    start_time_ms: int
    end_time_ms: int | None
    title: str | None
    artist: str | None
    album: str | None
    confidence_score: float | None
    is_transition: bool
    is_manual_edit: bool

    class Config:
        """Pydantic config."""

        from_attributes = True


@router.patch("/{track_id}", response_model=TrackResponse)
async def update_track(
    job_id: UUID,
    track_id: UUID,
    track_update: TrackUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> TrackResponse:
    """
    Update track fields.

    Sets is_manual_edit = True when any field is updated.

    Args:
        job_id: UUID of the job
        track_id: UUID of the track
        track_update: Track fields to update
        session: Database session

    Returns:
        TrackResponse: Updated track details

    Raises:
        HTTPException: 404 if job or track not found
    """
    # Verify job exists
    job_stmt = select(Job).where(Job.id == job_id)
    job_result = await session.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get track
    track_stmt = select(Track).where(Track.id == track_id, Track.job_id == job_id)
    track_result = await session.execute(track_stmt)
    track = track_result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Update fields if provided
    if track_update.artist is not None:
        track.artist = track_update.artist
    if track_update.title is not None:
        track.title = track_update.title
    if track_update.start_time_ms is not None:
        track.start_time_ms = track_update.start_time_ms
    if track_update.end_time_ms is not None:
        track.end_time_ms = track_update.end_time_ms

    # Mark as manual edit
    track.is_manual_edit = True

    await session.commit()
    await session.refresh(track)

    return TrackResponse.model_validate(track)


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    job_id: UUID,
    track_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """
    Delete a track (false positive removal).

    Args:
        job_id: UUID of the job
        track_id: UUID of the track
        session: Database session

    Raises:
        HTTPException: 404 if job or track not found
    """
    # Verify job exists
    job_stmt = select(Job).where(Job.id == job_id)
    job_result = await session.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get track
    track_stmt = select(Track).where(Track.id == track_id, Track.job_id == job_id)
    track_result = await session.execute(track_stmt)
    track = track_result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Delete track
    await session.delete(track)
    await session.commit()


@router.post("", response_model=TrackResponse, status_code=status.HTTP_201_CREATED)
async def create_track(
    job_id: UUID,
    track_create: TrackCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> TrackResponse:
    """
    Manually add a track (fill unidentified gap).

    Sets is_manual_edit = True.

    Args:
        job_id: UUID of the job
        track_create: Track data to create
        session: Database session

    Returns:
        TrackResponse: Created track details

    Raises:
        HTTPException: 404 if job not found
    """
    # Verify job exists
    job_stmt = select(Job).where(Job.id == job_id)
    job_result = await session.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create new track
    new_track = Track(
        job_id=job_id,
        position=track_create.position,
        start_time_ms=track_create.start_time_ms,
        end_time_ms=track_create.end_time_ms,
        title=track_create.title,
        artist=track_create.artist,
        is_manual_edit=True,
    )

    session.add(new_track)
    await session.commit()
    await session.refresh(new_track)

    return TrackResponse.model_validate(new_track)
