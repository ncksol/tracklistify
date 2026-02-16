"""ACRCloud audio fingerprinting service."""

import asyncio
import base64
import hashlib
import hmac
import os
import time
from typing import Any

import aiohttp

# Module-level cache for ACRCloud credentials
_acr_credentials: dict[str, str] | None = None


def _get_acr_credentials() -> dict[str, str]:
    """Get ACRCloud credentials from env vars or Key Vault.

    Returns:
        Dict with keys: access_key, access_secret, host

    Raises:
        ValueError: If credentials are not configured
    """
    global _acr_credentials  # noqa: PLW0603

    # Return cached credentials if already loaded
    if _acr_credentials is not None:
        return _acr_credentials

    # Try env vars first (local dev)
    access_key = os.getenv("ACR_ACCESS_KEY")
    access_secret = os.getenv("ACR_ACCESS_SECRET")
    acr_host = os.getenv("ACR_HOST")

    if access_key and access_secret and acr_host:
        _acr_credentials = {
            "access_key": access_key,
            "access_secret": access_secret,
            "host": acr_host,
        }
        return _acr_credentials

    # Try Key Vault (cloud)
    vault_url = os.getenv("KEY_VAULT_URI")
    if vault_url:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)

        access_key = client.get_secret("acr-access-key").value or ""
        access_secret = client.get_secret("acr-access-secret").value or ""
        acr_host = client.get_secret("acr-host").value or ""

        _acr_credentials = {
            "access_key": access_key,
            "access_secret": access_secret,
            "host": acr_host,
        }
        return _acr_credentials

    raise ValueError("ACRCloud credentials not found in environment variables or Key Vault")


async def identify_segment(audio_path: str) -> dict[str, Any] | None:
    """
    Identify an audio segment using ACRCloud's fingerprinting API.

    Args:
        audio_path: Path to the audio file to identify

    Returns:
        Dict with keys: title, artist, album, confidence_score, play_offset_ms
        Returns None if no match found or confidence below threshold
    """
    credentials = _get_acr_credentials()
    access_key = credentials["access_key"]
    access_secret = credentials["access_secret"]
    acr_host = credentials["host"]

    # Generate signature
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(int(time.time()))

    # Build string to sign
    string_to_sign = "\n".join(
        [
            http_method,
            http_uri,
            access_key,
            data_type,
            signature_version,
            timestamp,
        ]
    )

    # Create HMAC-SHA1 signature
    signature = base64.b64encode(
        hmac.new(
            access_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")

    # Read audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Make request with timeout and retry
    url = f"https://{acr_host}{http_uri}"
    timeout = aiohttp.ClientTimeout(total=30)

    result = None
    for attempt in range(3):
        try:
            form = aiohttp.FormData()
            form.add_field("sample", audio_data, filename="sample.wav")
            form.add_field("access_key", access_key)
            form.add_field("data_type", data_type)
            form.add_field("signature_version", signature_version)
            form.add_field("signature", signature)
            form.add_field("timestamp", timestamp)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(url, data=form) as response,
            ):
                if response.status != 200:
                    return None
                result = await response.json(content_type=None)
            break
        except (aiohttp.ClientError, TimeoutError):
            if attempt == 2:
                return None
            await asyncio.sleep(2**attempt)

    # Parse response
    if result is None or result.get("status", {}).get("code") != 0:
        return None

    metadata = result.get("metadata", {})
    music_list = metadata.get("music", [])

    if not music_list:
        return None

    # Extract first match
    match = music_list[0]

    # Check confidence threshold (ACRCloud scores are 0-100)
    confidence = match.get("score", 0)
    if confidence < 50:  # Threshold for minimum confidence
        return None

    # Extract track info
    title = match.get("title")
    artist = None
    album = None

    # Artists are in a list
    artists = match.get("artists", [])
    if artists:
        artist = artists[0].get("name")

    # Album info
    album_data = match.get("album", {})
    if album_data:
        album = album_data.get("name")

    # Play offset in milliseconds
    play_offset_ms = match.get("play_offset_ms", 0)

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "confidence_score": float(confidence) / 100.0,
        "play_offset_ms": int(play_offset_ms),
    }
