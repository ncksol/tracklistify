"""Cookie file management service for YouTube authentication."""

import contextlib
import logging
import os
import tempfile

from azure.core.exceptions import ResourceExistsError

from app.services.blob_storage import (
    _get_blob_service_client,
    _is_storage_configured,
)

logger = logging.getLogger(__name__)

COOKIE_CONTAINER = os.getenv("AZURE_COOKIE_CONTAINER", "tracklistify-cookies")
CANONICAL_COOKIE_BLOB = "canonical/youtube_cookies.txt"


async def save_canonical_cookie(cookie_content: bytes) -> None:
    """Save canonical YouTube cookie file to blob storage.

    Args:
        cookie_content: Raw bytes of the cookie file

    Raises:
        ValueError: If storage is not configured
    """
    if not _is_storage_configured():
        logger.warning("Storage not configured, skipping canonical cookie save")
        return

    async with _get_blob_service_client() as blob_service_client:
        container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)

        # Create container if it doesn't exist
        with contextlib.suppress(ResourceExistsError):
            await container_client.create_container()

        # Upload canonical cookie
        blob_client = container_client.get_blob_client(CANONICAL_COOKIE_BLOB)
        await blob_client.upload_blob(cookie_content, overwrite=True)
        logger.info("Canonical cookie saved to blob storage")


async def get_canonical_cookie() -> bytes | None:
    """Retrieve canonical YouTube cookie file from blob storage.

    Returns:
        Cookie file bytes if exists, None otherwise
    """
    if not _is_storage_configured():
        return None

    try:
        async with _get_blob_service_client() as blob_service_client:
            container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)
            blob_client = container_client.get_blob_client(CANONICAL_COOKIE_BLOB)

            download_stream = await blob_client.download_blob()
            content = await download_stream.readall()
            logger.info("Retrieved canonical cookie from blob storage")
            return content
    except Exception:
        logger.debug("Canonical cookie not found or retrieval failed")
        return None


async def delete_canonical_cookie() -> None:
    """Delete the canonical YouTube cookie file from blob storage."""
    if not _is_storage_configured():
        return

    try:
        async with _get_blob_service_client() as blob_service_client:
            container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)
            blob_client = container_client.get_blob_client(CANONICAL_COOKIE_BLOB)
            await blob_client.delete_blob()
            logger.info("Canonical cookie deleted from blob storage")
    except Exception:
        logger.debug("Failed to delete canonical cookie")


async def save_job_cookie(job_id: str, cookie_content: bytes) -> str:
    """Save job-specific cookie file to blob storage.

    Args:
        job_id: Job identifier
        cookie_content: Raw bytes of the cookie file

    Returns:
        Blob name/reference for the uploaded cookie

    Raises:
        ValueError: If storage is not configured
    """
    if not _is_storage_configured():
        raise ValueError("Storage not configured for job cookie upload")

    blob_name = f"{job_id}/cookies.txt"

    async with _get_blob_service_client() as blob_service_client:
        container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)

        # Create container if it doesn't exist
        with contextlib.suppress(ResourceExistsError):
            await container_client.create_container()

        # Upload job-specific cookie
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.upload_blob(cookie_content, overwrite=True)
        logger.info("Job cookie uploaded: job_id=%s", job_id)

    return blob_name


async def get_job_cookie(blob_name: str) -> bytes | None:
    """Retrieve job-specific cookie file from blob storage.

    Args:
        blob_name: Blob reference returned from save_job_cookie

    Returns:
        Cookie file bytes if exists, None otherwise
    """
    if not _is_storage_configured():
        return None

    try:
        async with _get_blob_service_client() as blob_service_client:
            container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)
            blob_client = container_client.get_blob_client(blob_name)

            download_stream = await blob_client.download_blob()
            content = await download_stream.readall()
            return content
    except Exception:
        logger.debug("Job cookie not found or retrieval failed")
        return None


async def delete_job_cookie(blob_name: str) -> None:
    """Delete job-specific cookie file from blob storage.

    Args:
        blob_name: Blob reference returned from save_job_cookie
    """
    if not _is_storage_configured():
        return

    try:
        async with _get_blob_service_client() as blob_service_client:
            container_client = blob_service_client.get_container_client(COOKIE_CONTAINER)
            blob_client = container_client.get_blob_client(blob_name)
            await blob_client.delete_blob()
            logger.info("Job cookie deleted")
    except Exception:
        logger.debug("Failed to delete job cookie")


async def probe_cookie(
    cookie_content: bytes,
    test_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
) -> bool:
    """Validate cookie by attempting a lightweight yt-dlp metadata fetch.

    Args:
        cookie_content: Raw bytes of the cookie file
        test_url: YouTube URL to test against (default: stable video)

    Returns:
        True if cookie appears valid, False otherwise
    """
    import asyncio

    # Write cookie to temp file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
    try:
        os.write(tmp_fd, cookie_content)
        os.close(tmp_fd)

        # Run yt-dlp with short timeouts. This can take up to ~20s total:
        # one timeout for process spawn and one timeout for process communicate.
        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",
                    tmp_path,
                    "--print",
                    "%(title)s",
                    "--no-download",
                    test_url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=10.0,
            )
            await asyncio.wait_for(process.communicate(), timeout=10.0)

            if process.returncode == 0:
                logger.info("Cookie validation succeeded")
                return True
            logger.warning("Cookie validation failed")
            return False
        except TimeoutError:
            logger.warning("Cookie validation timed out")
            return False
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
