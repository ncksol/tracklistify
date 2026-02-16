"""Result aggregator service - the secret sauce.

Takes raw fingerprint results and produces a clean tracklist by:
- Merging consecutive matches
- Detecting transitions
- Filtering by confidence
- Identifying gaps
- Deduplicating via fuzzy matching
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class SegmentResult:
    """Raw fingerprint result for a single segment."""

    segment_index: int
    start_ms: int
    end_ms: int
    title: str | None
    artist: str | None
    album: str | None
    confidence: float | None


@dataclass
class AggregatedTrack:
    """Aggregated track after processing."""

    position: int
    start_ms: int
    end_ms: int
    title: str | None
    artist: str | None
    album: str | None
    avg_confidence: float
    is_transition: bool


@dataclass
class UnidentifiedGap:
    """Gap where no track was identified."""

    start_ms: int
    end_ms: int


_NEUTRAL_SUFFIXES = re.compile(
    r"\s*\("
    r"(?:original(?:\s+mix)?|edit|radio\s+edit|album\s+version|extended(?:\s+mix)?|"
    r"main\s+mix|club\s+mix|club\s+edit|radio\s+version)"
    r"\)\s*$",
    re.IGNORECASE,
)


def _normalize_string(s: str | None) -> str:
    """Normalize string for comparison (lowercase, strip, remove neutral suffixes)."""
    if s is None:
        return ""
    normalized = s.lower().strip()
    # Strip only neutral version suffixes — keep meaningful ones like (Remix), (VIP), (Dub)
    normalized = _NEUTRAL_SUFFIXES.sub("", normalized)
    return normalized


def _fuzzy_match(s1: str | None, s2: str | None, threshold: float = 0.90) -> bool:
    """Check if two strings match using fuzzy comparison."""
    norm1 = _normalize_string(s1)
    norm2 = _normalize_string(s2)

    if not norm1 or not norm2:
        return norm1 == norm2

    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold


def _tracks_match(seg1: SegmentResult, seg2: SegmentResult) -> bool:
    """Check if two segments represent the same track using fuzzy matching."""
    # Both must have title and artist
    if seg1.title is None or seg1.artist is None:
        return False
    if seg2.title is None or seg2.artist is None:
        return False

    title_match = _fuzzy_match(seg1.title, seg2.title)
    artist_match = _fuzzy_match(seg1.artist, seg2.artist)

    return title_match and artist_match


def _is_valid_match(segment: SegmentResult, confidence_threshold: float = 0.50) -> bool:
    """Check if segment is a valid match (has metadata and meets confidence threshold)."""
    if segment.title is None or segment.artist is None:
        return False
    return not (segment.confidence is None or segment.confidence < confidence_threshold)


@dataclass
class _TrackAccumulator:
    """Internal state for accumulating track data."""

    segments: list[SegmentResult]
    start_ms: int
    end_ms: int
    total_confidence: float
    count: int


def aggregate_results(
    segments: list[SegmentResult],
    confidence_threshold: float = 0.50,
) -> tuple[list[AggregatedTrack], list[UnidentifiedGap]]:
    """Aggregate raw segment results into clean tracklist.

    Args:
        segments: List of raw fingerprint results, ordered by segment_index
        confidence_threshold: Minimum confidence to consider a match valid

    Returns:
        Tuple of (aggregated_tracks, unidentified_gaps)
    """
    if not segments:
        return [], []

    tracks: list[AggregatedTrack] = []
    gaps: list[UnidentifiedGap] = []

    current_track: _TrackAccumulator | None = None
    unmatched_run: list[SegmentResult] = []

    def emit_current_track() -> None:
        """Emit the current accumulated track."""
        nonlocal current_track
        if current_track is None:
            return

        # Use metadata from first segment in the run
        first_seg = current_track.segments[0]
        avg_conf = current_track.total_confidence / current_track.count

        # Check for transitions: if track alternates with another track
        is_transition = _detect_transition(current_track.segments)

        track = AggregatedTrack(
            position=len(tracks) + 1,
            start_ms=current_track.start_ms,
            end_ms=current_track.end_ms,
            title=first_seg.title,
            artist=first_seg.artist,
            album=first_seg.album,
            avg_confidence=avg_conf,
            is_transition=is_transition,
        )
        tracks.append(track)
        current_track = None

    def emit_gap() -> None:
        """Emit unmatched segments as a gap if 3+ consecutive."""
        nonlocal unmatched_run
        if len(unmatched_run) >= 3:
            gap = UnidentifiedGap(
                start_ms=unmatched_run[0].start_ms,
                end_ms=unmatched_run[-1].end_ms,
            )
            gaps.append(gap)
        unmatched_run = []

    for segment in segments:
        if not _is_valid_match(segment, confidence_threshold):
            # Unmatched segment — buffer it, don't emit current track yet
            unmatched_run.append(segment)
            continue

        # Valid match found
        if unmatched_run:
            if current_track is not None and len(unmatched_run) <= 2 and _tracks_match(segment, current_track.segments[-1]):
                # Same track resumes after a short gap — bridge it
                current_track.segments.append(segment)
                current_track.end_ms = segment.end_ms
                current_track.total_confidence += segment.confidence or 0.0
                current_track.count += 1
                unmatched_run = []
                continue
            # Gap too long or different track — emit current track and gap
            if current_track is not None:
                emit_current_track()
            emit_gap()

        # Check if this continues the current track
        if current_track is not None:
            last_seg = current_track.segments[-1]
            if _tracks_match(segment, last_seg):
                # Same track - accumulate
                current_track.segments.append(segment)
                current_track.end_ms = segment.end_ms
                current_track.total_confidence += segment.confidence or 0.0
                current_track.count += 1
            else:
                # Different track - emit current and start new
                emit_current_track()
                current_track = _TrackAccumulator(
                    segments=[segment],
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    total_confidence=segment.confidence or 0.0,
                    count=1,
                )
        else:
            # Start new track
            current_track = _TrackAccumulator(
                segments=[segment],
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                total_confidence=segment.confidence or 0.0,
                count=1,
            )

    # Emit any remaining track or gap
    if current_track is not None:
        emit_current_track()
    if unmatched_run:
        emit_gap()

    # Post-process: detect transitions between adjacent tracks
    _mark_transitions(tracks)

    return tracks, gaps


def _detect_transition(segments: list[SegmentResult]) -> bool:
    """Detect if segments show internal alternation (transition zone)."""
    # Given our grouping logic, segments here should all match the same track.
    # Real transition detection happens between tracks in _mark_transitions.
    # This function is kept for potential future enhancement.
    return False


def _mark_transitions(tracks: list[AggregatedTrack]) -> None:
    """Mark tracks that are in transition zones (alternating between two tracks)."""
    if len(tracks) < 2:
        return

    for i in range(len(tracks) - 1):
        current = tracks[i]
        next_track = tracks[i + 1]

        # Check if there's temporal overlap or very close proximity
        # If end of current track is very close to start of next (< 5 seconds)
        # and they're different tracks, mark as transition
        gap_ms = next_track.start_ms - current.end_ms

        # Check if this looks like a DJ transition (short overlap/gap)
        if gap_ms < 5000 and abs(gap_ms) < 2000:  # Less than 5s and within 2s
            current.is_transition = True
            next_track.is_transition = True
