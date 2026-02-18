"""Tests for audio segmentation service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.audio import get_audio_duration, segment_audio


class TestGetAudioDuration:
    """Tests for get_audio_duration function."""

    def test_returns_correct_duration(self, temp_audio_path):
        """Test that get_audio_duration returns correct duration from ffprobe."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "60.5\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            duration = get_audio_duration(temp_audio_path)

            # Verify correct ffprobe command was called
            mock_run.assert_called_once_with(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    temp_audio_path,
                ],
                capture_output=True,
                text=True,
            )

            # Verify correct duration returned
            assert duration == 60.5

    def test_raises_on_ffprobe_failure(self, temp_audio_path):
        """Test that get_audio_duration raises RuntimeError when ffprobe fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: No such file"

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="ffprobe failed with return code 1"),
        ):
            get_audio_duration(temp_audio_path)

    def test_raises_on_invalid_duration_output(self, temp_audio_path):
        """Test that get_audio_duration raises RuntimeError on invalid output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not_a_number\n"

        with (
            patch("subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="Invalid duration output from ffprobe"),
        ):
            get_audio_duration(temp_audio_path)


class TestSegmentAudio:
    """Tests for segment_audio function."""

    def test_produces_correct_number_of_segments(self, temp_audio_path, temp_output_dir):
        """Test segment_audio produces correct number of segments for known duration."""
        # Mock get_audio_duration to return 30 seconds
        # With 12s window and 6s hop, we should get: 0, 6, 12, 18, 24 = 5 segments
        with patch("app.services.audio.get_audio_duration", return_value=30.0) as mock_duration:
            # Mock ffmpeg subprocess
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                # Verify get_audio_duration was called
                mock_duration.assert_called_once_with(temp_audio_path)

                # Verify correct number of segments
                assert len(segments) == 5

                # Verify ffmpeg was called 5 times
                assert mock_run.call_count == 5

    def test_twelve_second_window_six_second_hop_sixty_seconds(
        self, temp_audio_path, temp_output_dir
    ):
        """Test segment_audio with 12s window and 6s hop on 60-second audio."""
        with patch("app.services.audio.get_audio_duration", return_value=60.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                # Verify correct number of segments
                assert len(segments) == 10

    def test_very_short_audio_produces_one_segment(self, temp_audio_path, temp_output_dir):
        """Test segment_audio with very short audio (< window_seconds) produces 1 segment."""
        with patch("app.services.audio.get_audio_duration", return_value=5.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                # Should produce exactly 1 segment
                assert len(segments) == 1

                # Verify the segment covers the full duration
                assert segments[0]["start_ms"] == 0
                assert segments[0]["end_ms"] == 5000

    def test_creates_output_directory(self, temp_audio_path, tmp_path):
        """Test segment_audio creates output directory if it doesn't exist."""
        output_dir = str(tmp_path / "nonexistent" / "nested" / "dir")

        with patch("app.services.audio.get_audio_duration", return_value=12.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segment_audio(temp_audio_path, output_dir)

                # Verify directory was created
                assert Path(output_dir).exists()
                assert Path(output_dir).is_dir()

    def test_segment_start_and_end_timestamps(self, temp_audio_path, temp_output_dir):
        """Test segment_audio returns correct start_ms and end_ms values."""
        with patch("app.services.audio.get_audio_duration", return_value=30.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                # Verify timestamps for each segment
                assert segments[0]["start_ms"] == 0
                assert segments[0]["end_ms"] == 12000
                assert segments[1]["start_ms"] == 6000
                assert segments[1]["end_ms"] == 18000
                assert segments[2]["start_ms"] == 12000
                assert segments[2]["end_ms"] == 24000
                assert segments[3]["start_ms"] == 18000
                assert segments[3]["end_ms"] == 30000
                assert segments[4]["start_ms"] == 24000
                assert segments[4]["end_ms"] == 30000

    def test_segment_paths_are_absolute(self, temp_audio_path, temp_output_dir):
        """Test that segment paths are absolute paths."""
        with patch("app.services.audio.get_audio_duration", return_value=12.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(temp_audio_path, temp_output_dir)

                assert Path(segments[0]["path"]).is_absolute()
                assert segments[0]["path"].endswith("segment_000.wav")

    def test_segment_filenames_are_zero_padded(self, temp_audio_path, temp_output_dir):
        """Test that segment filenames are zero-padded correctly."""
        with patch("app.services.audio.get_audio_duration", return_value=60.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                assert segments[0]["path"].endswith("segment_000.wav")
                assert segments[1]["path"].endswith("segment_001.wav")
                assert segments[9]["path"].endswith("segment_009.wav")

    def test_ffmpeg_called_with_correct_parameters(self, temp_audio_path, temp_output_dir):
        """Test that ffmpeg is called with correct parameters for audio conversion."""
        with patch("app.services.audio.get_audio_duration", return_value=12.0):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result) as mock_run:
                segment_audio(temp_audio_path, temp_output_dir)

                # Get the call arguments
                call_args = mock_run.call_args[0][0]

                # Verify ffmpeg parameters
                assert call_args[0] == "ffmpeg"
                assert "-i" in call_args
                assert temp_audio_path in call_args
                assert "-acodec" in call_args
                assert "pcm_s16le" in call_args
                assert "-ar" in call_args
                assert "16000" in call_args
                assert "-ac" in call_args
                assert "1" in call_args
                assert "-y" in call_args

    def test_raises_on_ffmpeg_failure(self, temp_audio_path, temp_output_dir):
        """Test that segment_audio raises RuntimeError when ffmpeg fails."""
        with patch("app.services.audio.get_audio_duration", return_value=12.0):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Error: Invalid codec"

            with (
                patch("subprocess.run", return_value=mock_result),
                pytest.raises(RuntimeError, match="ffmpeg failed for segment 0"),
            ):
                segment_audio(temp_audio_path, temp_output_dir)

    def test_skips_very_short_final_segment(self, temp_audio_path, temp_output_dir):
        """Test that segments shorter than 1 second at the end are skipped."""
        with patch("app.services.audio.get_audio_duration", return_value=60.5):
            mock_result = MagicMock()
            mock_result.returncode = 0

            with patch("subprocess.run", return_value=mock_result):
                segments = segment_audio(
                    temp_audio_path, temp_output_dir, window_seconds=12, hop_seconds=6
                )

                assert len(segments) == 10
                assert segments[-1]["end_ms"] <= 60500
                duration_ms = segments[-1]["end_ms"] - segments[-1]["start_ms"]
                assert duration_ms >= 1000
