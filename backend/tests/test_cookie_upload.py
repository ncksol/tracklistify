"""Tests for cookie upload behavior in jobs API and worker."""

import os
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, UploadFile
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.api.jobs import create_job, get_job_status
from app.api.jobs import router as jobs_router
from app.db import get_session
from app.models.base import Base
from app.models.job import Job, JobStatus
from app.models.job_event import JobEvent


@pytest_asyncio.fixture
async def async_session():
    """Create an async in-memory DB session for API handler tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sync_session():
    """Create a sync in-memory DB session for worker task tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest_asyncio.fixture
async def client(async_session: AsyncSession):
    """Create an httpx client for jobs router integration tests."""
    app = FastAPI()
    app.include_router(jobs_router)

    async def override_get_session():
        yield async_session

    app.dependency_overrides[get_session] = override_get_session

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def valid_cookie() -> bytes:
    return (
        b"# Netscape HTTP Cookie File\n"
        b".youtube.com\tTRUE\t/\tTRUE\t2147483647\tVISITOR_INFO1_LIVE\tvalid_token_123\n"
    )


@patch("app.api.jobs.process_dj_set")
@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_json_backward_compat(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    mock_process: MagicMock,
    client: httpx.AsyncClient,
):
    """JSON job creation remains backward compatible over HTTP."""
    mock_validate.return_value = None
    mock_process.delay = MagicMock(return_value=None)

    response = await client.post(
        "/api/jobs",
        json={
            "url": "https://youtube.com/watch?v=test123",
            "force": False,
            "confidence_threshold": 0.5,
        },
    )

    assert response.status_code == 201
    assert response.json()["youtube_url"] == "https://youtube.com/watch?v=test123"
    assert response.json()["status"] == "QUEUED"
    assert mock_process.delay.called
    assert mock_process.delay.call_args[0][3] is None
    # JSON requests should not pass a cookie to validate_url
    assert mock_validate.call_args.kwargs.get("cookie_path") is None


@patch("app.api.jobs.save_job_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.process_dj_set")
@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_multipart_cookie_saved_with_final_job_id(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    mock_process: MagicMock,
    mock_save_job: AsyncMock,
    async_session: AsyncSession,
    valid_cookie: bytes,
):
    """Multipart upload saves cookie directly under final job ID."""
    mock_validate.return_value = None
    mock_process.delay = MagicMock(return_value=None)
    mock_save_job.return_value = "saved-cookie-ref"

    response = await create_job(
        raw_request=MagicMock(),
        url="https://youtube.com/watch?v=test456",
        force=False,
        confidence_threshold=0.6,
        cookie_file=UploadFile(filename="cookies.txt", file=BytesIO(valid_cookie)),
        content_type="multipart/form-data; boundary=test",
        session=async_session,
    )

    assert response.status == "QUEUED"
    assert mock_save_job.call_count == 1
    assert mock_save_job.call_args.args[0] == str(response.id)
    assert mock_process.delay.call_args[0][3] == "saved-cookie-ref"
    # validate_url must receive cookie_path so validation uses the uploaded cookie
    assert mock_validate.call_args.kwargs.get("cookie_path") is not None


@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_cookie_guardrails_reject_non_netscape_format(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    async_session: AsyncSession,
):
    """Cookie upload rejects files that are not Netscape cookie format."""
    mock_validate.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await create_job(
            raw_request=MagicMock(),
            url="https://youtube.com/watch?v=test-guardrails",
            force=False,
            confidence_threshold=0.5,
            cookie_file=UploadFile(filename="cookies.txt", file=BytesIO(b"not-a-cookie-file")),
            content_type="multipart/form-data; boundary=test",
            session=async_session,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Cookie file must be Netscape format"


@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_cookie_guardrails_reject_invalid_extension(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    async_session: AsyncSession,
    valid_cookie: bytes,
):
    """Non-.txt uploaded cookie file is rejected with HTTP 400."""
    mock_validate.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await create_job(
            raw_request=MagicMock(),
            url="https://youtube.com/watch?v=test-guardrails",
            force=False,
            confidence_threshold=0.5,
            cookie_file=UploadFile(filename="cookies.json", file=BytesIO(valid_cookie)),
            content_type="multipart/form-data; boundary=test",
            session=async_session,
        )

    assert exc_info.value.status_code == 400


@patch("app.workers.process_set._log_event")
@patch("app.services.cookie_manager.save_canonical_cookie", new_callable=AsyncMock)
@patch("app.services.cookie_manager.probe_cookie", new_callable=AsyncMock)
@patch("app.services.cookie_manager.get_job_cookie", new_callable=AsyncMock)
@patch("app.workers.process_set.download_audio", new_callable=AsyncMock)
@patch("app.workers.process_set._get_sync_session")
def test_worker_uses_uploaded_cookie_without_probing(
    mock_get_session: MagicMock,
    mock_download: AsyncMock,
    mock_get_job_cookie: AsyncMock,
    mock_probe_cookie: AsyncMock,
    mock_save_canonical_cookie: AsyncMock,
    mock_log_event: MagicMock,
    sync_session: Session,
    valid_cookie: bytes,
):
    """Worker uses uploaded cookie directly without probe and promotes to canonical."""
    from app.workers import process_set as process_set_module
    from app.workers.process_set import process_dj_set

    process_set_module._canonical_cookie_probe_valid_until = None

    job = Job(
        id=uuid4(),
        youtube_url="https://youtube.com/watch?v=worker_uploaded",
        status=JobStatus.QUEUED,
        progress=0,
    )
    sync_session.add(job)
    sync_session.commit()
    sync_session.refresh(job)

    mock_get_session.return_value = sync_session
    mock_get_job_cookie.return_value = valid_cookie
    mock_download.side_effect = Exception("stop after cookie resolution")

    process_dj_set(str(job.id), job.youtube_url, cookie_blob_ref="job/cookies.txt")

    # Cookie is used directly (no probe_cookie call)
    assert mock_download.call_args.kwargs["cookie_path"] is not None
    assert not mock_probe_cookie.called
    # Cookie is promoted to canonical
    assert mock_save_canonical_cookie.called


@patch("app.workers.process_set._log_event")
@patch("app.services.cookie_manager.probe_cookie", new_callable=AsyncMock)
@patch("app.services.cookie_manager.get_canonical_cookie", new_callable=AsyncMock)
@patch("app.services.cookie_manager.delete_canonical_cookie", new_callable=AsyncMock)
@patch("app.workers.process_set.download_audio", new_callable=AsyncMock)
@patch("app.workers.process_set._get_sync_session")
def test_worker_deletes_stale_canonical_cookie(
    mock_get_session: MagicMock,
    mock_download: AsyncMock,
    mock_delete_canonical: AsyncMock,
    mock_get_canonical: AsyncMock,
    mock_probe: AsyncMock,
    mock_log_event: MagicMock,
    sync_session: Session,
):
    """Worker deletes stale canonical cookie and continues fallback path."""
    from app.workers import process_set as process_set_module
    from app.workers.process_set import process_dj_set

    process_set_module._canonical_cookie_probe_valid_until = None

    job = Job(
        id=uuid4(),
        youtube_url="https://youtube.com/watch?v=worker_test",
        status=JobStatus.QUEUED,
        progress=0,
    )
    sync_session.add(job)
    sync_session.commit()
    sync_session.refresh(job)

    mock_get_session.return_value = sync_session
    mock_get_canonical.return_value = b"stale cookie content"
    mock_probe.return_value = False
    mock_download.side_effect = Exception("stop after cookie resolution")

    process_dj_set(str(job.id), job.youtube_url, cookie_blob_ref=None)

    assert mock_probe.called
    assert mock_delete_canonical.called


@pytest.mark.asyncio
async def test_get_job_status_marks_stalled_segmenting_job_failed(async_session: AsyncSession):
    """SEGMENTING job with stale events is marked FAILED with guidance."""
    job = Job(
        youtube_url="https://youtube.com/watch?v=stalled-segmenting",
        status=JobStatus.SEGMENTING,
        progress=30,
        created_at=datetime.utcnow() - timedelta(hours=1),
    )
    async_session.add(job)
    await async_session.commit()
    await async_session.refresh(job)

    async_session.add(
        JobEvent(
            job_id=job.id,
            message="Starting audio segmentation (12s windows, 6s hop)...",
            phase="SEGMENTING",
            progress=30,
            timestamp=datetime.utcnow() - timedelta(minutes=25),
        )
    )
    await async_session.commit()

    response = await get_job_status(job_id=job.id, session=async_session)
    assert response.status == "FAILED"
    assert response.error_message is not None
    assert "stalled during segmentation" in response.error_message

    result = await async_session.execute(
        select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.timestamp.desc())
    )
    latest_event = result.scalars().first()
    assert latest_event is not None
    assert latest_event.phase == "FAILED"


@pytest.mark.asyncio
async def test_get_job_status_keeps_recent_segmenting_job_active(async_session: AsyncSession):
    """SEGMENTING job with recent events remains in-progress."""
    job = Job(
        youtube_url="https://youtube.com/watch?v=active-segmenting",
        status=JobStatus.SEGMENTING,
        progress=30,
    )
    async_session.add(job)
    await async_session.commit()
    await async_session.refresh(job)

    async_session.add(
        JobEvent(
            job_id=job.id,
            message="Starting audio segmentation (12s windows, 6s hop)...",
            phase="SEGMENTING",
            progress=30,
            timestamp=datetime.utcnow() - timedelta(minutes=2),
        )
    )
    await async_session.commit()

    response = await get_job_status(job_id=job.id, session=async_session)
    assert response.status == "SEGMENTING"
    assert response.error_message is None
