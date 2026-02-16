"""Tests for track CRUD endpoints."""

import os
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.job import Job, JobStatus
from app.models.track import Track

# Set required environment variables before importing app modules
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from app.api.tracks import router as tracks_router
from app.db import get_session


# Create a test FastAPI app with only the tracks router
def create_test_app():
    """Create a minimal FastAPI app for testing tracks endpoints."""
    test_app = FastAPI()
    test_app.include_router(tracks_router)
    return test_app


app = create_test_app()


@pytest_asyncio.fixture
async def test_db():
    """Create test database with SQLite in-memory."""
    # Create in-memory SQLite database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session maker
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield async_session

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(test_db):
    """Provide a test database session."""
    async with test_db() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_db):
    """Create an httpx async client with database override."""

    async def override_get_session():
        async with test_db() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_job(session):
    """Create a sample job in COMPLETE status."""
    job = Job(
        youtube_url="https://www.youtube.com/watch?v=test123",
        video_title="Test DJ Set",
        duration_seconds=3600,
        status=JobStatus.COMPLETE,
        progress=100,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_tracks(session, sample_job):
    """Create sample tracks for testing."""
    tracks = [
        Track(
            job_id=sample_job.id,
            position=1,
            start_time_ms=0,
            end_time_ms=180000,
            title="Track One",
            artist="Artist One",
            album="Album One",
            confidence_score=0.95,
            is_transition=False,
            is_manual_edit=False,
        ),
        Track(
            job_id=sample_job.id,
            position=2,
            start_time_ms=180000,
            end_time_ms=360000,
            title="Track Two",
            artist="Artist Two",
            confidence_score=0.87,
            is_transition=False,
            is_manual_edit=False,
        ),
    ]
    for track in tracks:
        session.add(track)
    await session.commit()

    # Refresh tracks to get IDs
    for track in tracks:
        await session.refresh(track)

    return tracks


@pytest.mark.asyncio
async def test_patch_track_update_title(client, sample_job, sample_tracks):
    """Test PATCH track: update title returns updated track with is_manual_edit=True."""
    track = sample_tracks[0]

    response = await client.patch(
        f"/api/jobs/{sample_job.id}/tracks/{track.id}",
        json={"title": "Updated Track Title"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Track Title"
    assert data["is_manual_edit"] is True
    assert data["id"] == str(track.id)
    # Other fields should remain unchanged
    assert data["artist"] == "Artist One"
    assert data["start_time_ms"] == 0
    assert data["end_time_ms"] == 180000


@pytest.mark.asyncio
async def test_patch_track_update_multiple_fields(client, sample_job, sample_tracks):
    """Test PATCH track: update multiple fields, all updated."""
    track = sample_tracks[0]

    response = await client.patch(
        f"/api/jobs/{sample_job.id}/tracks/{track.id}",
        json={
            "title": "New Title",
            "artist": "New Artist",
            "start_time_ms": 1000,
            "end_time_ms": 200000,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["artist"] == "New Artist"
    assert data["start_time_ms"] == 1000
    assert data["end_time_ms"] == 200000
    assert data["is_manual_edit"] is True


@pytest.mark.asyncio
async def test_patch_track_nonexistent_track(client, sample_job):
    """Test PATCH track: 404 for nonexistent track."""
    nonexistent_track_id = uuid4()

    response = await client.patch(
        f"/api/jobs/{sample_job.id}/tracks/{nonexistent_track_id}",
        json={"title": "Should Fail"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Track not found"


@pytest.mark.asyncio
async def test_patch_track_nonexistent_job(client, sample_tracks):
    """Test PATCH track: 404 for nonexistent job."""
    nonexistent_job_id = uuid4()
    track = sample_tracks[0]

    response = await client.patch(
        f"/api/jobs/{nonexistent_job_id}/tracks/{track.id}",
        json={"title": "Should Fail"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_delete_track_removes_track(client, session, sample_job, sample_tracks):
    """Test DELETE track: removes track and returns 204."""
    track = sample_tracks[0]

    response = await client.delete(f"/api/jobs/{sample_job.id}/tracks/{track.id}")

    assert response.status_code == 204
    assert response.content == b""

    # Verify track was deleted from database
    stmt = select(Track).where(Track.id == track.id)
    result = await session.execute(stmt)
    deleted_track = result.scalar_one_or_none()
    assert deleted_track is None


@pytest.mark.asyncio
async def test_delete_track_nonexistent_track(client, sample_job):
    """Test DELETE track: 404 for nonexistent track."""
    nonexistent_track_id = uuid4()

    response = await client.delete(
        f"/api/jobs/{sample_job.id}/tracks/{nonexistent_track_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Track not found"


@pytest.mark.asyncio
async def test_delete_track_nonexistent_job(client, sample_tracks):
    """Test DELETE track: 404 for nonexistent job."""
    nonexistent_job_id = uuid4()
    track = sample_tracks[0]

    response = await client.delete(f"/api/jobs/{nonexistent_job_id}/tracks/{track.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_post_track_creates_new_track(client, session, sample_job):
    """Test POST track: creates new track with is_manual_edit=True."""
    response = await client.post(
        f"/api/jobs/{sample_job.id}/tracks",
        json={
            "position": 3,
            "start_time_ms": 360000,
            "end_time_ms": 540000,
            "title": "Manually Added Track",
            "artist": "Manual Artist",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Manually Added Track"
    assert data["artist"] == "Manual Artist"
    assert data["position"] == 3
    assert data["start_time_ms"] == 360000
    assert data["end_time_ms"] == 540000
    assert data["is_manual_edit"] is True
    assert data["is_transition"] is False
    assert "id" in data

    # Verify track was created in database
    from uuid import UUID

    track_id = UUID(data["id"])
    stmt = select(Track).where(Track.id == track_id)
    result = await session.execute(stmt)
    created_track = result.scalar_one_or_none()
    assert created_track is not None
    assert created_track.title == "Manually Added Track"
    assert created_track.is_manual_edit is True


@pytest.mark.asyncio
async def test_post_track_nonexistent_job(client):
    """Test POST track: 404 for nonexistent job."""
    nonexistent_job_id = uuid4()

    response = await client.post(
        f"/api/jobs/{nonexistent_job_id}/tracks",
        json={
            "position": 1,
            "start_time_ms": 0,
            "end_time_ms": 100000,
            "title": "Should Fail",
            "artist": "Should Fail",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


@pytest.mark.asyncio
async def test_patch_track_partial_update(client, sample_job, sample_tracks):
    """Test PATCH track: partial update only changes specified fields."""
    track = sample_tracks[1]
    original_artist = track.artist
    original_start_time = track.start_time_ms

    response = await client.patch(
        f"/api/jobs/{sample_job.id}/tracks/{track.id}",
        json={"title": "Only Title Changed"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Only Title Changed"
    # Verify other fields unchanged
    assert data["artist"] == original_artist
    assert data["start_time_ms"] == original_start_time
    assert data["is_manual_edit"] is True


@pytest.mark.asyncio
async def test_patch_track_marks_as_manual_edit(client, sample_job, sample_tracks):
    """Test PATCH track: ensures is_manual_edit is set to True after any update."""
    track = sample_tracks[0]
    # Verify track initially has is_manual_edit=False
    assert track.is_manual_edit is False

    response = await client.patch(
        f"/api/jobs/{sample_job.id}/tracks/{track.id}",
        json={"artist": "Updated Artist"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_manual_edit"] is True
