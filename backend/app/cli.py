"""Standalone command-line contract for local track identification."""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias
from urllib.parse import urlparse

from app.services.aggregator import SegmentResult, aggregate_results
from app.services.audio import segment_audio
from app.services.fingerprint import identify_segment
from app.services.youtube import download_audio, validate_url
from app.standalone_export import (
    StandaloneGap,
    StandaloneIdentifyResult,
    StandaloneMetadata,
    StandaloneTrack,
    write_identify_output,
)

if TYPE_CHECKING:
    from collections.abc import Callable


IdentifyTrack: TypeAlias = StandaloneTrack  # noqa: UP040
IdentifyGap: TypeAlias = StandaloneGap  # noqa: UP040
IdentifyMetadata: TypeAlias = StandaloneMetadata  # noqa: UP040
IdentifyResult: TypeAlias = StandaloneIdentifyResult  # noqa: UP040


def _emit_progress(phase: str, message: str) -> None:
    """Emit local CLI pipeline progress updates to stderr."""
    print(f"[{phase}] {message}", file=sys.stderr, flush=True)


async def _batch_fingerprint_segments(
    segments: list[dict[str, Any]],
    *,
    max_concurrent: int = 3,
    throttle_seconds: float = 0.3,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> list[SegmentResult]:
    """Fingerprint segments locally with bounded concurrency and throttle."""
    semaphore = asyncio.Semaphore(max_concurrent)
    total_segments = len(segments)
    progress_step = max(total_segments // 10, 1) if total_segments else 1
    progress_lock = asyncio.Lock()
    completed_segments = 0
    tracks_found = 0

    async def fingerprint_with_semaphore(segment: dict[str, Any], index: int) -> SegmentResult:
        nonlocal completed_segments, tracks_found

        async with semaphore:
            match = await identify_segment(str(segment["path"]))
            await asyncio.sleep(throttle_seconds)

        result: SegmentResult
        if match is None:
            result = SegmentResult(
                segment_index=index,
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                title=None,
                artist=None,
                album=None,
                confidence=None,
            )
        else:
            result = SegmentResult(
                segment_index=index,
                start_ms=int(segment["start_ms"]),
                end_ms=int(segment["end_ms"]),
                title=match.get("title"),
                artist=match.get("artist"),
                album=match.get("album"),
                confidence=match.get("confidence_score"),
            )

        async with progress_lock:
            completed_segments += 1
            if result.title is not None:
                tracks_found += 1
            if on_progress and (
                completed_segments % progress_step == 0 or completed_segments == total_segments
            ):
                on_progress(completed_segments, total_segments, tracks_found)

        return result

    tasks = [fingerprint_with_semaphore(segment, index) for index, segment in enumerate(segments)]
    return list(await asyncio.gather(*tasks))


def _http_url(value: str) -> str:
    """Validate that the provided value is an absolute HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = "URL must be an absolute http(s) URL."
        raise argparse.ArgumentTypeError(msg)
    return value


def _existing_file(value: str) -> Path:
    """Validate that the provided path points to an existing file."""
    path = Path(value)
    if not path.is_file():
        msg = f"File not found: {path}"
        raise argparse.ArgumentTypeError(msg)
    return path


def _confidence_threshold(value: str) -> float:
    """Validate confidence threshold as a float between 0.0 and 1.0."""
    try:
        threshold = float(value)
    except ValueError as exc:
        msg = "Confidence threshold must be a float."
        raise argparse.ArgumentTypeError(msg) from exc

    if not 0.0 <= threshold <= 1.0:
        msg = "Confidence threshold must be between 0.0 and 1.0."
        raise argparse.ArgumentTypeError(msg)
    return threshold


def _output_path(value: str) -> Path:
    """Validate output path parent exists."""
    path = Path(value)
    if not path.parent.exists():
        msg = f"Output directory not found: {path.parent}"
        raise argparse.ArgumentTypeError(msg)
    return path


def build_parser() -> argparse.ArgumentParser:
    """Create the argparse command contract for standalone CLI usage."""
    parser = argparse.ArgumentParser(
        prog="tracklistify",
        description="Standalone CLI for local Tracklistify processing.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    identify_parser = subparsers.add_parser(
        "identify",
        help="Identify tracks from a source URL.",
    )
    identify_parser.add_argument("url", type=_http_url, help="Source URL to process.")
    identify_parser.add_argument(
        "--cookie-file",
        type=_existing_file,
        metavar="PATH",
        help="Path to a local cookie file for extraction tools.",
    )
    identify_parser.add_argument(
        "--confidence-threshold",
        type=_confidence_threshold,
        default=0.50,
        metavar="FLOAT",
        help="Minimum match confidence between 0.0 and 1.0.",
    )
    identify_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format for CLI result rendering.",
    )
    identify_parser.add_argument(
        "--output",
        type=_output_path,
        metavar="PATH",
        help="Write output to PATH instead of stdout.",
    )
    return parser


def run_identify(
    *,
    url: str,
    cookie_file: Path | None,
    confidence_threshold: float,
) -> IdentifyResult:
    """Run standalone identify pipeline in-process and return structured results."""
    cookie_path = str(cookie_file) if cookie_file is not None else None

    with tempfile.TemporaryDirectory(prefix="tracklistify_cli_") as workspace:
        workspace_path = Path(workspace)
        audio_path = workspace_path / "audio.wav"
        segments_path = workspace_path / "segments"

        _emit_progress("DOWNLOADING", "Validating source URL...")
        metadata = asyncio.run(validate_url(url, cookie_path=cookie_path))
        _emit_progress("DOWNLOADING", "Downloading source audio...")
        asyncio.run(download_audio(url, str(audio_path), cookie_path=cookie_path))
        _emit_progress("SEGMENTING", "Creating 12s segments with 6s hop...")
        segments = segment_audio(
            input_path=str(audio_path),
            output_dir=str(segments_path),
            window_seconds=12,
            hop_seconds=6,
        )
        _emit_progress("FINGERPRINTING", f"Fingerprinting {len(segments)} segments...")

        def _fingerprint_progress(completed: int, total: int, matched: int) -> None:
            _emit_progress(
                "FINGERPRINTING",
                f"Processed segments {completed}/{total} | tracks found {matched}",
            )

        fingerprint_results = asyncio.run(
            _batch_fingerprint_segments(
                segments,
                max_concurrent=3,
                throttle_seconds=0.3,
                on_progress=_fingerprint_progress,
            )
        )
        _emit_progress("AGGREGATING", "Merging fingerprint results...")
        aggregated_tracks, unidentified_gaps = aggregate_results(
            fingerprint_results,
            confidence_threshold=confidence_threshold,
        )

    tracks: list[IdentifyTrack] = [
        {
            "position": track.position,
            "start_ms": track.start_ms,
            "end_ms": track.end_ms,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "avg_confidence": track.avg_confidence,
            "is_transition": track.is_transition,
        }
        for track in aggregated_tracks
    ]
    gaps: list[IdentifyGap] = [
        {
            "start_ms": gap.start_ms,
            "end_ms": gap.end_ms,
        }
        for gap in unidentified_gaps
    ]
    matched_segments = sum(1 for result in fingerprint_results if result.title is not None)
    _emit_progress(
        "COMPLETE",
        f"Finished {len(fingerprint_results)} segments with {matched_segments} matches",
    )

    return {
        "tracks": tracks,
        "gaps": gaps,
        "metadata": {
            "url": url,
            "title": str(metadata.get("title", "")),
            "duration": str(metadata.get("duration", "")),
            "description": str(metadata.get("description", "")),
            "confidence_threshold": confidence_threshold,
            "segment_count": len(fingerprint_results),
            "matched_segment_count": matched_segments,
        },
    }


def _render_identify_result(
    *,
    result: IdentifyResult,
    output_format: str,
    output_path: Path | None,
) -> None:
    """Render identify result output to stdout or a file."""
    write_identify_output(
        result=result,
        output_format=output_format,
        output_path=output_path,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and execute the selected command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "identify":
            result = run_identify(
                url=args.url,
                cookie_file=args.cookie_file,
                confidence_threshold=args.confidence_threshold,
            )
            _render_identify_result(
                result=result,
                output_format=args.format,
                output_path=args.output,
            )
            return 0
    except NotImplementedError as exc:
        parser.exit(status=1, message=f"{exc}\n")
    except (ValueError, RuntimeError) as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
