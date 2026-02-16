# Implementation Plan: Tracklistify

**Feature**: `tracklistify` | **Date**: 2026-02-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification + prior architecture research

## Summary

Web app that accepts YouTube DJ set URLs, extracts audio, runs sliding-window audio fingerprinting via ACRCloud Broadcast Monitoring, and presents an ordered tracklist as an interactive waveform timeline. Python backend handles the heavy audio processing; Next.js frontend provides the interactive UI. Single user, Azure-hosted.

## Technical Context

**Frontend**: TypeScript 5.x (strict), Next.js 14+ (App Router), Tailwind CSS, Wavesurfer.js
**Backend**: Python 3.12+, FastAPI (async), Celery + Redis (job queue)
**Fingerprinting**: ACRCloud Broadcast Monitoring API
**Audio Tools**: yt-dlp (YouTube extraction), FFmpeg (segmentation), pydub (manipulation)
**Storage**: PostgreSQL (job metadata, tracklists), Redis (job queue + result caching), Azure Blob Storage (temporary audio files)
**Testing**: Vitest (frontend), pytest (backend)
**Target Platform**: Azure Container Apps (UK South) — containerised backend + workers, static frontend
**Performance Goals**: Process a 2-hour set in 5-15 minutes; UI interactions under 200ms
**Constraints**: ACRCloud cost ~$2-6 per 2-hour set (~1,200 API calls). Primary operating cost.
**Scale/Scope**: Single user, personal tool. Dozens of sets, not thousands.

## Constitution Check

*GATE: Pre-research check.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ⚠️ WATCH | Two-language stack (Python + TypeScript). Justified: Python audio ecosystem (librosa, pydub, numpy) has no viable JS equivalent. Celery is the simplest reliable job queue for long-running tasks. |
| II. Security by Default | ✅ PASS | ACRCloud key, Redis password, DB credentials all via env vars. YouTube URL validated before processing. Azure Blob uses SAS tokens. |
| III. Type Safety & Linting | ✅ PASS | TypeScript strict on frontend. Python type hints + mypy on backend. ESLint + Prettier + Ruff from day one. |
| IV. Test What Matters | ✅ PASS | Critical paths: audio segmentation logic, fingerprint result aggregation/merging, track deduplication, transition detection. Display: optional. |
| V. Ship Fast, Fix Fast | ✅ PASS | MVP = US1 only (submit URL → get tracklist). No editing, export, or history. |
| VI. Minimal Dependencies | ⚠️ WATCH | More deps than typical — justified individually below. |
| VII. Documentation as Code | ✅ PASS | README with setup instructions. API contracts via FastAPI auto-generated OpenAPI. |
| VIII. Azure, UK South | ✅ PASS | Container Apps + Managed PostgreSQL + Azure Cache for Redis + Blob Storage, all UK South. No services requiring Sweden. |

### Dependency Justifications

| Dependency | Why | Alternative Rejected |
|------------|-----|---------------------|
| **Next.js 14** | SSR submission page + client-side interactive timeline. Single frontend project. | CRA: no SSR. Vite: viable but Next gives routing + SSR free. |
| **Wavesurfer.js** | Waveform visualisation with clickable track regions. Killer UX feature. | Custom canvas: months of work for inferior result. |
| **Tailwind CSS** | Rapid styling, no custom CSS architecture needed. | Styled-components: more complexity for a solo project. |
| **FastAPI** | Async Python API with auto-generated OpenAPI docs, clean typing. | Flask: no async. Django: too heavy. Express: wrong language for audio processing. |
| **Celery + Redis** | Reliable async job queue for 5-15 minute processing tasks. | Bull/BullMQ: would require Node workers, losing Python audio ecosystem. Background threads: unreliable for long tasks. |
| **yt-dlp** | Industry standard YouTube audio extraction. Weekly releases. | youtube-dl: abandoned. pytube: unreliable. |
| **FFmpeg** | Audio segmentation and format conversion. No alternative. | — |
| **pydub** | Higher-level audio manipulation (when FFmpeg CLI is too low-level). | Raw FFmpeg for everything: more complex code. |
| **ACRCloud** | 70M+ track database. Broadcast Monitoring handles mixed/DJ audio with pitch shift, EQ, overlap. | Shazam: no API. AudD: smaller catalogue. Dejavu/Chromaprint: requires building own fingerprint DB (that's a company, not a feature). |
| **PostgreSQL** | Job metadata, tracklists, caching. Managed service on Azure. | SQLite: no concurrent access from API + workers. |
| **Azure Blob Storage** | Temporary audio file storage (1.2GB per 2-hour WAV). Delete after processing. | Local filesystem: doesn't survive container restarts. |

### Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected |
|-----------|------------|------------------------------|
| Two-language stack (Python + TS) | Python's audio processing ecosystem (pydub, librosa, numpy, FFmpeg bindings) has no JS equivalent. The backend is fundamentally an audio processing pipeline. | All-JS: no mature audio fingerprinting or processing libraries. All-Python: Django/Jinja templates can't deliver the interactive waveform timeline UX. |

## Architecture

### System Overview

```
[Browser] → [Next.js Frontend] → [FastAPI Backend] → [Celery + Redis Queue] → [Worker]
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

### The Core Challenge

DJ sets are adversarial to track identification:
- **Beatmatched transitions** — two tracks playing simultaneously for 30-90 seconds
- **EQ manipulation** — bass swapped between tracks, highs/mids filtered
- **Effects** — reverb, delay, flangers, loops
- **Tempo adjustment** — tracks pitched up/down 2-8% from original BPM
- **Unreleased/white labels** — tracks that don't exist in any fingerprint database
- **Acapellas over instrumentals** — mashups that match neither source

Every architectural decision flows from these constraints.

### Sliding Window Strategy

- **Window size**: 12 seconds — long enough for reliable fingerprint match, short enough for timestamp precision
- **Hop size**: 6 seconds — 50% overlap ensures track boundaries aren't missed
- **For a 2-hour set**: ~1,200 segments
- **Concurrency**: Batch 10 segments in parallel to ACRCloud (within rate limits)

Why 12 seconds? Below 8s, match rates drop sharply on mixed audio. Above 15s, you lose timestamp precision and risk windows containing two blended tracks.

### Result Aggregation (The Secret Sauce)

Raw fingerprint results are noisy. Aggregation logic:

1. **Merge consecutive matches** — segments 40-55 all identify "Track X" → collapse to single entry with start/end timestamps
2. **Detect transitions** — segments 53-57 identify both Track X and Track Y → crossfade zone. Mark with `is_transition` flag
3. **Confidence thresholding** — discard matches below ~70% confidence to avoid phantom matches
4. **Gap handling** — 3+ consecutive unmatched segments → flag as "Unidentified" with timestamp range
5. **Deduplication** — same track under different metadata (remix vs original, different releases) → fuzzy string matching on title/artist

### Processing Pipeline

```
1. POST /api/jobs {url}
   → Validate URL (yt-dlp --get-title)
   → Check cache (processed this URL before?)
   → Create job record (status: QUEUED)
   → Enqueue Celery task
   → Return job ID + WebSocket channel

2. Celery Worker:
   a. Download audio → Azure Blob temp container
   b. Extract YouTube metadata (title, description, comments)
   c. Parse description for existing tracklist (regex: "01:23:45 Artist - Track")
   d. Segment audio into 12s/6s-hop windows
   e. Batch-send segments to ACRCloud (10 parallel)
   f. Aggregate results (merge, threshold, dedup)
   g. Cross-reference with parsed description tracklist
   h. Store final tracklist in PostgreSQL
   i. Delete temp audio from Blob
   j. Push completion via WebSocket

3. GET /api/jobs/{id}/tracklist
   → Return structured tracklist with timestamps, confidence scores
```

### Free Validation Layer

YouTube video descriptions and pinned comments frequently contain DJ-posted tracklists. Parse these with regex for timestamp patterns and cross-reference against fingerprint results — free accuracy boost and gap-filling.

### Expected Accuracy

| Scenario | Accuracy |
|----------|----------|
| Commercial tracks played cleanly (32+ bars unmixed) | 80-90% |
| Tracks during transitions (short exposure, heavy EQ) | 50-60% |
| Unreleased dubplates, white labels, heavily effected sections | 0% |

85% with timestamps is vastly more useful than anything that exists today. 100% is impossible — design for graceful gaps.

## Project Structure

### Source Code

```text
frontend/
├── src/
│   ├── app/                     # Next.js App Router
│   │   ├── page.tsx             # Home — URL submission form
│   │   ├── sets/
│   │   │   └── [id]/
│   │   │       └── page.tsx     # Results — waveform timeline + tracklist
│   │   └── history/
│   │       └── page.tsx         # Processing history (US5)
│   ├── components/
│   │   ├── SubmitForm.tsx
│   │   ├── WaveformTimeline.tsx # Wavesurfer.js integration
│   │   ├── TrackList.tsx
│   │   ├── TrackRow.tsx
│   │   ├── ProgressBar.tsx
│   │   └── ExportMenu.tsx
│   └── lib/
│       ├── api.ts               # Backend API client
│       └── websocket.ts         # WebSocket connection for progress
├── package.json
├── tsconfig.json
├── eslint.config.js
├── tailwind.config.ts
└── Dockerfile

backend/
├── app/
│   ├── main.py                  # FastAPI app entry
│   ├── api/
│   │   ├── jobs.py              # POST /jobs, GET /jobs/{id}
│   │   └── tracks.py            # GET/PATCH/DELETE tracks
│   ├── workers/
│   │   ├── celery_app.py        # Celery configuration
│   │   └── process_set.py       # Main processing pipeline task
│   ├── services/
│   │   ├── youtube.py           # yt-dlp wrapper
│   │   ├── audio.py             # FFmpeg segmentation
│   │   ├── fingerprint.py       # ACRCloud integration
│   │   ├── aggregator.py        # Result merging, dedup, transition detection
│   │   └── description_parser.py # YouTube description tracklist extraction
│   ├── models/
│   │   ├── job.py               # SQLAlchemy Job model
│   │   ├── track.py             # SQLAlchemy Track model
│   │   └── unidentified.py      # SQLAlchemy UnidentifiedSegment model
│   └── db.py                    # Database connection
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── .env.example

docs/
├── constitution.md
└── specs/
    ├── spec.md
    ├── plan.md
    └── tasks.md
```

**Structure Decision**: Web application split — Python backend (FastAPI + Celery workers) and TypeScript frontend (Next.js). Justified by the fundamentally different ecosystems needed: Python for audio processing, TypeScript for interactive UI.

## Data Model

### Job

| Field | Type | Notes |
|-------|------|-------|
| id | uuid | Primary key |
| youtube_url | string | Original URL |
| video_title | string | Fetched from YouTube |
| duration_seconds | int | Video duration |
| status | enum | QUEUED, DOWNLOADING, SEGMENTING, FINGERPRINTING, AGGREGATING, COMPLETE, FAILED |
| progress | int | 0-100 percentage |
| error_message | string? | Null unless FAILED |
| created_at | datetime | Submission time |
| completed_at | datetime? | Processing completion |

### Track

| Field | Type | Notes |
|-------|------|-------|
| id | uuid | Primary key |
| job_id | uuid | FK → Job |
| position | int | Order in set |
| start_time_ms | int | Milliseconds from start |
| end_time_ms | int? | Milliseconds, null if unknown |
| title | string? | Null if unidentified |
| artist | string? | Null if unidentified |
| album | string? | |
| confidence_score | float? | ACRCloud confidence (0-100) |
| is_transition | boolean | Detected during overlap zone |
| is_manual_edit | boolean | User-edited |
| spotify_url | string? | Enrichment (future) |
| apple_music_url | string? | Enrichment (future) |
| album_art_url | string? | Enrichment (future) |

### UnidentifiedSegment

| Field | Type | Notes |
|-------|------|-------|
| id | uuid | Primary key |
| job_id | uuid | FK → Job |
| start_time_ms | int | Segment start |
| end_time_ms | int | Segment end |
| notes | string? | e.g., "possible unreleased track", "MC segment" |

## Cost Model

- **ACRCloud**: ~$2-6 per 2-hour set (~1,200 API calls). Primary operating cost.
- **Azure Container Apps**: Minimal for single-user workload. Scale-to-zero when idle.
- **PostgreSQL (Azure Flexible Server)**: Burstable B1ms tier (~£12/month).
- **Redis (Azure Cache)**: Basic C0 tier (~£12/month).
- **Blob Storage**: Negligible — temp files deleted after processing.

### Future Cost Optimisation

At scale: use Chromaprint (open source) for a first pass, only send uncertain segments to ACRCloud. Reduces API calls by ~60%.

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | ⚠️ ACCEPTED | Two-language split documented in Complexity Tracking. Each side is internally simple. |
| II. Security by Default | ✅ PASS | All secrets in env vars. URL validation at entry. Blob SAS tokens. |
| III. Type Safety & Linting | ✅ PASS | TS strict + mypy. ESLint + Ruff. |
| IV. Test What Matters | ✅ PASS | Aggregator, segmenter, description parser all testable. |
| V. Ship Fast, Fix Fast | ✅ PASS | MVP = submit + results. No editing/export/history. |
| VI. Minimal Dependencies | ⚠️ ACCEPTED | Each dep justified in table above. |
| VII. Documentation as Code | ✅ PASS | FastAPI auto-generates OpenAPI. README with setup. |
| VIII. Azure, UK South | ✅ PASS | All services available in UK South. |
