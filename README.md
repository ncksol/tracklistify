<p align="center">
  <img src="docs/banner.png" alt="Tracklistify" width="600" />
</p>
<p align="center">
  <p align="center">
    <strong>Turn DJ sets into tracklists using audio fingerprinting</strong>
  </p>
  <p align="center">
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-how-it-works">How It Works</a> •
    <a href="#-api">API</a> •
    <a href="#-deployment">Deployment</a> •
    <a href="docs/specs/spec.md">Spec</a> •
    <a href="docs/specs/plan.md">Roadmap</a>
  </p>
</p>

---

Paste a YouTube DJ set URL → Tracklistify extracts the audio, runs sliding-window fingerprinting via [ACRCloud](https://www.acrcloud.com/), and returns an ordered tracklist with timestamps. Click any track to jump to that point in the video.

## ✨ Features

- 🔗 **Paste & identify** — submit any YouTube DJ set URL
- 🎯 **Audio fingerprinting** — ACRCloud-powered track identification with configurable confidence threshold
- 📊 **Live progress** — real-time pipeline status with activity log
- ▶️ **Embedded player** — click a track to seek the YouTube video
- 📝 **Manual editing** — add, remove, or correct tracks and unidentified sections
- 📤 **Export** — download tracklists as JSON or plain text
- 🔄 **Reanalyse** — re-run identification with different settings
- ⚙️ **Settings** — adjust confidence threshold per analysis
- 🔗 **Shareable links** — share results with a public URL

## 🏗 Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Browser   │────▶│  Next.js     │────▶│  FastAPI          │
│             │◀────│  Frontend    │◀────│  Backend          │
└─────────────┘     └──────────────┘     └────────┬─────────┘
                                                  │
                                         ┌────────▼─────────┐
                                         │  Celery Worker    │
                                         │                   │
                                         │  yt-dlp → FFmpeg  │
                                         │       ↓           │
                                         │  ACRCloud API     │
                                         │       ↓           │
                                         │  Aggregator       │
                                         └────────┬─────────┘
                                                  │
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                         PostgreSQL            Redis           Azure Blob
                         (results)            (queue)         (temp audio)
```

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS 4 |
| **Backend** | Python 3.12, FastAPI, Celery |
| **Audio** | yt-dlp, FFmpeg, ACRCloud Broadcast Monitoring API |
| **Database** | PostgreSQL (SQLAlchemy 2.0 + Alembic) |
| **Queue** | Redis |
| **Infra** | Azure Container Apps, Bicep IaC, GitHub Actions CI/CD |

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- [ACRCloud](https://www.acrcloud.com/) account (Broadcast Monitoring API)

### Run with Docker

```bash
git clone https://github.com/your-username/tracklistify.git
cd tracklistify

# Configure credentials
cp backend/.env.example backend/.env
# Edit backend/.env with your ACRCloud credentials

# Start everything
docker-compose up
```

Open [http://localhost:3000](http://localhost:3000) and paste a YouTube URL.

### Run standalone CLI (no backend/frontend)

Use this mode to generate a local tracklist directly from a YouTube URL.

**Prerequisites**

- Python 3.12+
- `ffmpeg` and `ffprobe` on your `PATH`
- `yt-dlp` on your `PATH`
- Node.js on your `PATH` (used by `yt-dlp --js-runtimes node`)
- ACRCloud Broadcast Monitoring credentials exported as environment variables:
  - `ACR_ACCESS_KEY`
  - `ACR_ACCESS_SECRET`
  - `ACR_HOST`

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Export ACRCloud credentials in your shell before running:
# export ACR_ACCESS_KEY=...
# export ACR_ACCESS_SECRET=...
# export ACR_HOST=identify-eu-west-1.acrcloud.com

tracklistify identify "https://www.youtube.com/watch?v=VIDEO_ID"
tracklistify identify "https://www.youtube.com/watch?v=VIDEO_ID" --format json --output ./tracklist.json
```

**CLI usage**

```bash
# show available commands/options
tracklistify --help
tracklistify identify --help

# command shape
tracklistify identify "<youtube_url>" \
  [--cookie-file PATH] \
  [--confidence-threshold FLOAT] \
  [--format text|json] \
  [--output PATH]

# write text output to a file
tracklistify identify "https://www.youtube.com/watch?v=VIDEO_ID" --output ./tracklist.txt

# write JSON output to a file
tracklistify identify "https://www.youtube.com/watch?v=VIDEO_ID" --format json --output ./tracklist.json

# use a cookies file if needed for video access
tracklistify identify "https://www.youtube.com/watch?v=VIDEO_ID" --cookie-file ./cookies.txt
```

### Run locally (development)

```bash
# Start Postgres + Redis
docker-compose up postgres redis -d

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000 &
celery -A app.workers.celery_app worker --loglevel=info --pool=solo &

# Frontend
cd ../frontend
npm install
npm run dev
```

## 📡 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs` | Submit a URL for processing |
| `GET` | `/api/jobs/{id}` | Job status and progress |
| `GET` | `/api/jobs/{id}/tracklist` | Identified tracks + unidentified gaps |
| `GET` | `/api/jobs/{id}/events` | Processing event log |
| `GET` | `/api/jobs/{id}/export` | Export tracklist (JSON / text) |
| `DELETE` | `/api/jobs/{id}` | Delete a job and all related data |
| `POST` | `/api/jobs/{id}/tracks` | Manually add a track |
| `PATCH` | `/api/jobs/{id}/tracks/{tid}` | Edit track metadata |
| `DELETE` | `/api/jobs/{id}/tracks/{tid}` | Remove a false positive |
| `DELETE` | `/api/jobs/{id}/unidentified/{sid}` | Remove an unidentified section |

## ☁️ Deployment

Infrastructure is provisioned on Azure using Bicep templates. See [`infra/`](infra/) for details.

```bash
# Provision Azure resources
./infra/deploy.sh

# CI/CD deploys automatically on push to main via GitHub Actions
```

### Cost Estimates

| Resource | Cost |
|----------|------|
| **ACRCloud** | ~$2–6 per 2-hour set (~1,200 API calls) |
| **Azure PostgreSQL** (B1ms) | ~£12/month |
| **Azure Redis** (C0) | ~£12/month |
| **Container Apps** | Scale-to-zero; minimal for low traffic |
| **Blob Storage** | Negligible (temp files auto-deleted) |

## 📁 Project Structure

```
tracklistify/
├── frontend/           # Next.js web application
├── backend/            # FastAPI + Celery workers
│   ├── app/
│   │   ├── api/        # REST endpoints
│   │   ├── models/     # SQLAlchemy models
│   │   ├── services/   # Fingerprinting, aggregation, storage
│   │   └── workers/    # Celery pipeline tasks
│   ├── alembic/        # Database migrations
│   └── tests/          # Pytest suite
├── infra/              # Azure Bicep templates + deploy script
├── docs/               # Specification, roadmap, constitution
│   ├── specs/          # Feature spec & implementation plan
│   └── constitution.md # Coding principles & conventions
├── .github/workflows/  # CI + CD pipelines
└── docker-compose.yml  # Local development environment
```

## 📚 Documentation

- **[Feature Specification](docs/specs/spec.md)** — user stories, requirements, and technical design
- **[Implementation Plan](docs/specs/plan.md)** — phased roadmap with task breakdown
- **[Project Constitution](docs/constitution.md)** — coding conventions, security rules, and architecture constraints

## 📄 License

This project is provided as-is for personal and educational use.
