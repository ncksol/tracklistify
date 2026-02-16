"""Celery application configuration with Redis broker."""

import os

from celery import Celery  # type: ignore[import-untyped]
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read Redis URL from environment variable with default fallback
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery application instance
celery_app: Celery = Celery("tracklistify")

# Configure Celery
celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_hijack_root_logger=False,
)

# Explicitly include task modules (autodiscover looks for tasks.py by default)
celery_app.conf.update(include=["app.workers.process_set"])
