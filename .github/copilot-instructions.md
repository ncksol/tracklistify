# Copilot Instructions — Tracklistify

## What This Is

Web app that takes a YouTube DJ set URL, extracts audio, runs sliding-window audio fingerprinting via ACRCloud, and returns an ordered tracklist with timestamps. Python backend + Next.js frontend monorepo. Single user, Azure-hosted.

## Architecture

```
[Browser] → [Next.js Frontend] → [FastAPI Backend] → [Celery + Redis] → [Worker]
                                                                            │
                                                        ┌──────────────────┼──────────────────┐
                                                        ▼                  ▼                  ▼
                                                  [yt-dlp]          [FFmpeg]          [ACRCloud API]
                                                        │                                     │
                                                        ▼                                     ▼
                                               [Azure Blob]                        [Result Aggregator]
                                               (temp audio)                               │
                                                                                          ▼
                                                                                    [PostgreSQL]
```

- **Frontend** (`frontend/`): Next.js 14 App Router, TypeScript strict, Tailwind CSS, Wavesurfer.js, Vitest
- **Backend** (`backend/`): Python 3.12+, FastAPI (async), Celery + Redis, SQLAlchemy, pytest
- **Infra** (`infra/`): Bicep templates, Azure Container Apps, UK South region

### Core Processing Pipeline

1. Validate YouTube URL via `yt-dlp --get-title`
2. Download audio → Azure Blob temp container
3. Segment audio into **12-second windows with 6-second hop** (50% overlap)
4. Batch-send segments to ACRCloud (10 parallel, within rate limits)
5. Aggregate results: merge consecutive matches, detect transitions, confidence threshold >70%, gap handling, fuzzy dedup
6. Cross-reference with parsed YouTube description tracklist
7. Store final tracklist in PostgreSQL, delete temp audio

### Key Entities

- **Job**: A submitted YouTube video with processing status (QUEUED → DOWNLOADING → SEGMENTING → FINGERPRINTING → AGGREGATING → COMPLETE/FAILED)
- **Track**: A detected track with position, timestamps, artist, title, confidence score
- **UnidentifiedSegment**: Gaps where fingerprinting couldn't identify a track

## Build & Test

```bash
# Frontend
cd frontend
npm install
npm run dev          # dev server
npm run build        # production build
npm run lint         # ESLint + Prettier
npx vitest           # run all tests
npx vitest run src/components/TrackRow.test.tsx  # single test file

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload    # dev server
ruff check .                      # lint
ruff format .                     # format
mypy .                            # type check
pytest                            # run all tests
pytest tests/test_aggregator.py   # single test file
pytest tests/test_aggregator.py::test_merge_consecutive -v  # single test

# Docker (full stack)
docker-compose up    # runs frontend, backend, PostgreSQL, Redis
```

## Conventions

### From Project Constitution (`docs/constitution.md`)

- **YAGNI religiously** — no abstractions until the second use case demands them. No abstract base classes, factories, or strategy patterns unless two concrete implementations exist.
- **Functions over classes** when state isn't needed.
- **No `utils` files** — rethink the design instead.
- **Max 3 levels of directory nesting** without justification.
- **All secrets via environment variables** — zero hardcoded secrets, tokens, or credentials in source.
- **Type safety enforced** — TypeScript `strict: true` (no `any` without justification), Python type hints on all function signatures.
- **Zero warnings policy** — warnings are errors in CI.
- **Pin all dependency versions** exactly (not ranges).
- **Comments explain WHY, not WHAT** — delete comments that restate the code.
- **Conventional commits** for commit messages.
- **Before adding a dependency**: can it be done in ≤50 lines with stdlib? If yes, do that.

### Code Style

- **Frontend**: ESLint + Prettier (`frontend/eslint.config.js`)
- **Backend**: Ruff linter + formatter (configured in `backend/pyproject.toml`)
- **Python type checking**: mypy (configured in `backend/pyproject.toml`)

### Testing

- Test critical paths: audio segmentation, fingerprint aggregation/merging, track deduplication, transition detection, description parsing.
- Prefer integration tests over isolated unit tests.
- Don't test pure display/formatting.

### Azure

- Default region: **UK South**. Only use Sweden Central if a service isn't available in UK South.
- Infrastructure defined in Bicep templates under `infra/`.

## Specs & Planning

- `docs/specs/spec.md` — feature specification with user stories and acceptance criteria
- `docs/specs/plan.md` — architecture, tech decisions, data model, dependency justifications
- `docs/specs/tasks.md` — phased task breakdown with dependency graph
- `docs/constitution.md` — project principles and quality gates
