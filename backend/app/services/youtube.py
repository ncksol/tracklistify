"""YouTube download service using yt-dlp."""

import asyncio
import contextlib
import os
import re
import shutil
import tempfile


def _is_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube URL."""
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://(www\.)?youtu\.be/[\w-]+",
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def _get_cookies_args(cookie_path: str | None = None) -> list[str]:
    """Return yt-dlp cookies arguments if a cookies file is available.

    Copies to a temp file because yt-dlp writes back to the cookies file
    and the source mount may be read-only.

    Args:
        cookie_path: Optional explicit cookie file path to use

    Returns:
        List of yt-dlp arguments for cookies, or empty list if no cookie available
    """
    cookies_file = cookie_path or os.getenv("YTDLP_COOKIES_FILE") or "/app/cookies/cookies.txt"

    if os.path.isfile(cookies_file):
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        os.close(tmp_fd)
        shutil.copy2(cookies_file, tmp_path)
        return ["--cookies", tmp_path]
    return []


_YTDLP_BASE = ["yt-dlp", "--js-runtimes", "node", "--remote-components", "ejs:github"]


async def _run_ytdlp(args: list[str], cookie_path: str | None = None) -> tuple[str, str]:
    """Run yt-dlp with given arguments and return stdout, stderr.

    If cookies are available, tries with cookies first.
    Falls back to running without cookies on failure.

    Args:
        args: yt-dlp command line arguments
        cookie_path: Optional explicit cookie file path to use

    Returns:
        Tuple of (stdout, stderr) as strings
    """
    cookies_args = _get_cookies_args(cookie_path)
    try:
        process = await asyncio.create_subprocess_exec(
            *_YTDLP_BASE,
            *cookies_args,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    finally:
        if cookies_args:
            with contextlib.suppress(OSError):
                os.unlink(cookies_args[1])

    if process.returncode != 0 and cookies_args:
        first_stderr = stderr.decode().strip()
        # Retry without cookies - they may be expired
        process = await asyncio.create_subprocess_exec(
            *_YTDLP_BASE,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(
                f"yt-dlp failed (retry without cookies also failed).\n"
                f"Original error: {first_stderr}\n"
                f"Retry error: {stderr.decode().strip()}"
            )

    elif process.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed with exit code {process.returncode}: {stderr.decode().strip()}"
        )

    return stdout.decode().strip(), stderr.decode().strip()


async def validate_url(url: str, cookie_path: str | None = None) -> dict[str, str]:
    """
    Validate YouTube URL and extract metadata.

    Args:
        url: YouTube video URL
        cookie_path: Optional explicit cookie file path to use

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
            ],
            cookie_path=cookie_path,
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


async def download_audio(url: str, output_path: str, cookie_path: str | None = None) -> str:
    """
    Download audio from YouTube video as WAV file.

    Args:
        url: YouTube video URL
        output_path: Path where the WAV file should be saved
        cookie_path: Optional explicit cookie file path to use

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
        ],
        cookie_path=cookie_path,
    )

    return output_path
