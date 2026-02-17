"""Celery application configuration with Redis broker."""

import logging
import os
import sys

from celery import Celery  # type: ignore[import-untyped]
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _get_redis_url() -> str:
    """Get Redis URL, using Key Vault for password if needed."""
    # If explicit REDIS_URL is set, use it (local dev)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url

    # Cloud: build URL from components
    host = os.getenv("REDIS_HOST")
    if not host:
        # Fallback to default for local dev
        return "redis://localhost:6379/0"

    # For cloud: read Redis key from Key Vault if available
    vault_url = os.getenv("KEY_VAULT_URI")
    if vault_url:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        redis_key = client.get_secret("redis-primary-key").value
        return f"rediss://:{redis_key}@{host}:6380/0?ssl_cert_reqs=required"

    # No Key Vault, use unsecured connection
    return f"redis://{host}:6379/0"


# Get Redis URL with fallback logic
REDIS_URL: str = _get_redis_url()

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

# Configure logging so child worker output is visible in container logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
