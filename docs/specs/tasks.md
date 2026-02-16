# Tasks: Tracklistify

**Input**: Design documents from `docs/specs/`
**Prerequisites**: plan.md (required), spec.md (required)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialisation, tooling, and both project scaffolds

- [ ] T001 Create monorepo structure with `frontend/` and `backend/` directories at repo root
- [ ] T002 [P] Initialise Next.js 14 project with App Router in `frontend/`, TypeScript strict, Tailwind CSS in `frontend/tailwind.config.ts`
- [ ] T003 [P] Initialise Python 3.12 project with FastAPI in `backend/`, create `backend/pyproject.toml` and `backend/requirements.txt`
- [ ] T004 [P] Configure ESLint + Prettier for frontend in `frontend/eslint.config.js`
- [ ] T005 [P] Configure Ruff linter + formatter for backend in `backend/pyproject.toml`
- [ ] T006 [P] Configure TypeScript strict mode in `frontend/tsconfig.json` (no `any` allowed)
- [ ] T007 [P] Configure mypy for Python type checking in `backend/pyproject.toml`
- [ ] T008 Create `.env.example` files in both `frontend/.env.example` and `backend/.env.example` with all required env vars (ACRCloud key, DB URL, Redis URL, Blob connection string)
- [ ] T009 Create `backend/Dockerfile` with Python 3.12, yt-dlp, FFmpeg, and all Python dependencies
- [ ] T010 Create `frontend/Dockerfile` for Next.js production build
- [ ] T011 Create `docker-compose.yml` at repo root for local dev (backend, frontend, PostgreSQL, Redis)
- [ ] T012 Write root `README.md` with project description, prerequisites, and copy-pasteable setup commands (< 2 minutes to run)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database, job queue, external service wiring, AND Azure infrastructure — MUST complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Infrastructure as Code

- [ ] T013 [P] Create Azure resource group and Container Apps environment (Bicep or Terraform) for UK South in `infra/main.bicep`
- [ ] T014 [P] Configure Azure Managed PostgreSQL (Flexible Server, Burstable B1ms, UK South) in `infra/database.bicep`
- [ ] T015 [P] Configure Azure Cache for Redis (Basic C0, UK South) in `infra/redis.bicep`
- [ ] T016 [P] Configure Azure Blob Storage account and temp audio container in `infra/storage.bicep`
- [ ] T017 [P] Configure Azure Container Apps for backend API, Celery worker, and frontend in `infra/containers.bicep`
- [ ] T018 Create deployment script that provisions all infra from Bicep templates in `infra/deploy.sh`

### Database & Models

- [ ] T019 Define SQLAlchemy models for Job (id, youtube_url, video_title, duration_seconds, status enum, progress, error_message, created_at, completed_at) in `backend/app/models/job.py`
- [ ] T020 [P] Define SQLAlchemy model for Track (id, job_id FK, position, start_time_ms, end_time_ms, title, artist, album, confidence_score, is_transition, is_manual_edit) in `backend/app/models/track.py`
- [ ] T021 [P] Define SQLAlchemy model for UnidentifiedSegment (id, job_id FK, start_time_ms, end_time_ms, notes) in `backend/app/models/unidentified.py`
- [ ] T022 Create database connection and session management in `backend/app/db.py`
- [ ] T023 Create Alembic migration configuration and initial migration in `backend/alembic/`

### Application Core

- [ ] T024 Configure Celery app with Redis broker in `backend/app/workers/celery_app.py`
- [ ] T025 Create FastAPI app entry point with CORS config for frontend in `backend/app/main.py`

### Service Wrappers

- [ ] T026 [P] Create Azure Blob Storage helper (upload, download, delete temp audio files) in `backend/app/services/blob_storage.py`
- [ ] T027 [P] Create ACRCloud client wrapper (send audio segment, parse response with confidence score and match offset) in `backend/app/services/fingerprint.py`
- [ ] T028 [P] Create yt-dlp wrapper (validate URL, get metadata, download audio as WAV) in `backend/app/services/youtube.py`
- [ ] T029 [P] Create FFmpeg audio segmenter (split audio into 12s windows with 6s hop) in `backend/app/services/audio.py`

**Checkpoint**: Foundation ready — Azure infra provisioned, all external services wired, database schema live, job queue operational

---

## Phase 3: User Story 1 — Submit DJ Set for Track Detection (Priority: P1) 🎯 MVP

**Goal**: User pastes YouTube URL → system processes audio → returns ordered tracklist with timestamps

**Independent Test**: Submit a known Boiler Room set URL. Receive a tracklist that roughly matches the published tracklist.

### Backend — Processing Pipeline

- [ ] T030 [US1] Implement YouTube description/comments parser to extract existing tracklists (regex for timestamp patterns like "01:23:45 Artist - Track") in `backend/app/services/description_parser.py`
- [ ] T031 [P] [US1] Implement result aggregator: merge consecutive matches, detect transitions, confidence thresholding (>70%), gap handling (3+ unmatched segments → UnidentifiedSegment), fuzzy dedup on title/artist in `backend/app/services/aggregator.py`
- [ ] T032 [US1] Implement main Celery processing pipeline task (download → segment → fingerprint batch with 10 parallel → aggregate → cross-reference description → store results → clean up temp audio) in `backend/app/workers/process_set.py`
- [ ] T033 [US1] Implement WebSocket endpoint for real-time processing progress updates in `backend/app/api/websocket.py`

### Backend — API Endpoints

- [ ] T034 [US1] Implement POST `/api/jobs` endpoint (validate YouTube URL via yt-dlp --get-title, check cache for duplicate URL, create job record, enqueue Celery task, return job ID) in `backend/app/api/jobs.py`
- [ ] T035 [US1] Implement GET `/api/jobs/{id}` endpoint (return job status, progress, error if failed) in `backend/app/api/jobs.py`
- [ ] T036 [US1] Implement GET `/api/jobs/{id}/tracklist` endpoint (return ordered tracks + unidentified segments) in `backend/app/api/jobs.py`

### Frontend — Submission & Results

- [ ] T037 [US1] Create URL submission form component with validation and error display in `frontend/src/components/SubmitForm.tsx`
- [ ] T038 [US1] Create home page with submission form in `frontend/src/app/page.tsx`
- [ ] T039 [US1] Create API client module for backend communication in `frontend/src/lib/api.ts`
- [ ] T040 [US1] Create WebSocket client for real-time progress updates in `frontend/src/lib/websocket.ts`
- [ ] T041 [US1] Create progress bar component showing job status and percentage in `frontend/src/components/ProgressBar.tsx`
- [ ] T042 [US1] Create track row component displaying position, timestamp, artist, title, confidence in `frontend/src/components/TrackRow.tsx`
- [ ] T043 [US1] Create tracklist component rendering ordered tracks + unidentified segments in `frontend/src/components/TrackList.tsx`
- [ ] T044 [US1] Create results page with tracklist display, loading states, and error handling in `frontend/src/app/sets/[id]/page.tsx`

### Tests

- [ ] T045 [P] [US1] Write pytest tests for audio segmenter (correct window count, overlap, edge cases for short audio) in `backend/tests/test_audio.py`
- [ ] T046 [P] [US1] Write pytest tests for result aggregator (merge consecutive, transition detection, confidence threshold, gap handling, dedup) in `backend/tests/test_aggregator.py`
- [ ] T047 [P] [US1] Write pytest tests for description parser (various timestamp formats, edge cases) in `backend/tests/test_description_parser.py`
- [ ] T048 [US1] Write pytest integration test for full processing pipeline with mock ACRCloud responses in `backend/tests/test_pipeline.py`

**Checkpoint**: MVP complete — submit a URL, see processing progress, get a tracklist. Independently deployable and testable.

---

## Phase 4: User Story 2 — View and Browse Detection Results (Priority: P2)

**Goal**: Interactive waveform timeline with clickable track regions and YouTube seek

**Independent Test**: After processing, user sees waveform with coloured regions. Clicking a track seeks YouTube video to that timestamp.

- [ ] T049 [US2] Create waveform timeline component with Wavesurfer.js, rendering track boundaries as coloured regions in `frontend/src/components/WaveformTimeline.tsx`
- [ ] T050 [US2] Add embedded YouTube player to results page with seek-to-timestamp on track click in `frontend/src/app/sets/[id]/page.tsx`
- [ ] T051 [US2] Add visual distinction for unidentified segments (grey/hatched regions) in `frontend/src/components/WaveformTimeline.tsx`
- [ ] T052 [US2] Add waveform audio data endpoint — serve a downsampled waveform JSON from backend in `backend/app/api/jobs.py`

**Checkpoint**: Rich results view — waveform + clickable tracklist + YouTube player

---

## Phase 5: User Story 3 — Edit and Correct Tracklist (Priority: P3)

**Goal**: User can fix misidentified tracks, fill unidentified gaps, adjust timestamps

**Independent Test**: Click edit on a track, change artist/title, save. Reload page — changes persist.

- [ ] T053 [US3] Implement PATCH `/api/jobs/{id}/tracks/{track_id}` endpoint (update artist, title, start_time_ms, end_time_ms) in `backend/app/api/tracks.py`
- [ ] T054 [US3] Implement DELETE `/api/jobs/{id}/tracks/{track_id}` endpoint (remove false positive) in `backend/app/api/tracks.py`
- [ ] T055 [US3] Implement POST `/api/jobs/{id}/tracks` endpoint (manually add track to fill unidentified gap) in `backend/app/api/tracks.py`
- [ ] T056 [US3] Create inline editing UI for track rows (editable fields for artist, title, timestamp) in `frontend/src/components/TrackRow.tsx`
- [ ] T057 [US3] Add delete button to track rows with confirmation in `frontend/src/components/TrackRow.tsx`
- [ ] T058 [US3] Add "Add Track" button for unidentified segments in `frontend/src/components/TrackList.tsx`
- [ ] T059 [P] [US3] Write pytest tests for track CRUD endpoints in `backend/tests/test_tracks.py`

**Checkpoint**: Full edit capability — correct, add, delete tracks. All changes persist.

---

## Phase 6: User Story 4 — Export Tracklist (Priority: P4)

**Goal**: Export to plain text, JSON, or shareable link

**Independent Test**: Click export, select format, receive correctly formatted file.

- [ ] T060 [US4] Implement GET `/api/jobs/{id}/export?format=text` endpoint (formatted plain text with timestamps) in `backend/app/api/export.py`
- [ ] T061 [P] [US4] Implement GET `/api/jobs/{id}/export?format=json` endpoint (structured JSON) in `backend/app/api/export.py`
- [ ] T062 [US4] Implement shareable link generation (public read-only view via unique slug) in `backend/app/api/export.py`
- [ ] T063 [US4] Create public shareable results page (no editing, view-only) in `frontend/src/app/share/[slug]/page.tsx`
- [ ] T064 [US4] Create export menu component with format selection in `frontend/src/components/ExportMenu.tsx`

**Checkpoint**: Full export — text, JSON, shareable link

---

## Phase 7: User Story 5 — Processing History (Priority: P5)

**Goal**: View list of previously processed sets, access past results

**Independent Test**: Process multiple sets, visit history page, see all past submissions with links.

- [ ] T065 [US5] Implement GET `/api/jobs` endpoint with pagination (list all jobs, ordered by date, with track count) in `backend/app/api/jobs.py`
- [ ] T066 [US5] Create history page with list of past submissions in `frontend/src/app/history/page.tsx`
- [ ] T067 [US5] Add navigation between home, history, and results pages in `frontend/src/components/Navigation.tsx`

**Checkpoint**: Complete app — submit, view, edit, export, history

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CI/CD, monitoring, and final quality pass

- [ ] T068 Set up GitHub Actions CI pipeline (lint, type-check, test for both frontend and backend) in `.github/workflows/ci.yml`
- [ ] T069 Set up GitHub Actions CD pipeline (build Docker images, deploy to Azure Container Apps) in `.github/workflows/deploy.yml`
- [ ] T070 Add error tracking and monitoring (Application Insights or Sentry) in both frontend and backend
- [ ] T071 Add rate limiting to job submission endpoint (prevent accidental spam) in `backend/app/api/jobs.py`
- [ ] T072 Final README update with architecture diagram, deployment instructions, and cost estimates in `README.md`

---

## Agent Swarm: Parallel Execution Analysis

### Execution Lanes

The project can be split into **4 concurrent agent lanes** after Phase 1 completes. Phase 1 must be done by a single agent (or two — one frontend, one backend) since it creates the scaffolding everything else depends on.

```
Timeline →

PHASE 1 (Sequential — 1 agent)
│
├── T001 (monorepo structure)
├── T002+T003 (frontend + backend init — 2 agents possible)
├── T004-T007 (linting/typing config — can parallel)
├── T008-T012 (env, Docker, compose, README)
│
▼ PHASE 1 COMPLETE — FORK INTO LANES
│
├─── LANE A: Infra Agent ──────────────────────────────────────────────────
│    T013-T018 (all Azure IaC)
│    Then: T068-T069 (CI/CD pipelines)
│    Then: T070 (monitoring)
│    Then: T072 (final README)
│
├─── LANE B: Backend Models + Services Agent ──────────────────────────────
│    T019-T023 (DB models + Alembic)
│    T024-T025 (Celery + FastAPI entry)
│    T026-T029 (all service wrappers — parallel within)
│    ▼ PHASE 2 BACKEND COMPLETE
│    T030-T031 (description parser + aggregator — parallel)
│    T032 (processing pipeline — depends on T030+T031)
│    T033 (WebSocket)
│    T034-T036 (API endpoints)
│    ▼ US1 BACKEND COMPLETE
│    Then available for: US3 backend (T053-T055), US4 backend (T060-T062),
│                        US5 backend (T065), US3 tests (T059)
│
├─── LANE C: Frontend Agent ───────────────────────────────────────────────
│    ⏸ WAIT for Lane B to complete API endpoints (T034-T036)
│    T037-T044 (all US1 frontend components + pages)
│    ▼ US1 FRONTEND COMPLETE
│    T049-T051 (US2 waveform + YouTube player)
│    T056-T058 (US3 editing UI)
│    T063-T064 (US4 export UI + share page)
│    T066-T067 (US5 history + navigation)
│
├─── LANE D: Test Agent ───────────────────────────────────────────────────
│    ⏸ WAIT for Lane B service wrappers (T026-T029)
│    T045 (segmenter tests)
│    ⏸ WAIT for T030-T031
│    T046-T047 (aggregator + parser tests — parallel)
│    ⏸ WAIT for T032
│    T048 (integration test)
│    Then: T059 (US3 track CRUD tests)
│
```

### Dependency Graph (Critical Path)

```
T001 → T002+T003 → T004-T007 → T008-T012
                         │
         ┌───────────────┼───────────────┬──────────────┐
         ▼               ▼               ▼              ▼
    LANE A:         LANE B:         LANE C:        LANE D:
    T013-T018       T019-T029       (waits)        (waits)
    (IaC)           (models+svc)        │              │
         │               │              │              │
         │          T030+T031 ──────────│──────────→ T045
         │               │              │          T046+T047
         │          T032 (pipeline)     │              │
         │          T033 (WS)           │          T048
         │          T034-T036 ──────→ T037-T044       │
         │               │              │              │
    T068-T069       T053-T055       T049-T051     T059
    (CI/CD)         (US3 BE)        (US2 FE)         │
         │          T060-T062       T056-T058         │
    T070            (US4 BE)        (US3 FE)          │
    T072            T065            T063-T064         │
                    (US5 BE)        T066-T067         │
```

### Critical Path (Longest Sequential Chain)

```
T001 → T003 → T019 → T022 → T023 → T024 → T025 → T030 → T032 → T034 → T037 → T044
(setup)  (py)  (model) (db)  (alembic)(celery)(api) (parser)(pipe) (POST) (form) (results)

= 12 sequential tasks before MVP frontend is visible
```

### Agent Assignment Summary

| Agent | Focus | Tasks | Blocked By |
|-------|-------|-------|------------|
| **Agent A — Infra** | Azure IaC, CI/CD, monitoring | T013-T018, T068-T070, T072 | Phase 1 only |
| **Agent B — Backend** | Models, services, pipeline, API | T019-T036, T053-T055, T060-T062, T065 | Phase 1 only |
| **Agent C — Frontend** | Components, pages, UI | T037-T044, T049-T051, T056-T058, T063-T064, T066-T067 | Agent B API endpoints |
| **Agent D — Tests** | Unit + integration tests | T045-T048, T059 | Agent B service code |

### Optimal Swarm Strategy

1. **Single agent** does Phase 1 (T001-T012) — scaffolding must be coherent
2. **Fork into 4 agents** at Phase 2:
   - Agent A starts immediately on IaC (fully independent)
   - Agent B starts immediately on models + services
   - Agent C waits for Agent B's API endpoints (T034-T036), then sprints through all frontend
   - Agent D writes tests as Agent B delivers testable services
3. **Agent A finishes first** (IaC + CI/CD is ~11 tasks, no deep dependencies)
4. **Agent C has the longest wait** but shortest sprint once unblocked
5. **Merge point**: All agents' work converges for the MVP checkpoint after Phase 3

### Estimated Timeline (4 agents)

| Phase | Sequential | With 4 Agents |
|-------|-----------|---------------|
| Phase 1 (Setup) | 12 tasks | 12 tasks (1 agent) |
| Phase 2 (Foundation) | 17 tasks | ~10 tasks (A+B parallel) |
| Phase 3 (US1 MVP) | 19 tasks | ~12 tasks (B+C+D parallel) |
| Phase 4-7 (US2-5) | 19 tasks | ~8 tasks (B+C parallel) |
| Phase 8 (Polish) | 5 tasks | Already done by Agent A |
| **Total** | **72 tasks serial** | **~42 effective tasks** (~42% faster) |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — this is the MVP
- **US2 (Phase 4)**: Depends on US1 (needs processed results to display)
- **US3 (Phase 5)**: Depends on US2 (editing extends the results view). Backend can start after US1 backend.
- **US4 (Phase 6)**: Depends on US1 (needs tracklist data to export). Can parallel with US2/US3.
- **US5 (Phase 7)**: Depends on US1 (needs job records). Can parallel with US2/US3/US4.
- **Polish (Phase 8)**: IaC in Phase 2. CI/CD can start after Phase 1.

### Within User Story 1

- T030, T031 can run in parallel (description parser + aggregator are independent)
- T032 depends on T030 + T031 (pipeline uses both)
- T033 independent of pipeline logic
- T034-T036 depend on T032 (API needs pipeline)
- T037-T044 frontend tasks depend on T034-T036 (need API to call)
- T045-T047 tests can run in parallel once their target code exists
- T048 depends on T032 (integration test needs pipeline)

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (including Azure infra)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Submit a real Boiler Room set, compare results to published tracklist
5. Deploy to Azure — it works for one user (you), ship it

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test with real DJ sets → Deploy (MVP! 🎯)
3. Add US2 → Waveform timeline → Deploy
4. Add US3 → Editing capability → Deploy
5. Add US4 + US5 → Export + History → Deploy
6. Polish → CI/CD, monitoring → Production-ready

## Summary

- **Total tasks**: 72
- **Phase 1 (Setup)**: 12 tasks
- **Phase 2 (Foundational + IaC)**: 17 tasks
- **Phase 3 (US1 — MVP)**: 19 tasks
- **Phase 4 (US2)**: 4 tasks
- **Phase 5 (US3)**: 7 tasks
- **Phase 6 (US4)**: 5 tasks
- **Phase 7 (US5)**: 3 tasks
- **Phase 8 (Polish)**: 5 tasks
- **MVP scope**: 48 tasks (Phase 1 + 2 + 3)
- **Agent lanes**: 4 (Infra, Backend, Frontend, Tests)
- **Parallel speedup**: ~42% faster with 4 agents vs sequential
