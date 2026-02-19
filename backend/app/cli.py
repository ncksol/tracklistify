"""Command line interface for Tracklistify identification."""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiohttp

DEFAULT_API_URL = os.getenv("TRACKLISTIFY_API_URL", "http://localhost:8000")
FINAL_STATUSES = {"COMPLETE", "FAILED"}


def _extract_error_detail(payload_text: str) -> str:
    """Extract error detail from an API response body."""
    stripped = payload_text.strip()
    if not stripped:
        return "unknown error"

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail)
    return stripped


async def _request_json(
    *,
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Send an HTTP request and parse JSON response."""
    async with session.request(method, url, **kwargs) as response:
        payload_text = await response.text()

    if response.status >= 400:
        detail = _extract_error_detail(payload_text)
        raise RuntimeError(f"{method} {url} failed ({response.status}): {detail}")

    if not payload_text:
        return {}

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}") from exc

    if isinstance(payload, dict):
        return payload
    raise RuntimeError(f"Unexpected response shape from {url}")


async def _submit_job(
    *,
    session: aiohttp.ClientSession,
    api_url: str,
    youtube_url: str,
    force: bool,
    confidence_threshold: float,
    cookie_file: Path | None,
) -> dict[str, Any]:
    """Submit a job using JSON or multipart based on cookie presence."""
    endpoint = f"{api_url.rstrip('/')}/api/jobs"

    if cookie_file is None:
        return await _request_json(
            session=session,
            method="POST",
            url=endpoint,
            json={
                "url": youtube_url,
                "force": force,
                "confidence_threshold": confidence_threshold,
            },
        )

    if not cookie_file.exists():
        raise RuntimeError(f"Cookie file does not exist: {cookie_file}")

    try:
        cookie_bytes = cookie_file.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Failed to read cookie file: {cookie_file}") from exc
    form = aiohttp.FormData()
    form.add_field("url", youtube_url)
    form.add_field("force", str(force).lower())
    form.add_field("confidence_threshold", str(confidence_threshold))
    form.add_field(
        "cookie_file",
        cookie_bytes,
        filename=cookie_file.name,
        content_type="text/plain",
    )

    return await _request_json(
        session=session,
        method="POST",
        url=endpoint,
        data=form,
    )


def _format_timestamp(milliseconds: int) -> str:
    """Format milliseconds into mm:ss or h:mm:ss."""
    total_seconds = max(milliseconds, 0) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _print_events(events: list[dict[str, Any]]) -> str | None:
    """Print event rows and return latest timestamp."""
    latest_timestamp: str | None = None
    for event in events:
        timestamp = str(event.get("timestamp", ""))
        latest_timestamp = timestamp or latest_timestamp
        timestamp_display = timestamp[11:19] if len(timestamp) >= 19 else timestamp
        progress = int(event.get("progress", 0))
        phase = str(event.get("phase", "UNKNOWN"))
        message = str(event.get("message", ""))
        print(f"{timestamp_display}  {progress:3d}%  [{phase}] {message}")
    return latest_timestamp


async def _wait_for_completion(
    *,
    session: aiohttp.ClientSession,
    api_url: str,
    job_id: str,
    poll_interval: float,
) -> dict[str, Any]:
    """Poll events and status until the job is complete or failed."""
    base = api_url.rstrip("/")
    status_url = f"{base}/api/jobs/{job_id}"
    events_url = f"{base}/api/jobs/{job_id}/events"
    last_event_timestamp: str | None = None

    while True:
        params: dict[str, str] | None = None
        if last_event_timestamp:
            params = {"after": last_event_timestamp}

        events_payload = await _request_json(
            session=session,
            method="GET",
            url=events_url,
            params=params,
        )
        events = events_payload.get("events", [])
        if isinstance(events, list):
            maybe_latest = _print_events(events)
            if maybe_latest:
                last_event_timestamp = maybe_latest

        status_payload = await _request_json(
            session=session,
            method="GET",
            url=status_url,
        )
        status = str(status_payload.get("status", ""))
        if status in FINAL_STATUSES:
            return status_payload

        await asyncio.sleep(poll_interval)


def _print_tracklist(tracklist: dict[str, Any], *, json_output: bool) -> None:
    """Print final tracklist in human-readable or JSON format."""
    if json_output:
        print(json.dumps(tracklist, indent=2))
        return

    tracks = tracklist.get("tracks", [])
    unidentified_segments = tracklist.get("unidentified_segments", [])

    print("\nTracklist:")
    if not isinstance(tracks, list) or not tracks:
        print("  No tracks identified.")
    else:
        for track in tracks:
            position = int(track.get("position", 0))
            start = _format_timestamp(int(track.get("start_time_ms", 0)))
            artist = str(track.get("artist") or "Unknown Artist")
            title = str(track.get("title") or "Unknown Title")
            confidence_raw = track.get("confidence_score")
            confidence_suffix = ""
            if isinstance(confidence_raw, int | float):
                confidence_suffix = f" ({round(confidence_raw * 100):.0f}%)"
            print(f"  {position:2d}. {start}  {artist} — {title}{confidence_suffix}")

    if isinstance(unidentified_segments, list) and unidentified_segments:
        print("\nUnidentified segments:")
        for segment in unidentified_segments:
            start = _format_timestamp(int(segment.get("start_time_ms", 0)))
            end = _format_timestamp(int(segment.get("end_time_ms", 0)))
            print(f"  - {start} - {end}")


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(
        prog="tracklistify-cli",
        description="Run Tracklistify identification from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    identify_parser = subparsers.add_parser(
        "identify",
        help="Submit a YouTube URL for track identification.",
    )
    identify_parser.add_argument("url", help="YouTube URL to identify.")
    identify_parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="Tracklistify backend URL (default: %(default)s).",
    )
    identify_parser.add_argument(
        "--cookie-file",
        type=Path,
        default=None,
        help="Path to Netscape-format YouTube cookie .txt file.",
    )
    identify_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reanalysis even if a completed cached job exists.",
    )
    identify_parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.5,
        help="Minimum confidence threshold (0.0-1.0).",
    )
    identify_parser.add_argument(
        "--poll-interval",
        type=float,
        default=5.0,
        help="Polling interval in seconds while waiting for completion.",
    )
    identify_parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Submit job and exit immediately.",
    )
    identify_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print final tracklist as JSON.",
    )

    return parser


async def run_cli(argv: Sequence[str]) -> int:
    """Run CLI with parsed args."""
    parser = build_parser()
    args = parser.parse_args(list(argv))

    if args.command != "identify":
        parser.error("Unknown command")

    if not 0.0 <= args.confidence_threshold <= 1.0:
        parser.error("--confidence-threshold must be between 0.0 and 1.0")
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be positive")

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            job = await _submit_job(
                session=session,
                api_url=args.api_url,
                youtube_url=args.url,
                force=args.force,
                confidence_threshold=args.confidence_threshold,
                cookie_file=args.cookie_file,
            )
        except (aiohttp.ClientError, RuntimeError) as exc:
            print(f"Failed to submit job: {exc}", file=sys.stderr)
            return 1

        job_id = str(job.get("id", ""))
        print(f"Submitted job: {job_id}")

        if args.no_wait:
            return 0

        try:
            final_status = await _wait_for_completion(
                session=session,
                api_url=args.api_url,
                job_id=job_id,
                poll_interval=args.poll_interval,
            )
        except (aiohttp.ClientError, RuntimeError) as exc:
            print(f"Failed while polling job: {exc}", file=sys.stderr)
            return 1

        if final_status.get("status") != "COMPLETE":
            error_message = str(final_status.get("error_message") or "unknown error")
            print(f"Job failed: {error_message}", file=sys.stderr)
            return 1

        tracklist = await _request_json(
            session=session,
            method="GET",
            url=f"{args.api_url.rstrip('/')}/api/jobs/{job_id}/tracklist",
        )
        _print_tracklist(tracklist, json_output=args.json_output)
        return 0


def main() -> None:
    """Entrypoint for installed console script."""
    raise SystemExit(asyncio.run(run_cli(sys.argv[1:])))


if __name__ == "__main__":
    main()
