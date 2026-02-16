"""YouTube description/comments parser for extracting tracklists.

This module provides functionality to extract existing tracklists from YouTube
video descriptions, which DJs often include. This provides a "free" validation
layer for fingerprint results.
"""

import re


def timestamp_to_ms(timestamp: str) -> int:
    """Convert timestamp string to milliseconds.

    Supports both HH:MM:SS and MM:SS formats.

    Args:
        timestamp: Timestamp string in format "HH:MM:SS" or "MM:SS"

    Returns:
        Timestamp in milliseconds

    Examples:
        >>> timestamp_to_ms("01:23:45")
        5025000
        >>> timestamp_to_ms("1:23:45")
        5025000
        >>> timestamp_to_ms("23:45")
        1425000
        >>> timestamp_to_ms("0:45")
        45000
    """
    # Split by colon and reverse to handle from seconds backwards
    parts = timestamp.strip().split(":")

    hours_str: str
    minutes_str: str
    seconds_str: str

    if len(parts) == 2:
        # MM:SS format
        minutes_str, seconds_str = parts
        hours_str = "0"
    elif len(parts) == 3:
        # HH:MM:SS format
        hours_str, minutes_str, seconds_str = parts
    else:
        return 0

    try:
        total_seconds = int(hours_str) * 3600 + int(minutes_str) * 60 + int(seconds_str)
        return total_seconds * 1000
    except ValueError:
        return 0


def parse_tracklist(description: str) -> list[dict[str, str | int]]:
    """Parse a YouTube description for timestamp + track entries.

    Supports various common timestamp formats:
    - "01:23:45 Artist - Track Title"
    - "1:23:45 Artist - Track Title"
    - "23:45 Artist - Track"
    - "0:45 Artist - Track"
    - "[01:23:45] Artist - Track"
    - "01:23:45 - Artist - Track"

    Args:
        description: YouTube video description text

    Returns:
        List of dictionaries with keys:
        - "timestamp_ms": int (timestamp in milliseconds)
        - "artist": str (artist name, or empty string if not found)
        - "title": str (track title)
        Returns empty list if no tracklist found.

    Examples:
        >>> parse_tracklist("01:23:45 Artist Name - Track Title")
        [{'timestamp_ms': 5025000, 'artist': 'Artist Name', 'title': 'Track Title'}]
        >>> parse_tracklist("[0:45] Artist - Title")
        [{'timestamp_ms': 45000, 'artist': 'Artist', 'title': 'Title'}]
    """
    # Regex pattern to match timestamp entries
    # Matches: [optional bracket] HH:MM:SS or MM:SS [optional bracket] [optional dash] track info
    pattern = r"^[\s]*\[?(\d{1,2}:\d{1,2}(?::\d{2})?)\]?[\s]*-?[\s]+(.+)$"

    tracks: list[dict[str, str | int]] = []

    for line in description.split("\n"):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if not match:
            continue

        timestamp_str = match.group(1)
        track_info = match.group(2).strip()

        # Convert timestamp to milliseconds
        timestamp_ms = timestamp_to_ms(timestamp_str)
        if timestamp_ms == 0:
            continue

        # Clean up track_info - remove common prefixes like "01.", "1)", etc.
        track_info = re.sub(r"^[\d]+[\.\)]\s*", "", track_info)

        # Parse artist and title from track_info
        # Look for " - " (with spaces) as separator
        if " - " in track_info:
            parts = track_info.split(" - ", 1)  # Split only on first occurrence
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            # No separator found, treat whole string as title
            artist = ""
            title = track_info.strip()

        # Skip if both artist and title are empty
        if not artist and not title:
            continue

        tracks.append(
            {
                "timestamp_ms": timestamp_ms,
                "artist": artist,
                "title": title,
            }
        )

    return tracks
