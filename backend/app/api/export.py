"""Export API endpoints for tracklists."""

import secrets
from typing import TYPE_CHECKING, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.job import Job

if TYPE_CHECKING:
    from app.models.track import Track
    from app.models.unidentified import UnidentifiedSegment

router = APIRouter(prefix="/api/jobs", tags=["export"])
share_router = APIRouter(prefix="/api/share", tags=["share"])


def ms_to_timestamp(ms: int) -> str:
    """
    Convert milliseconds to HH:MM:SS timestamp format.

    Args:
        ms: Time in milliseconds

    Returns:
        str: Formatted timestamp (HH:MM:SS)
    """
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class ExportTrack(BaseModel):
    """Track data for export."""

    position: int
    start_time_ms: int
    end_time_ms: int | None
    artist: str | None
    title: str | None
    confidence_score: float | None = None


class ExportUnidentifiedSegment(BaseModel):
    """Unidentified segment data for export."""

    start_time_ms: int
    end_time_ms: int
    notes: str | None


class ExportResponse(BaseModel):
    """JSON export response schema."""

    job_id: UUID
    title: str | None
    url: str
    duration_seconds: int | None
    tracks: list[ExportTrack]


class ShareResponse(BaseModel):
    """Response for share link generation."""

    slug: str
    url: str


@router.get("/{job_id}/export", response_model=None)
async def export_tracklist(
    job_id: UUID,
    format: str = Query(default="json", pattern="^(text|json)$"),
    session: AsyncSession = Depends(get_session),
) -> Response | ExportResponse:
    """
    Export tracklist in specified format.

    Supports both plain text and JSON export formats.

    Args:
        job_id: UUID of the job
        format: Export format - 'text' or 'json' (default: 'json')
        session: Database session

    Returns:
        Response: Plain text or JSON response based on format parameter

    Raises:
        HTTPException: 404 if job not found
    """
    # Load job with relationships
    stmt = (
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.tracks), selectinload(Job.unidentified_segments))
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if format == "text":
        return _export_as_text(job)
    else:
        return _export_as_json(job)


def _export_as_text(job: Job) -> Response:
    """
    Export tracklist as plain text.

    Format:
    - Tracks: "01. [00:05:30] Artist - Title"
    - Unidentified: "-- [00:15:00 - 00:17:30] Unidentified"

    Args:
        job: Job instance with loaded tracks and unidentified segments

    Returns:
        Response: Plain text response
    """
    lines = []

    # Combine and sort all segments by start time
    all_items: list[tuple[str, Track | UnidentifiedSegment]] = []

    for track in job.tracks:
        all_items.append(("track", track))

    for segment in job.unidentified_segments:
        all_items.append(("unidentified", segment))

    all_items.sort(key=lambda x: x[1].start_time_ms)

    # Format each item
    for item_type, item in all_items:
        if item_type == "track":
            track = cast("Track", item)
            timestamp = ms_to_timestamp(track.start_time_ms)
            artist = track.artist or "Unknown Artist"
            title = track.title or "Unknown Title"
            line = f"{track.position:02d}. [{timestamp}] {artist} - {title}"
            lines.append(line)
        else:
            segment = cast("UnidentifiedSegment", item)
            start_ts = ms_to_timestamp(segment.start_time_ms)
            end_ts = ms_to_timestamp(segment.end_time_ms)
            line = f"-- [{start_ts} - {end_ts}] Unidentified"
            lines.append(line)

    content = "\n".join(lines)
    return Response(content=content, media_type="text/plain")


def _export_as_json(job: Job) -> ExportResponse:
    """
    Export tracklist as JSON.

    Includes job metadata and ordered tracks array.

    Args:
        job: Job instance with loaded tracks and unidentified segments

    Returns:
        ExportResponse: Structured JSON export
    """
    # Sort tracks by start_time_ms
    sorted_tracks = sorted(job.tracks, key=lambda t: t.start_time_ms)

    tracks = [
        ExportTrack(
            position=track.position,
            start_time_ms=track.start_time_ms,
            end_time_ms=track.end_time_ms,
            artist=track.artist,
            title=track.title,
            confidence_score=track.confidence_score,
        )
        for track in sorted_tracks
    ]

    return ExportResponse(
        job_id=job.id,
        title=job.video_title,
        url=job.youtube_url,
        duration_seconds=job.duration_seconds,
        tracks=tracks,
    )


@router.post("/{job_id}/share")
async def generate_share_link(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ShareResponse:
    """
    Generate a shareable link for a job's tracklist.

    If a share slug already exists for this job, returns the existing one.
    Otherwise, generates a new unique slug.

    Args:
        job_id: UUID of the job
        session: Database session

    Returns:
        ShareResponse: Contains the slug and full share URL

    Raises:
        HTTPException: 404 if job not found
    """
    # Load job
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Return existing slug if available
    if job.share_slug:
        return ShareResponse(slug=job.share_slug, url=f"/share/{job.share_slug}")

    # Generate new unique slug
    max_attempts = 10
    for _ in range(max_attempts):
        slug = secrets.token_urlsafe(8)
        # Check if slug already exists
        check_stmt = select(Job).where(Job.share_slug == slug)
        check_result = await session.execute(check_stmt)
        if not check_result.scalar_one_or_none():
            job.share_slug = slug
            await session.commit()
            return ShareResponse(slug=slug, url=f"/share/{slug}")

    # If we couldn't generate a unique slug after max_attempts
    raise HTTPException(
        status_code=500, detail="Failed to generate unique share link"
    )


@share_router.get("/{slug}")
async def get_shared_tracklist(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> ExportResponse:
    """
    Retrieve a tracklist by share slug.

    Returns the same data format as the /api/jobs/{job_id}/export endpoint.

    Args:
        slug: Share slug to look up
        session: Database session

    Returns:
        ExportResponse: Tracklist data in JSON format

    Raises:
        HTTPException: 404 if slug not found
    """
    # Load job by share_slug with relationships
    stmt = (
        select(Job)
        .where(Job.share_slug == slug)
        .options(selectinload(Job.tracks), selectinload(Job.unidentified_segments))
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Share link not found")

    return _export_as_json(job)
