# Alembic Migration Setup

This directory contains Alembic database migrations for the Tracklistify application.

## Configuration

### Environment Variables

Alembic is configured to read the database URL from the `DATABASE_URL` environment variable. Make sure this is set before running migrations:

```bash
export DATABASE_URL="postgresql+asyncpg://tracklistify:tracklistify@localhost:5432/tracklistify"
```

Or create a `.env` file in the backend directory (see `.env.example`).

### Async SQLAlchemy Support

The migration environment (`alembic/env.py`) is configured to work with async SQLAlchemy:

- Uses `async_engine_from_config` for creating database connections
- Implements `run_async_migrations()` pattern for async database operations
- All models are imported to ensure they're registered with `Base.metadata`

## Database Schema

The initial migration creates three tables:

### jobs
- Tracks DJ set processing jobs
- Stores YouTube URL, video metadata, status, and progress
- Uses UUID as primary key
- Includes JobStatus enum (QUEUED, DOWNLOADING, SEGMENTING, FINGERPRINTING, AGGREGATING, COMPLETE, FAILED)

### tracks
- Stores identified music tracks from processed DJ sets
- Links to jobs table via foreign key
- Includes track metadata (title, artist, album, confidence score)
- Tracks position and timing information (start_time_ms, end_time_ms)

### unidentified_segments
- Stores segments that couldn't be identified
- Links to jobs table via foreign key
- Includes timing information and optional notes

## Running Migrations

### Apply migrations to the database:
```bash
cd backend
.venv/bin/alembic upgrade head
```

### Create a new migration (autogenerate):
```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "description of changes"
```

### Downgrade migrations:
```bash
cd backend
.venv/bin/alembic downgrade -1  # Go back one migration
.venv/bin/alembic downgrade base  # Revert all migrations
```

### View migration history:
```bash
cd backend
.venv/bin/alembic history
.venv/bin/alembic current
```

## Files

- `alembic.ini` - Main Alembic configuration file
- `alembic/env.py` - Migration environment configuration with async support
- `alembic/versions/` - Directory containing migration scripts
- `alembic/script.py.mako` - Template for generating new migration files

## Initial Migration

The initial migration (`e1c9f0bf9de7_initial_schema.py`) was created manually to match the SQLAlchemy models defined in:
- `app/models/base.py`
- `app/models/job.py`
- `app/models/track.py`
- `app/models/unidentified.py`

All models inherit from the `Base` class defined in `app/models/base.py`.
