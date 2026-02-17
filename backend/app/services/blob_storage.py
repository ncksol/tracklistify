"""Azure Blob Storage helper service for audio file management."""

import contextlib
import os
from pathlib import Path

import aiofiles  # type: ignore[import-untyped]
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Module-level configuration
STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "tracklistify-temp-audio")


def _is_storage_configured() -> bool:
    """Check if Azure Storage is configured with real credentials."""
    if STORAGE_CONNECTION_STRING and not STORAGE_CONNECTION_STRING.startswith("your_"):
        return True
    return bool(STORAGE_ACCOUNT_NAME)


def _get_blob_service_client() -> BlobServiceClient:
    """Get an async BlobServiceClient instance.

    Returns:
        BlobServiceClient: Async blob service client

    Raises:
        ValueError: If neither connection string nor storage account name is configured
    """
    if not _is_storage_configured():
        raise ValueError(
            "Either AZURE_STORAGE_CONNECTION_STRING or STORAGE_ACCOUNT_NAME must be set"
        )

    # If connection string is set, use it (local dev)
    if STORAGE_CONNECTION_STRING and not STORAGE_CONNECTION_STRING.startswith("your_"):
        return BlobServiceClient.from_connection_string(STORAGE_CONNECTION_STRING)

    # Cloud: use managed identity
    if STORAGE_ACCOUNT_NAME:
        from azure.identity.aio import DefaultAzureCredential

        account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
        return BlobServiceClient(account_url, credential=DefaultAzureCredential())

    raise ValueError("Storage configuration error")  # Should not reach here


async def upload_audio(job_id: str, file_path: str) -> str:
    """Upload a local audio file to Azure Blob Storage.

    Args:
        job_id: Job identifier to use as prefix in blob name
        file_path: Path to the local file to upload

    Returns:
        str: URL of the uploaded blob

    Raises:
        FileNotFoundError: If the local file doesn't exist
        ValueError: If connection string is not configured
    """
    if not _is_storage_configured():
        return f"local://{file_path}"

    local_file = Path(file_path)
    if not local_file.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Create blob name with job_id prefix
    blob_name = f"{job_id}/{local_file.name}"

    async with _get_blob_service_client() as blob_service_client:
        container_client = blob_service_client.get_container_client(STORAGE_CONTAINER)

        # Create container if it doesn't exist
        with contextlib.suppress(Exception):
            await container_client.create_container()

        # Upload the file (stream from disk to avoid loading into memory)
        blob_client = container_client.get_blob_client(blob_name)
        with open(file_path, "rb") as data:
            await blob_client.upload_blob(data, overwrite=True)

        return blob_client.url


async def download_audio(blob_name: str, local_path: str) -> str:
    """Download an audio file from Azure Blob Storage to local path.

    Args:
        blob_name: Name of the blob to download
        local_path: Path where the file should be saved locally

    Returns:
        str: Path to the downloaded file (same as local_path)

    Raises:
        ValueError: If connection string is not configured
    """
    # Ensure the directory exists
    local_file = Path(local_path)
    local_file.parent.mkdir(parents=True, exist_ok=True)

    async with _get_blob_service_client() as blob_service_client:
        container_client = blob_service_client.get_container_client(STORAGE_CONTAINER)
        blob_client = container_client.get_blob_client(blob_name)

        # Download the blob
        download_stream = await blob_client.download_blob()
        content = await download_stream.readall()

        # Write to local file
        async with aiofiles.open(local_path, "wb") as f:
            await f.write(content)

    return local_path


async def delete_audio(blob_name: str) -> None:
    """Delete an audio file from Azure Blob Storage.

    Args:
        blob_name: Name of the blob to delete

    Raises:
        ValueError: If connection string is not configured
    """
    if not _is_storage_configured():
        return

    async with _get_blob_service_client() as blob_service_client:
        container_client = blob_service_client.get_container_client(STORAGE_CONTAINER)
        blob_client = container_client.get_blob_client(blob_name)

        # Delete the blob (ignore if it doesn't exist)
        await blob_client.delete_blob()
