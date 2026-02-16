"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def temp_audio_path(tmp_path):
    """Fixture providing a temporary audio file path."""
    audio_file = tmp_path / "test_audio.mp3"
    return str(audio_file)


@pytest.fixture
def temp_output_dir(tmp_path):
    """Fixture providing a temporary output directory path."""
    output_dir = tmp_path / "segments"
    return str(output_dir)
