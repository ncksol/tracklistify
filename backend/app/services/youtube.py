"""YouTube download service using yt-dlp."""

import asyncio
import os
import re


def _is_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube URL."""
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://(www\.)?youtu\.be/[\w-]+",
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE", "/app/cookies/cookies.txt")


def _get_cookies_args() -> list[str]:
    """Return yt-dlp cookies arguments if a cookies file is available."""
    if os.path.isfile(_COOKIES_FILE):
        return ["--cookies", _COOKIES_FILE]
    return []


async def _run_ytdlp(args: list[str]) -> tuple[str, str]:
    """Run yt-dlp with given arguments and return stdout, stderr."""
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--js-runtimes", "nodejs",
        *_get_cookies_args(),
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed with exit code {process.returncode}: {stderr.decode().strip()}"
        )

    return stdout.decode().strip(), stderr.decode().strip()


async def validate_url(url: str) -> dict[str, str]:
    """
    Validate YouTube URL and extract metadata.

    Args:
        url: YouTube video URL

    Returns:
        Dictionary with 'title', 'duration', and 'description' keys

    Raises:
        ValueError: If URL is invalid or not a YouTube URL
        RuntimeError: If yt-dlp execution fails
    """
    if not _is_youtube_url(url):
        raise ValueError("URL must be a valid YouTube URL (youtube.com/watch or youtu.be)")

    try:
        stdout, _ = await _run_ytdlp(
            [
                "--print",
                "%(title)s",
                "--print",
                "%(duration_string)s",
                "--print",
                "%(description)s",
                "--no-download",
                url,
            ]
        )
    except RuntimeError as e:
        raise ValueError(f"Invalid or unavailable YouTube video: {e}") from e

    # Parse output: first line is title, second is duration, rest is description
    lines = stdout.split("\n")
    if len(lines) < 2:
        raise ValueError("Unable to extract video metadata")

    title = lines[0]
    duration = lines[1]
    description = "\n".join(lines[2:]) if len(lines) > 2 else ""

    return {
        "title": title,
        "duration": duration,
        "description": description,
    }


async def download_audio(url: str, output_path: str) -> str:
    """
    Download audio from YouTube video as WAV file.

    Args:
        url: YouTube video URL
        output_path: Path where the WAV file should be saved

    Returns:
        Path to the downloaded WAV file

    Raises:
        ValueError: If URL is not a valid YouTube URL
        RuntimeError: If download fails
    """
    if not _is_youtube_url(url):
        raise ValueError("URL must be a valid YouTube URL (youtube.com/watch or youtu.be)")

    await _run_ytdlp(
        [
            "-x",
            "--audio-format",
            "wav",
            "-o",
            output_path,
            url,
        ]
    )

    return output_path
