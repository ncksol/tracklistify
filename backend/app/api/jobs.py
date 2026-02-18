"""Jobs API endpoints."""

import contextlib
import logging
import os
import random
import tempfile
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.job import Job, JobStatus
from app.models.job_event import JobEvent
from app.models.track import Track
from app.models.unidentified import UnidentifiedSegment
from app.services.cookie_manager import save_job_cookie
from app.services.youtube import validate_url
from app.workers.process_set import process_dj_set

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


# Simple in-memory rate limiter for job submissions
_submission_timestamps: list[datetime] = []
_MAX_SUBMISSIONS_PER_HOUR = 5
_RATE_LIMIT_WINDOW = timedelta(hours=1)


def _check_rate_limit() -> None:
    """
    Check if rate limit is exceeded for job submissions.

    Prunes old timestamps and enforces max 5 submissions per hour.

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    now = datetime.now()
    cutoff = now - _RATE_LIMIT_WINDOW

    # Prune old timestamps
    _submission_timestamps[:] = [ts for ts in _submission_timestamps if ts > cutoff]

    # Check limit
    if len(_submission_timestamps) >= _MAX_SUBMISSIONS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. Maximum {_MAX_SUBMISSIONS_PER_HOUR} "
                "job submissions per hour."
            ),
        )

    # Record this submission
    _submission_timestamps.append(now)


# Request schemas
class JobCreateRequest(BaseModel):
    """Request schema for creating a new job."""

    url: str
    force: bool = False
    confidence_threshold: float = 0.50


# Cookie upload constants
_MAX_COOKIE_SIZE_BYTES = 1024 * 1024  # 1 MB
_ALLOWED_COOKIE_EXTENSIONS = {".txt"}


def _looks_like_netscape_cookie(content: bytes) -> bool:
    """Check whether uploaded content appears to be Netscape cookie format."""
    first_line = content.splitlines()[0].strip() if content else b""
    return first_line.startswith(b"# Netscape HTTP Cookie File")


async def _validate_cookie_file(cookie_file: UploadFile) -> bytes:
    """Validate and read uploaded cookie file.

    Args:
        cookie_file: Uploaded cookie file

    Returns:
        Cookie file content as bytes

    Raises:
        HTTPException: 400 if validation fails
    """
    # Check file extension
    if not cookie_file.filename:
        raise HTTPException(status_code=400, detail="Cookie file must have a filename")

    file_ext = "." + cookie_file.filename.rsplit(".", 1)[-1].lower()
    if file_ext not in _ALLOWED_COOKIE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Cookie file must be a .txt file, got: {file_ext}",
        )

    # Read and check size
    cookie_content = await cookie_file.read()
    if len(cookie_content) > _MAX_COOKIE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Cookie file too large (max {_MAX_COOKIE_SIZE_BYTES / 1024:.0f} KB)",
        )

    if len(cookie_content) == 0:
        raise HTTPException(status_code=400, detail="Cookie file is empty")

    if not _looks_like_netscape_cookie(cookie_content):
        raise HTTPException(
            status_code=400,
            detail="Cookie file must be Netscape format",
        )

    return cookie_content


def _generate_placeholder_waveform(job_id: UUID, duration_seconds: int) -> list[float]:
    """
    Generate placeholder waveform data.

    Creates one peak value per second of audio, with random amplitudes
    between 0.3 and 1.0. Uses job_id as seed for consistency.

    Args:
        job_id: UUID of the job (used as random seed)
        duration_seconds: Duration of the audio in seconds

    Returns:
        List of normalized peak values (0.0 to 1.0)
    """
    # Seed random generator with job_id for consistent results
    rng = random.Random(str(job_id))

    # Generate one peak per second
    peaks = [rng.uniform(0.3, 1.0) for _ in range(duration_seconds)]

    return peaks


# Response schemas
class JobResponse(BaseModel):
    """Response schema for job details."""

    id: UUID
    youtube_url: str
    video_title: str | None
    duration_seconds: int | None
    confidence_threshold: float
    status: str
    progress: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class JobWithCountResponse(JobResponse):
    """Response schema for job details with track count."""

    track_count: int


class JobListResponse(BaseModel):
    """Response schema for paginated job list."""

    jobs: list[JobWithCountResponse]
    total: int
    page: int
    per_page: int


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


class UnidentifiedSegmentResponse(BaseModel):
    """Response schema for unidentified segment details."""

    id: UUID
    start_time_ms: int
    end_time_ms: int
    notes: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class TracklistResponse(BaseModel):
    """Response schema for job tracklist."""

    job_id: UUID
    tracks: list[TrackResponse]
    unidentified_segments: list[UnidentifiedSegmentResponse]


class WaveformResponse(BaseModel):
    """Response schema for waveform data."""

    peaks: list[float]
    duration_seconds: int
    sample_rate: int

    class Config:
        """Pydantic config."""

        from_attributes = True


class JobEventResponse(BaseModel):
    """Response schema for job event details."""

    id: str
    job_id: str
    timestamp: str
    message: str
    phase: str
    progress: int


class JobEventsResponse(BaseModel):
    """Response schema for job events list."""

    events: list[JobEventResponse]


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    session: AsyncSession = Depends(get_session),
) -> JobListResponse:
    """
    List all jobs with pagination.

    Returns jobs ordered by created_at DESC with track counts.

    Args:
        page: Page number (1-indexed)
        per_page: Number of jobs per page
        session: Database session

    Returns:
        JobListResponse: Paginated list of jobs with metadata
    """
    # Calculate offset
    offset = (page - 1) * per_page

    # Create subquery to count tracks per job
    track_count_subquery = (
        select(Track.job_id, func.count(Track.id).label("track_count"))
        .group_by(Track.job_id)
        .subquery()
    )

    # Query jobs with track counts
    stmt = (
        select(
            Job,
            func.coalesce(track_count_subquery.c.track_count, 0).label("track_count"),
        )
        .outerjoin(track_count_subquery, Job.id == track_count_subquery.c.job_id)
        .order_by(Job.created_at.desc())
        .limit(per_page)
        .offset(offset)
    )

    result = await session.execute(stmt)
    rows = result.all()

    # Get total count
    count_stmt = select(func.count()).select_from(Job)
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()

    # Build response
    jobs = [
        JobWithCountResponse(
            id=job.id,
            youtube_url=job.youtube_url,
            video_title=job.video_title,
            duration_seconds=job.duration_seconds,
            confidence_threshold=job.confidence_threshold,
            status=job.status.value,
            progress=job.progress,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at,
            track_count=track_count,
        )
        for job, track_count in rows
    ]

    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    raw_request: Request,
    request: JobCreateRequest | None = None,
    url: str | None = Form(None),
    force: bool = Form(False),
    confidence_threshold: float = Form(0.50),
    cookie_file: UploadFile | None = File(None),
    content_type: str | None = Header(default=None, alias="Content-Type"),
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """
    Create a new DJ set processing job.

    Accepts both JSON and multipart/form-data requests:
    - JSON: Standard request with JobCreateRequest schema
    - Multipart: url, force, confidence_threshold as form fields,
                 optional cookie_file as file upload

    Validates the YouTube URL and checks if a completed job already exists
    for the same URL. If found, returns the existing job. Otherwise, creates
    a new job and enqueues it for processing.

    Args:
        request: JSON request body (optional, for JSON requests)
        url: YouTube URL (for multipart requests)
        force: Force reanalysis flag (for multipart requests)
        confidence_threshold: Minimum confidence score (for multipart requests)
        cookie_file: Optional YouTube cookie file upload
        session: Database session

    Returns:
        JobResponse: Created or existing job details

    Raises:
        HTTPException: 400 if URL validation fails or cookie invalid,
                       429 if rate limit exceeded
    """
    # Check rate limit
    _check_rate_limit()

    # Determine request type using Content-Type (boundary-safe for multipart)
    normalized_content_type = (content_type or "").lower()
    is_multipart = normalized_content_type.startswith("multipart/form-data")
    job_cookie_blob_ref: str | None = None
    cookie_content_to_save: bytes | None = None

    if is_multipart:
        # Multipart request
        if url is None:
            raise HTTPException(status_code=400, detail="url field is required")
        job_url = url
        job_force = force
        job_confidence_threshold = confidence_threshold

        # Handle optional cookie file upload
        if cookie_file and cookie_file.filename:
            cookie_content_to_save = await _validate_cookie_file(cookie_file)
    else:
        # JSON request
        if request is None:
            try:
                request = JobCreateRequest.model_validate(await raw_request.json())
            except ValidationError as e:
                raise HTTPException(status_code=422, detail=e.errors()) from e
            except ValueError as e:
                raise HTTPException(status_code=400, detail="JSON request body is required") from e
        job_url = request.url
        job_force = request.force
        job_confidence_threshold = request.confidence_threshold
        cookie_content_to_save = None

    # Validate YouTube URL (use uploaded cookie if available)
    cookie_temp_path: str | None = None
    try:
        if cookie_content_to_save:
            tmp_fd, cookie_temp_path = tempfile.mkstemp(suffix=".txt")
            os.write(tmp_fd, cookie_content_to_save)
            os.close(tmp_fd)
        await validate_url(job_url, cookie_path=cookie_temp_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    finally:
        if cookie_temp_path:
            with contextlib.suppress(OSError):
                os.unlink(cookie_temp_path)

    # Check cache: if a COMPLETE job exists for this URL, return it (unless force reanalyse)
    if not job_force:
        stmt = select(Job).where(
            Job.youtube_url == job_url,
            Job.status == JobStatus.COMPLETE,
        )
        result = await session.execute(stmt)
        existing_job = result.scalar_one_or_none()

        if existing_job:
            return JobResponse(
                id=existing_job.id,
                youtube_url=existing_job.youtube_url,
                video_title=existing_job.video_title,
                duration_seconds=existing_job.duration_seconds,
                confidence_threshold=existing_job.confidence_threshold,
                status=existing_job.status.value,
                progress=existing_job.progress,
                error_message=existing_job.error_message,
                created_at=existing_job.created_at,
                completed_at=existing_job.completed_at,
            )

    # Create new job with QUEUED status
    new_job = Job(
        youtube_url=job_url,
        confidence_threshold=job_confidence_threshold,
        status=JobStatus.QUEUED,
        progress=0,
    )
    session.add(new_job)
    await session.commit()
    await session.refresh(new_job)

    # Save uploaded cookie under final job ID (single write, no temp-blob rename window)
    if cookie_content_to_save:
        try:
            job_cookie_blob_ref = await save_job_cookie(str(new_job.id), cookie_content_to_save)
        except ValueError:
            logger.warning("Cookie storage unavailable, falling back to saved/no cookie")
            job_cookie_blob_ref = None

    # Enqueue Celery task for processing
    process_dj_set.delay(
        str(new_job.id),
        job_url,
        job_confidence_threshold,
        job_cookie_blob_ref,
    )

    return JobResponse(
        id=new_job.id,
        youtube_url=new_job.youtube_url,
        video_title=new_job.video_title,
        duration_seconds=new_job.duration_seconds,
        confidence_threshold=new_job.confidence_threshold,
        status=new_job.status.value,
        progress=new_job.progress,
        error_message=new_job.error_message,
        created_at=new_job.created_at,
        completed_at=new_job.completed_at,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """
    Get job status and details.

    Args:
        job_id: UUID of the job
        session: Database session

    Returns:
        JobResponse: Job details including status, progress, and error if failed

    Raises:
        HTTPException: 404 if job not found
    """
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        id=job.id,
        youtube_url=job.youtube_url,
        video_title=job.video_title,
        duration_seconds=job.duration_seconds,
        confidence_threshold=job.confidence_threshold,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get("/{job_id}/tracklist", response_model=TracklistResponse)
async def get_job_tracklist(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> TracklistResponse:
    """
    Get the ordered tracklist for a completed job.

    Includes both tracks and unidentified segments, sorted by start_time_ms.

    Args:
        job_id: UUID of the job
        session: Database session

    Returns:
        TracklistResponse: Tracklist with tracks and unidentified segments

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

    # Sort tracks by start_time_ms
    sorted_tracks = sorted(job.tracks, key=lambda t: t.start_time_ms)

    # Sort unidentified segments by start_time_ms
    sorted_unidentified = sorted(job.unidentified_segments, key=lambda u: u.start_time_ms)

    return TracklistResponse(
        job_id=job.id,
        tracks=[TrackResponse.model_validate(track) for track in sorted_tracks],
        unidentified_segments=[
            UnidentifiedSegmentResponse.model_validate(segment) for segment in sorted_unidentified
        ],
    )


@router.get("/{job_id}/waveform", response_model=WaveformResponse)
async def get_job_waveform(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> WaveformResponse:
    """
    Get waveform data for audio visualization.

    Returns a downsampled waveform as JSON for frontend visualization.
    Currently returns placeholder data; will be replaced with real FFmpeg-based
    peak extraction later.

    Args:
        job_id: UUID of the job
        session: Database session

    Returns:
        WaveformResponse: Waveform data with normalized peaks, duration, and sample rate

    Raises:
        HTTPException: 404 if job not found or not COMPLETE
    """
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status.value != "COMPLETE":
        raise HTTPException(status_code=404, detail="Waveform only available for completed jobs")

    if job.duration_seconds is None:
        raise HTTPException(status_code=404, detail="Job duration not available")

    # Generate placeholder waveform data
    peaks = _generate_placeholder_waveform(job_id, job.duration_seconds)

    return WaveformResponse(
        peaks=peaks,
        duration_seconds=job.duration_seconds,
        sample_rate=1,  # 1 sample per second for placeholder
    )


@router.get("/{job_id}/events", response_model=JobEventsResponse)
async def get_job_events(
    job_id: UUID,
    after: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> JobEventsResponse:
    """
    Get activity log events for a job, optionally filtered by timestamp.

    Returns events ordered by timestamp ascending, with optional filtering
    to get only events after a specific timestamp.

    Args:
        job_id: UUID of the job
        after: Optional ISO 8601 timestamp to filter events after
        session: Database session

    Returns:
        JobEventsResponse: List of job events

    Raises:
        HTTPException: 404 if job not found
    """
    # Verify job exists
    job_stmt = select(Job).where(Job.id == job_id)
    job_result = await session.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Build events query
    query = select(JobEvent).where(JobEvent.job_id == job_id)

    if after:
        after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
        query = query.where(JobEvent.timestamp > after_dt)

    query = query.order_by(JobEvent.timestamp.asc())
    result = await session.execute(query)
    events = result.scalars().all()

    return JobEventsResponse(
        events=[
            JobEventResponse(
                id=str(event.id),
                job_id=str(event.job_id),
                timestamp=event.timestamp.isoformat(),
                message=event.message,
                phase=event.phase,
                progress=event.progress,
            )
            for event in events
        ]
    )


@router.delete(
    "/{job_id}/unidentified/{segment_id}",
    status_code=204,
)
async def delete_unidentified_segment(
    job_id: UUID,
    segment_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an unidentified segment."""
    stmt = select(UnidentifiedSegment).where(
        UnidentifiedSegment.id == segment_id,
        UnidentifiedSegment.job_id == job_id,
    )
    result = await session.execute(stmt)
    segment = result.scalar_one_or_none()

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    await session.delete(segment)
    await session.commit()


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a job and all its related data."""
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await session.delete(job)
    await session.commit()
