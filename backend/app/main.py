"""Main FastAPI application."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import export, jobs, tracks, websocket
from app.monitoring import setup_monitoring


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup: load environment variables
    load_dotenv()
    # Setup Application Insights monitoring
    setup_monitoring()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Tracklistify API",
    description="Backend API for Tracklistify",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins_str: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
cors_origins: list[str] = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API router
api_router = APIRouter()

# Include sub-routers
app.include_router(jobs.router)
app.include_router(tracks.router)
app.include_router(export.router)
app.include_router(export.share_router)

# WebSocket router
app.include_router(websocket.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
