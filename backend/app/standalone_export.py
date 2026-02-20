"""Standalone output rendering helpers for identify command results."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from pathlib import Path


class StandaloneTrack(TypedDict):
    """Serialized aggregated track payload."""

    position: int
    start_ms: int
    end_ms: int
    title: str | None
    artist: str | None
    album: str | None
    avg_confidence: float
    is_transition: bool


class StandaloneGap(TypedDict):
    """Serialized unidentified gap payload."""

    start_ms: int
    end_ms: int


class StandaloneMetadata(TypedDict):
    """Top-level metadata payload for identify results."""

    url: str
    title: str
    duration: str
    description: str
    confidence_threshold: float
    segment_count: int
    matched_segment_count: int


class StandaloneIdentifyResult(TypedDict):
    """Structured identify command result."""

    tracks: list[StandaloneTrack]
    gaps: list[StandaloneGap]
    metadata: StandaloneMetadata


def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to HH:MM:SS timestamp format."""
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _render_as_text(result: StandaloneIdentifyResult) -> str:
    lines: list[str] = []
    all_items: list[tuple[int, str, StandaloneTrack | StandaloneGap]] = []

    for track in result["tracks"]:
        all_items.append((track["start_ms"], "track", track))

    for gap in result["gaps"]:
        all_items.append((gap["start_ms"], "gap", gap))

    all_items.sort(key=lambda x: x[0])

    for _, item_type, item in all_items:
        if item_type == "track":
            track = cast("StandaloneTrack", item)
            timestamp = ms_to_timestamp(track["start_ms"])
            artist = track["artist"] or "Unknown Artist"
            title = track["title"] or "Unknown Title"
            lines.append(f"{track['position']:02d}. [{timestamp}] {artist} - {title}")
        else:
            gap = cast("StandaloneGap", item)
            start_ts = ms_to_timestamp(gap["start_ms"])
            end_ts = ms_to_timestamp(gap["end_ms"])
            lines.append(f"-- [{start_ts} - {end_ts}] Unidentified")

    return "\n".join(lines)


def _render_as_json(result: StandaloneIdentifyResult) -> str:
    return json.dumps(result, indent=2)


def render_identify_result(*, result: StandaloneIdentifyResult, output_format: str) -> str:
    """Render identify result as text or JSON."""
    if output_format == "text":
        return _render_as_text(result)
    if output_format == "json":
        return _render_as_json(result)

    msg = f"Unsupported output format: {output_format}"
    raise ValueError(msg)


def write_identify_output(
    *,
    result: StandaloneIdentifyResult,
    output_format: str,
    output_path: Path | None,
) -> None:
    """Write rendered identify output to stdout or file."""
    rendered_output = render_identify_result(result=result, output_format=output_format)
    output = f"{rendered_output}\n"

    if output_path is None:
        sys.stdout.write(output)
        return

    output_path.write_text(output, encoding="utf-8")
