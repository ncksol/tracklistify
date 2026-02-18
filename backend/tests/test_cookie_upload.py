"""Tests for cookie upload behavior in jobs API and worker."""

import os
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.api.jobs import JobCreateRequest, create_job
from app.models.base import Base
from app.models.job import Job, JobStatus


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
    """Create a sync in-memory DB session for worker task test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    session = session_maker()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def valid_cookie() -> bytes:
    return (
        b"# Netscape HTTP Cookie File\n"
        b".youtube.com\tTRUE\t/\tTRUE\t2147483647\tVISITOR_INFO1_LIVE\tvalid_token_123\n"
    )


@pytest.fixture
def invalid_cookie() -> bytes:
    return (
        b"# Netscape HTTP Cookie File\n"
        b".youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_INFO1_LIVE\texpired_token\n"
    )


@patch("app.api.jobs.process_dj_set")
@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_json_backward_compat(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    mock_process: MagicMock,
    async_session: AsyncSession,
):
    """JSON job creation remains backward compatible."""
    mock_validate.return_value = None
    mock_process.delay = MagicMock(return_value=None)

    response = await create_job(
        request=JobCreateRequest(
            url="https://youtube.com/watch?v=test123",
            force=False,
            confidence_threshold=0.5,
        ),
        content_type="application/json",
        session=async_session,
    )

    assert response.youtube_url == "https://youtube.com/watch?v=test123"
    assert response.status == "QUEUED"
    assert mock_process.delay.called
    assert mock_process.delay.call_args[0][3] is None


@patch("app.services.cookie_manager.delete_job_cookie", new_callable=AsyncMock)
@patch("app.services.cookie_manager.get_job_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.save_job_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.save_canonical_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.probe_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.process_dj_set")
@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_valid_cookie_promotion(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    mock_process: MagicMock,
    mock_probe: AsyncMock,
    mock_save_canonical: AsyncMock,
    mock_save_job: AsyncMock,
    mock_get_job_cookie: AsyncMock,
    mock_delete_job_cookie: AsyncMock,
    async_session: AsyncSession,
    valid_cookie: bytes,
):
    """Valid uploaded cookie is saved for the job and promoted to canonical."""
    mock_validate.return_value = None
    mock_probe.return_value = True
    mock_get_job_cookie.return_value = valid_cookie
    mock_save_job.side_effect = ["temp-job/cookies.txt", "final-job/cookies.txt"]
    mock_process.delay = MagicMock(return_value=None)

    response = await create_job(
        url="https://youtube.com/watch?v=test456",
        force=False,
        confidence_threshold=0.6,
        cookie_file=UploadFile(filename="cookies.txt", file=BytesIO(valid_cookie)),
        content_type="multipart/form-data; boundary=test",
        session=async_session,
    )

    assert response.status == "QUEUED"
    assert mock_probe.called
    assert mock_save_job.call_count == 2
    assert mock_save_canonical.called
    assert mock_delete_job_cookie.called
    assert mock_process.delay.called
    assert mock_process.delay.call_args[0][3] == "final-job/cookies.txt"


@patch("app.api.jobs.save_job_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.save_canonical_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.probe_cookie", new_callable=AsyncMock)
@patch("app.api.jobs.process_dj_set")
@patch("app.api.jobs.validate_url", new_callable=AsyncMock)
@patch("app.api.jobs._check_rate_limit")
@pytest.mark.asyncio
async def test_invalid_cookie_fallback(
    mock_rate_limit: MagicMock,
    mock_validate: AsyncMock,
    mock_process: MagicMock,
    mock_probe: AsyncMock,
    mock_save_canonical: AsyncMock,
    mock_save_job: AsyncMock,
    async_session: AsyncSession,
    invalid_cookie: bytes,
):
    """Invalid/stale uploaded cookie falls back and still creates the job."""
    mock_validate.return_value = None
    mock_probe.return_value = False
    mock_process.delay = MagicMock(return_value=None)

    response = await create_job(
        url="https://youtube.com/watch?v=test789",
        force=False,
        confidence_threshold=0.5,
        cookie_file=UploadFile(filename="cookies.txt", file=BytesIO(invalid_cookie)),
        content_type="multipart/form-data; boundary=test",
        session=async_session,
    )

    assert response.status == "QUEUED"
    assert not mock_save_job.called
    assert not mock_save_canonical.called
    assert mock_process.delay.call_args[0][3] is None


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
            url="https://youtube.com/watch?v=test-guardrails",
            force=False,
            confidence_threshold=0.5,
            cookie_file=UploadFile(filename="cookies.json", file=BytesIO(valid_cookie)),
            content_type="multipart/form-data; boundary=test",
            session=async_session,
        )

    assert exc_info.value.status_code == 400


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
    from app.workers.process_set import process_dj_set

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
