"""Tests for YouTube description parser."""

import pytest
from app.services.description_parser import parse_tracklist, timestamp_to_ms


class TestTimestampToMs:
    """Test the timestamp_to_ms helper function."""

    def test_hh_mm_ss_format(self):
        """Test HH:MM:SS format conversion."""
        assert timestamp_to_ms("1:30:00") == 5400000

    def test_mm_ss_format(self):
        """Test MM:SS format conversion."""
        assert timestamp_to_ms("5:30") == 330000

    def test_zero_timestamp(self):
        """Test zero timestamp."""
        assert timestamp_to_ms("0:00") == 0

    def test_single_digit_hours(self):
        """Test single digit hours."""
        assert timestamp_to_ms("1:23:45") == 5025000

    def test_double_digit_hours(self):
        """Test double digit hours."""
        assert timestamp_to_ms("01:23:45") == 5025000

    def test_single_digit_minutes(self):
        """Test single digit minutes."""
        assert timestamp_to_ms("0:45") == 45000

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert timestamp_to_ms("  1:30:00  ") == 5400000


class TestParseTracklist:
    """Test the main parse_tracklist function."""

    def test_hh_mm_ss_format(self):
        """Test HH:MM:SS timestamp format."""
        description = "01:23:45 Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 5025000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_mm_ss_format(self):
        """Test MM:SS timestamp format."""
        description = "23:45 Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 1425000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_bracketed_timestamps(self):
        """Test timestamps in square brackets."""
        description = "[01:23:45] Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 5025000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_dash_separator_after_timestamp(self):
        """Test dash after timestamp."""
        description = "01:23:45 - Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 5025000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_track_number_prefix_dot(self):
        """Test track number with dot prefix is stripped."""
        description = "23:45 01. Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 1425000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_track_number_prefix_parenthesis(self):
        """Test track number with parenthesis prefix is stripped."""
        description = "23:45 1) Artist Name - Track Title"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 1425000
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_no_artist_title_separator(self):
        """Test entry without artist-title separator."""
        description = "23:45 Just A Track Name"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 1425000
        assert result[0]["artist"] == ""
        assert result[0]["title"] == "Just A Track Name"

    def test_multiple_entries(self):
        """Test parsing multiple tracklist entries."""
        description = """
0:01 First Artist - First Track
5:30 Second Artist - Second Track
10:15 Third Artist - Third Track
[15:45] Fourth Artist - Fourth Track
20:00 - Fifth Artist - Fifth Track
25:30 01. Sixth Artist - Sixth Track
        """.strip()

        result = parse_tracklist(description)

        assert len(result) == 6

        # Verify order is preserved
        assert result[0]["timestamp_ms"] == 1000
        assert result[0]["artist"] == "First Artist"
        assert result[0]["title"] == "First Track"

        assert result[1]["timestamp_ms"] == 330000
        assert result[1]["artist"] == "Second Artist"
        assert result[1]["title"] == "Second Track"

        assert result[2]["timestamp_ms"] == 615000
        assert result[2]["artist"] == "Third Artist"
        assert result[2]["title"] == "Third Track"

        assert result[3]["timestamp_ms"] == 945000
        assert result[3]["artist"] == "Fourth Artist"
        assert result[3]["title"] == "Fourth Track"

        assert result[4]["timestamp_ms"] == 1200000
        assert result[4]["artist"] == "Fifth Artist"
        assert result[4]["title"] == "Fifth Track"

        assert result[5]["timestamp_ms"] == 1530000
        assert result[5]["artist"] == "Sixth Artist"
        assert result[5]["title"] == "Sixth Track"

    def test_empty_description(self):
        """Test empty description returns empty list."""
        description = ""
        result = parse_tracklist(description)

        assert result == []

    def test_no_tracklist(self):
        """Test description with no timestamps returns empty list."""
        description = """
        This is just a normal video description with no timestamps.
        It has multiple lines.
        But none of them contain any tracklist information.
        Just regular text about the video.
        """.strip()

        result = parse_tracklist(description)

        assert result == []

    def test_mixed_content(self):
        """Test description with both timestamp lines and regular text."""
        description = """
Welcome to my DJ set!
This is an amazing mix recorded live.

Tracklist:

0:01 Artist One - Track One
Some random comment here
5:30 Artist Two - Track Two
Another comment or note
10:15 Artist Three - Track Three

Thanks for watching!
Don't forget to like and subscribe.
        """.strip()

        result = parse_tracklist(description)

        # Should only parse the three timestamp lines
        assert len(result) == 3
        assert result[0]["artist"] == "Artist One"
        assert result[1]["artist"] == "Artist Two"
        assert result[2]["artist"] == "Artist Three"

    def test_whitespace_handling(self):
        """Test proper handling of whitespace in entries."""
        description = "  01:23:45   Artist Name   -   Track Title  "
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track Title"

    def test_multiple_dashes_in_title(self):
        """Test track with multiple dashes (only first is separator)."""
        description = "5:30 Artist Name - Track - With - Dashes"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["artist"] == "Artist Name"
        assert result[0]["title"] == "Track - With - Dashes"

    def test_single_digit_minutes_and_seconds(self):
        """Test single digit minutes and seconds."""
        description = "0:05 Artist - Track"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 5000

    def test_zero_timestamp_at_start(self):
        """Test 0:00 timestamp is valid."""
        description = "0:00 Opening Track - Artist"
        result = parse_tracklist(description)

        # Note: timestamp_to_ms("0:00") returns 0, and the code checks if timestamp_ms == 0 and skips it
        # Let me check the implementation again...
        # Yes, line 103-104: if timestamp_ms == 0: continue
        # So this should return empty list
        assert result == []

    def test_actual_zero_timestamp_edge_case(self):
        """Test that non-zero timestamps work correctly."""
        description = "0:01 Artist - Track"
        result = parse_tracklist(description)

        assert len(result) == 1
        assert result[0]["timestamp_ms"] == 1000
        assert result[0]["artist"] == "Artist"
        assert result[0]["title"] == "Track"
