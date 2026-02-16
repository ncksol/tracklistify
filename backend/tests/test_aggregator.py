"""Tests for the result aggregator service."""

import pytest

from app.services.aggregator import (
    SegmentResult,
    AggregatedTrack,
    UnidentifiedGap,
    aggregate_results,
)


class TestMergeConsecutiveMatches:
    """Test merging of consecutive segments identifying the same track."""

    def test_merge_five_consecutive_segments(self):
        """5 segments all identifying "Track A" should produce 1 AggregatedTrack."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album="Album A",
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Track A",
                artist="Artist A",
                album="Album A",
                confidence=0.92,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track A",
                artist="Artist A",
                album="Album A",
                confidence=0.88,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title="Track A",
                artist="Artist A",
                album="Album A",
                confidence=0.90,
            ),
            SegmentResult(
                segment_index=4,
                start_ms=40000,
                end_ms=50000,
                title="Track A",
                artist="Artist A",
                album="Album A",
                confidence=0.85,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 1
        assert len(gaps) == 0

        track = tracks[0]
        assert track.position == 1
        assert track.start_ms == 0
        assert track.end_ms == 50000
        assert track.title == "Track A"
        assert track.artist == "Artist A"
        assert track.album == "Album A"
        # Average confidence: (0.95 + 0.92 + 0.88 + 0.90 + 0.85) / 5 = 0.90
        assert abs(track.avg_confidence - 0.90) < 0.01


class TestMultipleTracks:
    """Test handling of multiple distinct tracks."""

    def test_two_tracks_in_sequence(self):
        """Segments identifying Track A then Track B should produce 2 AggregatedTracks."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="First Song",
                artist="Artist One",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="First Song",
                artist="Artist One",
                album=None,
                confidence=0.93,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Second Song",
                artist="Artist Two",
                album=None,
                confidence=0.91,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title="Second Song",
                artist="Artist Two",
                album=None,
                confidence=0.89,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2
        assert len(gaps) == 0

        # First track
        assert tracks[0].position == 1
        assert tracks[0].start_ms == 0
        assert tracks[0].end_ms == 20000
        assert tracks[0].title == "First Song"
        assert tracks[0].artist == "Artist One"

        # Second track
        assert tracks[1].position == 2
        assert tracks[1].start_ms == 20000
        assert tracks[1].end_ms == 40000
        assert tracks[1].title == "Second Song"
        assert tracks[1].artist == "Artist Two"


class TestTransitionDetection:
    """Test detection of transitions between tracks."""

    def test_close_track_transition_marked(self):
        """Tracks with < 2s gap should be marked as transitions."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="First Song",
                artist="Artist One",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="First Song",
                artist="Artist One",
                album=None,
                confidence=0.93,
            ),
            # Very short gap (1 second)
            SegmentResult(
                segment_index=2,
                start_ms=21000,
                end_ms=31000,
                title="Second Song",
                artist="Artist Two",
                album=None,
                confidence=0.91,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=31000,
                end_ms=41000,
                title="Second Song",
                artist="Artist Two",
                album=None,
                confidence=0.89,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2

        # Both tracks should be marked as transitions due to close proximity
        assert tracks[0].is_transition is True
        assert tracks[1].is_transition is True

    def test_wide_gap_no_transition(self):
        """Tracks with > 5s gap should NOT be marked as transitions."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="First Song",
                artist="Artist One",
                album=None,
                confidence=0.95,
            ),
            # Large gap (6 seconds)
            SegmentResult(
                segment_index=1,
                start_ms=16000,
                end_ms=26000,
                title="Second Song",
                artist="Artist Two",
                album=None,
                confidence=0.91,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2
        # No transition marking for wide gaps
        assert tracks[0].is_transition is False
        assert tracks[1].is_transition is False


class TestConfidenceThresholding:
    """Test confidence threshold filtering."""

    def test_low_confidence_treated_as_unmatched(self):
        """Segments with confidence below threshold should be treated as unmatched."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Track Low",
                artist="Artist Low",
                album=None,
                confidence=0.55,  # Below 60% threshold
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track Low",
                artist="Artist Low",
                album=None,
                confidence=0.58,  # Below 60% threshold
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title="Track Low",
                artist="Artist Low",
                album=None,
                confidence=0.59,  # Below 60% threshold
            ),
            SegmentResult(
                segment_index=4,
                start_ms=40000,
                end_ms=50000,
                title="Track B",
                artist="Artist B",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments, confidence_threshold=0.60)

        # Should have 2 tracks (A and B) and 1 gap (the 3 low-confidence segments)
        assert len(tracks) == 2
        assert tracks[0].title == "Track A"
        assert tracks[1].title == "Track B"

        # 3 consecutive low-confidence segments should create a gap
        assert len(gaps) == 1
        assert gaps[0].start_ms == 10000
        assert gaps[0].end_ms == 40000

    def test_none_confidence_treated_as_unmatched(self):
        """Segments with None confidence should be treated as unmatched."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=None,  # None confidence
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=None,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 0
        assert len(gaps) == 1
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 30000


class TestGapHandling:
    """Test gap handling logic."""

    def test_three_consecutive_unmatched_creates_gap(self):
        """3+ consecutive None/unmatched segments should produce an UnidentifiedGap."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=4,
                start_ms=40000,
                end_ms=50000,
                title="Track B",
                artist="Artist B",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2
        assert len(gaps) == 1

        gap = gaps[0]
        assert gap.start_ms == 10000
        assert gap.end_ms == 40000

    def test_short_gap_not_created(self):
        """1-2 unmatched segments between tracks should NOT create an UnidentifiedGap."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track B",
                artist="Artist B",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2
        assert len(gaps) == 0  # No gap created for single unmatched segment

    def test_two_unmatched_no_gap(self):
        """2 unmatched segments should NOT create a gap."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title="Track B",
                artist="Artist B",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 2
        assert len(gaps) == 0  # No gap created for only 2 unmatched segments


class TestFuzzyDeduplication:
    """Test fuzzy matching for track deduplication."""

    def test_fuzzy_match_with_minor_variation(self):
        """Similar track names with minor variations should merge (>0.85 similarity)."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Wonderful Song Title",
                artist="Amazing Artist",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="wonderful song title",  # Same but lowercase
                artist="amazing artist",  # Same but lowercase
                album=None,
                confidence=0.92,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        # Should merge into 1 track due to fuzzy matching (exact match when normalized)
        assert len(tracks) == 1
        assert tracks[0].start_ms == 0
        assert tracks[0].end_ms == 20000

    def test_remix_suffix_creates_separate_track(self):
        """Track with remix suffix falls below 0.85 threshold and creates separate track."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Artist Name - Track",
                artist="Artist Name",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Artist Name - Track (Remix)",
                artist="Artist Name",
                album=None,
                confidence=0.92,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        # Remix suffix brings similarity to ~0.826, below 0.85 threshold
        # Should create 2 separate tracks
        assert len(tracks) == 2
        assert tracks[0].title == "Artist Name - Track"
        assert tracks[1].title == "Artist Name - Track (Remix)"

    def test_fuzzy_match_case_insensitive(self):
        """Case variations should be treated as same track."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="TRACK NAME",
                artist="ARTIST NAME",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="track name",
                artist="artist name",
                album=None,
                confidence=0.92,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track Name",
                artist="Artist Name",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        # All should merge into 1 track
        assert len(tracks) == 1
        assert tracks[0].start_ms == 0
        assert tracks[0].end_ms == 30000

    def test_different_tracks_not_merged(self):
        """Truly different tracks should not be merged."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Completely Different Track",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Another Track Entirely",
                artist="Artist A",
                album=None,
                confidence=0.92,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        # Should create 2 separate tracks
        assert len(tracks) == 2


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_input(self):
        """Empty list should return empty lists."""
        tracks, gaps = aggregate_results([])

        assert len(tracks) == 0
        assert len(gaps) == 0

    def test_all_unidentified(self):
        """All segments with no match should return one big UnidentifiedGap."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
            SegmentResult(
                segment_index=3,
                start_ms=30000,
                end_ms=40000,
                title=None,
                artist=None,
                album=None,
                confidence=None,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 0
        assert len(gaps) == 1

        gap = gaps[0]
        assert gap.start_ms == 0
        assert gap.end_ms == 40000

    def test_single_valid_segment(self):
        """Single valid segment should create one track."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 1
        assert len(gaps) == 0
        assert tracks[0].avg_confidence == 0.95

    def test_missing_artist_treated_as_unmatched(self):
        """Segments with title but no artist should be treated as unmatched."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title="Track A",
                artist=None,  # Missing artist
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title="Track A",
                artist=None,
                album=None,
                confidence=0.92,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title="Track A",
                artist=None,
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 0
        assert len(gaps) == 1
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 30000

    def test_missing_title_treated_as_unmatched(self):
        """Segments with artist but no title should be treated as unmatched."""
        segments = [
            SegmentResult(
                segment_index=0,
                start_ms=0,
                end_ms=10000,
                title=None,  # Missing title
                artist="Artist A",
                album=None,
                confidence=0.95,
            ),
            SegmentResult(
                segment_index=1,
                start_ms=10000,
                end_ms=20000,
                title=None,
                artist="Artist A",
                album=None,
                confidence=0.92,
            ),
            SegmentResult(
                segment_index=2,
                start_ms=20000,
                end_ms=30000,
                title=None,
                artist="Artist A",
                album=None,
                confidence=0.90,
            ),
        ]

        tracks, gaps = aggregate_results(segments)

        assert len(tracks) == 0
        assert len(gaps) == 1
        assert gaps[0].start_ms == 0
        assert gaps[0].end_ms == 30000
