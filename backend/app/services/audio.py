"""FFmpeg audio segmentation service for sliding window fingerprinting."""

import subprocess
from pathlib import Path
from typing import Any


def get_audio_duration(file_path: str) -> float:
    """
    Get the duration of an audio file in seconds using ffprobe.

    Args:
        file_path: Path to the audio file

    Returns:
        Duration in seconds

    Raises:
        RuntimeError: If ffprobe fails or returns invalid output
    """
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed with return code {result.returncode}: {result.stderr}")

    try:
        duration = float(result.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"Invalid duration output from ffprobe: {result.stdout}") from e

    return duration


def segment_audio(
    input_path: str,
    output_dir: str,
    window_seconds: int = 12,
    hop_seconds: int = 6,
) -> list[dict[str, Any]]:
    """
    Split an audio file into overlapping segments using FFmpeg.

    Uses a sliding window approach with configurable window size and hop size.
    Each segment is exported as 16kHz mono WAV (optimal for fingerprinting).

    Args:
        input_path: Path to the input audio file
        output_dir: Directory to save segment files
        window_seconds: Window size in seconds (default: 12)
        hop_seconds: Hop size in seconds (default: 6, 50% overlap)

    Returns:
        List of segment metadata dicts with keys:
        - path: Absolute path to the segment file
        - start_ms: Start timestamp in milliseconds
        - end_ms: End timestamp in milliseconds

    Example:
        >>> segments = await segment_audio("mix.mp3", "/tmp/segments")
        >>> segments[0]
        {"path": "/tmp/segments/segment_000.wav", "start_ms": 0, "end_ms": 12000}
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get total duration
    total_duration = get_audio_duration(input_path)

    # Calculate segment boundaries
    segments: list[dict[str, Any]] = []
    segment_index = 0
    current_start = 0.0

    while current_start < total_duration:
        # Calculate segment boundaries
        start_seconds = current_start
        end_seconds = min(current_start + window_seconds, total_duration)
        duration_seconds = end_seconds - start_seconds

        # Skip very short segments at the end (< 1 second)
        if duration_seconds < 1.0:
            break

        # Generate output filename
        segment_filename = f"segment_{segment_index:03d}.wav"
        segment_path = output_path / segment_filename

        # Run FFmpeg to extract segment
        # -ss before -i enables fast input seeking (byte-accurate for WAV)
        result = subprocess.run(
            [
                "ffmpeg",
                "-ss",
                str(start_seconds),
                "-i",
                input_path,
                "-t",
                str(duration_seconds),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                str(segment_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed for segment {segment_index} "
                f"(return code {result.returncode}): {result.stderr}"
            )

        # Add segment metadata
        segments.append(
            {
                "path": str(segment_path.absolute()),
                "start_ms": int(start_seconds * 1000),
                "end_ms": int(end_seconds * 1000),
            }
        )

        # Move to next segment
        segment_index += 1
        current_start += hop_seconds

    return segments
