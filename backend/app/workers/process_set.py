"""Main Celery task for processing DJ sets through the fingerprinting pipeline."""

import asyncio
import contextlib
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.websocket import notify_progress
from app.models.job import Job, JobStatus
from app.models.track import Track
from app.models.unidentified import UnidentifiedSegment
from app.services.aggregator import SegmentResult, aggregate_results
from app.services.audio import segment_audio
from app.services.blob_storage import delete_audio, upload_audio
from app.services.description_parser import parse_tracklist
from app.services.fingerprint import identify_segment
from app.services.youtube import download_audio, validate_url
from app.workers.celery_app import celery_app

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

_sync_engine: Any = None
_SyncSessionMaker: Any = None
_CANONICAL_COOKIE_PROBE_TTL_SECONDS = int(os.getenv("CANONICAL_COOKIE_PROBE_TTL_SECONDS", "3600"))
_canonical_cookie_probe_valid_until: datetime | None = None


def _get_sync_session() -> Session:
    """Lazy-init sync engine and return a new session."""
    global _sync_engine, _SyncSessionMaker  # noqa: PLW0603
    if _sync_engine is None:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        else:
            # Cloud: build URL with managed identity token
            host = os.getenv("POSTGRES_HOST")
            db = os.getenv("POSTGRES_DB", "tracklistify")
            if not host:
                raise ValueError("Either DATABASE_URL or POSTGRES_HOST must be set")
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
            user = os.getenv("POSTGRES_USER", "tracklistify-celery-worker")
            sync_url = f"postgresql://{user}:{token}@{host}/{db}?sslmode=require"
        _sync_engine = create_engine(sync_url, pool_pre_ping=True)
        _SyncSessionMaker = sessionmaker(bind=_sync_engine)
    return _SyncSessionMaker()  # type: ignore[no-any-return]


def _update_job_status(
    session: Session,
    job_id: str,
    status: JobStatus,
    progress: int,
    error_message: str | None = None,
) -> None:
    """Update job status in database and notify via WebSocket.

    Args:
        session: SQLAlchemy session
        job_id: Job ID
        status: New job status
        progress: Progress percentage (0-100)
        error_message: Optional error message
    """
    from uuid import UUID

    # Convert string job_id to UUID for querying
    job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
    job = session.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        return

    job.status = status
    job.progress = progress
    if error_message:
        job.error_message = error_message
    if status == JobStatus.COMPLETE:
        job.completed_at = datetime.utcnow()

    session.commit()

    # Notify via WebSocket (run async in sync context)
    asyncio.run(
        notify_progress(
            job_id=job_id,
            status=status.value,
            progress=progress,
            error=error_message,
        )
    )


def _log_event(session: Any, job_id: str, message: str, phase: str, progress: int) -> None:
    """Log a pipeline event to the job_events table."""
    from uuid import UUID

    from app.models.job_event import JobEvent

    job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
    event = JobEvent(
        job_id=job_uuid,
        message=message,
        phase=phase,
        progress=progress,
    )
    session.add(event)
    session.commit()


async def _batch_fingerprint_segments(
    segments: list[dict[str, Any]],
    max_concurrent: int = 10,
) -> list[SegmentResult]:
    """Fingerprint segments in parallel batches.

    Args:
        segments: List of segment metadata from audio.segment_audio
        max_concurrent: Maximum concurrent requests to ACRCloud

    Returns:
        List of SegmentResult objects
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: list[SegmentResult] = []

    async def fingerprint_with_semaphore(segment: dict[str, Any], index: int) -> SegmentResult:
        """Fingerprint a single segment with semaphore limit."""
        async with semaphore:
            match = await identify_segment(segment["path"])

            if match:
                return SegmentResult(
                    segment_index=index,
                    start_ms=segment["start_ms"],
                    end_ms=segment["end_ms"],
                    title=match["title"],
                    artist=match["artist"],
                    album=match["album"],
                    confidence=match["confidence_score"],
                )
            else:
                return SegmentResult(
                    segment_index=index,
                    start_ms=segment["start_ms"],
                    end_ms=segment["end_ms"],
                    title=None,
                    artist=None,
                    album=None,
                    confidence=None,
                )

    # Create tasks for all segments
    tasks = [fingerprint_with_semaphore(segment, index) for index, segment in enumerate(segments)]

    # Run all tasks concurrently with semaphore limiting parallelism
    results = await asyncio.gather(*tasks)

    return list(results)


@celery_app.task  # type: ignore[untyped-decorator]
def process_dj_set(
    job_id: str,
    youtube_url: str,
    confidence_threshold: float = 0.50,
    cookie_blob_ref: str | None = None,
) -> None:
    """Process a DJ set through the complete fingerprinting pipeline.

    Args:
        job_id: Unique job identifier
        youtube_url: YouTube URL of the DJ set
        confidence_threshold: Minimum confidence score for track identification
        cookie_blob_ref: Optional blob reference for job-specific cookie file

    Pipeline steps:
        1. Download audio from YouTube
        2. Upload to Azure Blob Storage
        3. Get YouTube metadata
        4. Parse description for existing tracklist
        5. Segment audio into overlapping windows
        6. Fingerprint segments via ACRCloud (10 parallel)
        7. Aggregate results into clean tracklist
        8. Store tracks and unidentified segments in database
        9. Clean up temporary files

    The task updates job status and progress throughout via WebSocket.
    """
    session = _get_sync_session()
    temp_dir: Path | None = None
    blob_name: str | None = None
    cookie_temp_path: str | None = None

    try:
        global _canonical_cookie_probe_valid_until  # noqa: PLW0603

        # Step 0: Resolve cookie source at execution time
        cookie_source = "none"
        if cookie_blob_ref:
            # Try to retrieve job-specific cookie from blob storage
            from app.services.cookie_manager import (
                get_job_cookie,
                probe_cookie,
                save_canonical_cookie,
            )

            cookie_content = asyncio.run(get_job_cookie(cookie_blob_ref))
            if cookie_content:
                # Validate uploaded cookie in worker to avoid request-path latency.
                is_uploaded_cookie_valid = asyncio.run(probe_cookie(cookie_content))
                if is_uploaded_cookie_valid:
                    # Write to temp file for yt-dlp
                    tmp_fd, cookie_temp_path = tempfile.mkstemp(suffix=".txt")
                    os.write(tmp_fd, cookie_content)
                    os.close(tmp_fd)
                    cookie_source = "uploaded"
                    logger.info("[%s] Using uploaded cookie", job_id)

                    # Uploaded cookie is now verified by probe; promote for reuse.
                    try:
                        asyncio.run(save_canonical_cookie(cookie_content))
                        _canonical_cookie_probe_valid_until = datetime.utcnow() + timedelta(
                            seconds=_CANONICAL_COOKIE_PROBE_TTL_SECONDS
                        )
                    except Exception:
                        logger.warning(
                            "[%s] Failed to promote uploaded cookie to canonical",
                            job_id,
                        )
                else:
                    logger.warning("[%s] Uploaded cookie is stale/invalid, falling back", job_id)
            else:
                logger.warning("[%s] Uploaded cookie not found, trying canonical", job_id)

        if cookie_source == "none":
            # Try canonical cookie
            from app.services.cookie_manager import (
                delete_canonical_cookie,
                get_canonical_cookie,
                probe_cookie,
            )

            canonical_cookie = asyncio.run(get_canonical_cookie())
            if canonical_cookie:
                # Avoid probing canonical cookie on every job; cache successful probe for a TTL.
                now = datetime.utcnow()
                should_probe = (
                    _canonical_cookie_probe_valid_until is None
                    or now >= _canonical_cookie_probe_valid_until
                )
                is_valid = True
                if should_probe:
                    is_valid = asyncio.run(probe_cookie(canonical_cookie))
                    if is_valid:
                        _canonical_cookie_probe_valid_until = now + timedelta(
                            seconds=_CANONICAL_COOKIE_PROBE_TTL_SECONDS
                        )
                    else:
                        _canonical_cookie_probe_valid_until = None

                if is_valid:
                    tmp_fd, cookie_temp_path = tempfile.mkstemp(suffix=".txt")
                    os.write(tmp_fd, canonical_cookie)
                    os.close(tmp_fd)
                    cookie_source = "canonical"
                    logger.info("[%s] Using canonical cookie", job_id)
                else:
                    logger.warning(
                        "[%s] Canonical cookie is stale/invalid, deleting and falling back",
                        job_id,
                    )
                    asyncio.run(delete_canonical_cookie())
                    logger.info(
                        "[%s] No valid cookie available, proceeding without authentication",
                        job_id,
                    )
            else:
                logger.info("[%s] No cookie available, proceeding without authentication", job_id)

        _log_event(session, job_id, f"Cookie source: {cookie_source}", "DOWNLOADING", 2)

        # Step 1: Update status to DOWNLOADING
        _update_job_status(session, job_id, JobStatus.DOWNLOADING, 5)
        _log_event(session, job_id, "Starting audio download...", "DOWNLOADING", 5)
        logger.info("[%s] Starting audio download from %s", job_id, youtube_url)

        # Step 2: Download audio to temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix="tracklistify_"))
        audio_path = temp_dir / "audio.wav"

        asyncio.run(download_audio(youtube_url, str(audio_path), cookie_path=cookie_temp_path))

        # Get file size for logging
        file_size_mb = audio_path.stat().st_size / (1024 * 1024) if audio_path.exists() else 0
        _update_job_status(session, job_id, JobStatus.DOWNLOADING, 10)
        _log_event(session, job_id, f"Audio downloaded ({file_size_mb:.1f} MB)", "DOWNLOADING", 10)
        logger.info("[%s] Audio downloaded (%.1f MB)", job_id, file_size_mb)

        # Step 3: Upload to Azure Blob Storage
        logger.info("[%s] Uploading audio to blob storage...", job_id)
        upload_result = asyncio.run(upload_audio(job_id, str(audio_path)))
        blob_name = f"{job_id}/audio.wav"
        _update_job_status(session, job_id, JobStatus.DOWNLOADING, 15)

        # Log whether we uploaded to cloud or using local mode
        if upload_result and upload_result.startswith("local://"):
            _log_event(session, job_id, "Skipping cloud storage (local mode)", "DOWNLOADING", 15)
        else:
            _log_event(session, job_id, "Audio uploaded to storage", "DOWNLOADING", 15)

        # Step 4: Get YouTube metadata
        _update_job_status(session, job_id, JobStatus.DOWNLOADING, 20)
        metadata = asyncio.run(validate_url(youtube_url, cookie_path=cookie_temp_path))
        video_title = metadata["title"]
        duration_str = metadata["duration"]
        description = metadata["description"]

        _log_event(session, job_id, f'Extracted metadata: "{video_title}"', "DOWNLOADING", 20)

        # Convert duration string to seconds (format: HH:MM:SS or MM:SS)
        duration_parts = duration_str.split(":")
        if len(duration_parts) == 3:
            hours, minutes, seconds = map(int, duration_parts)
            duration_seconds = hours * 3600 + minutes * 60 + seconds
        elif len(duration_parts) == 2:
            minutes, seconds = map(int, duration_parts)
            duration_seconds = minutes * 60 + seconds
        else:
            duration_seconds = 0

        # Update job with metadata
        from uuid import UUID

        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        job = session.query(Job).filter(Job.id == job_uuid).first()
        if job:
            job.video_title = video_title
            job.duration_seconds = duration_seconds
            session.commit()

        # Step 5: Parse description for existing tracklist
        # Note: parsed_tracklist could be used for cross-referencing in future
        parsed_tracklist = parse_tracklist(description)
        _update_job_status(session, job_id, JobStatus.DOWNLOADING, 25)

        # Log tracklist parsing results
        if parsed_tracklist:
            _log_event(
                session,
                job_id,
                f"Parsed description: found {len(parsed_tracklist)} tracks",
                "DOWNLOADING",
                25,
            )
        else:
            _log_event(session, job_id, "No tracklist found in description", "DOWNLOADING", 25)

        # Step 6: Segment audio
        _update_job_status(session, job_id, JobStatus.SEGMENTING, 30)
        _log_event(
            session,
            job_id,
            "Starting audio segmentation (12s windows, 6s hop)...",
            "SEGMENTING",
            30,
        )

        segments_dir = temp_dir / "segments"
        segments = segment_audio(
            input_path=str(audio_path),
            output_dir=str(segments_dir),
            window_seconds=12,
            hop_seconds=6,
        )
        _update_job_status(session, job_id, JobStatus.SEGMENTING, 35)
        _log_event(
            session,
            job_id,
            f"Created {len(segments)} segments for fingerprinting",
            "SEGMENTING",
            35,
        )

        # Step 7: Fingerprint segments (batch with 10 concurrent requests)
        _update_job_status(session, job_id, JobStatus.FINGERPRINTING, 40)
        _log_event(
            session,
            job_id,
            f"Starting track identification ({len(segments)} segments, 10 parallel)...",
            "FINGERPRINTING",
            40,
        )

        # Process segments in chunks to provide progress updates
        all_results = []
        chunk_size = max(len(segments) // 10, 1)
        tracks_found = 0

        for i in range(0, len(segments), chunk_size):
            chunk = segments[i : i + chunk_size]
            chunk_results = asyncio.run(_batch_fingerprint_segments(chunk, max_concurrent=10))
            all_results.extend(chunk_results)
            tracks_found = sum(1 for r in all_results if r.title is not None)
            completed = len(all_results)
            fp_progress = 40 + int((completed / len(segments)) * 40)
            _log_event(
                session,
                job_id,
                f"Identified {completed}/{len(segments)} segments "
                f"({tracks_found} tracks found so far)",
                "FINGERPRINTING",
                fp_progress,
            )
            _update_job_status(session, job_id, JobStatus.FINGERPRINTING, fp_progress)

        fingerprint_results = all_results

        # Final fingerprinting log
        total_matched = sum(1 for r in fingerprint_results if r.title is not None)
        _update_job_status(session, job_id, JobStatus.FINGERPRINTING, 80)
        _log_event(
            session,
            job_id,
            f"Fingerprinting complete: {total_matched}/{len(segments)} segments matched",
            "FINGERPRINTING",
            80,
        )

        # Step 8: Aggregate results
        _update_job_status(session, job_id, JobStatus.AGGREGATING, 85)
        _log_event(
            session, job_id, "Merging results and detecting transitions...", "AGGREGATING", 85
        )

        aggregated_tracks, unidentified_gaps = aggregate_results(
            fingerprint_results, confidence_threshold
        )

        _update_job_status(session, job_id, JobStatus.AGGREGATING, 90)
        _log_event(
            session,
            job_id,
            f"Found {len(aggregated_tracks)} tracks, "
            f"{len(unidentified_gaps)} unidentified segments",
            "AGGREGATING",
            90,
        )

        # Step 9: Cross-reference with parsed description (optional enhancement)
        # For now, we just store the aggregated results
        # Future: match aggregated tracks with parsed_tracklist for validation

        # Step 10: Store tracks in database
        from uuid import UUID

        job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        for aggregated_track in aggregated_tracks:
            track = Track(
                job_id=job_uuid,
                position=aggregated_track.position,
                start_time_ms=aggregated_track.start_ms,
                end_time_ms=aggregated_track.end_ms,
                title=aggregated_track.title,
                artist=aggregated_track.artist,
                album=aggregated_track.album,
                confidence_score=aggregated_track.avg_confidence,
                is_transition=aggregated_track.is_transition,
                is_manual_edit=False,
            )
            session.add(track)

        # Step 11: Store unidentified segments
        for gap in unidentified_gaps:
            unidentified = UnidentifiedSegment(
                job_id=job_uuid,
                start_time_ms=gap.start_ms,
                end_time_ms=gap.end_ms,
                notes=None,
            )
            session.add(unidentified)

        session.commit()
        _update_job_status(session, job_id, JobStatus.AGGREGATING, 95)
        _log_event(session, job_id, "Tracklist saved to database", "AGGREGATING", 95)

        # Step 12: Clean up - delete from Blob Storage
        if blob_name:
            asyncio.run(delete_audio(blob_name))

        # Step 13: Mark job as complete
        _update_job_status(session, job_id, JobStatus.COMPLETE, 100)
        _log_event(session, job_id, "Processing complete!", "COMPLETE", 100)

    except Exception as e:
        # Handle any errors
        error_message = f"{type(e).__name__}: {str(e)}"
        logger.exception("[%s] Task failed: %s", job_id, error_message)
        _update_job_status(session, job_id, JobStatus.FAILED, 0, error_message)

        # Attempt cleanup even on failure
        if blob_name:
            with contextlib.suppress(Exception):
                asyncio.run(delete_audio(blob_name))

    finally:
        # Clean up temp directory
        if temp_dir and temp_dir.exists():
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)

        # Clean up cookie temp file
        if cookie_temp_path:
            with contextlib.suppress(OSError):
                os.unlink(cookie_temp_path)

        # Clean up job-specific cookie from blob storage if it was uploaded
        if cookie_blob_ref:
            from app.services.cookie_manager import delete_job_cookie

            with contextlib.suppress(Exception):
                asyncio.run(delete_job_cookie(cookie_blob_ref))

        session.close()
