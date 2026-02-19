"""Tests for Tracklistify CLI identify workflow."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from app.cli import _format_timestamp, _print_tracklist, _submit_job, run_cli


def test_format_timestamp_minutes_and_hours() -> None:
    """Timestamp formatting handles minute and hour ranges."""
    assert _format_timestamp(90_000) == "01:30"
    assert _format_timestamp(3_723_000) == "1:02:03"


@pytest.mark.asyncio
async def test_submit_job_uses_json_without_cookie() -> None:
    """Job submission uses JSON payload when cookie file is not provided."""
    session = MagicMock(spec=aiohttp.ClientSession)

    with patch("app.cli._request_json", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"id": "job-123"}
        response = await _submit_job(
            session=session,
            api_url="http://localhost:8000",
            youtube_url="https://youtu.be/test",
            force=False,
            confidence_threshold=0.5,
            cookie_file=None,
        )

    assert response["id"] == "job-123"
    assert "json" in mock_request.call_args.kwargs
    assert "data" not in mock_request.call_args.kwargs
    assert mock_request.call_args.kwargs["json"] == {
        "url": "https://youtu.be/test",
        "force": False,
        "confidence_threshold": 0.5,
    }


@pytest.mark.asyncio
async def test_submit_job_uses_multipart_with_cookie(tmp_path: Path) -> None:
    """Job submission uses multipart form data when cookie file is provided."""
    cookie_path = tmp_path / "cookies.txt"
    cookie_path.write_bytes(
        b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\tX\tY\n"
    )
    session = MagicMock(spec=aiohttp.ClientSession)

    with patch("app.cli._request_json", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"id": "job-456"}
        await _submit_job(
            session=session,
            api_url="http://localhost:8000",
            youtube_url="https://youtu.be/test",
            force=True,
            confidence_threshold=0.2,
            cookie_file=cookie_path,
        )

    kwargs = mock_request.call_args.kwargs
    assert "data" in kwargs
    assert "json" not in kwargs
    form = kwargs["data"]
    assert isinstance(form, aiohttp.FormData)
    field_names = [field[0]["name"] for field in form._fields]
    assert set(field_names) == {"url", "force", "confidence_threshold", "cookie_file"}


@pytest.mark.asyncio
async def test_submit_job_fails_for_missing_cookie_file(tmp_path: Path) -> None:
    """Missing cookie files are rejected before making API calls."""
    missing_cookie = tmp_path / "missing.txt"
    session = MagicMock(spec=aiohttp.ClientSession)

    with pytest.raises(RuntimeError, match="Cookie file does not exist"):
        await _submit_job(
            session=session,
            api_url="http://localhost:8000",
            youtube_url="https://youtu.be/test",
            force=False,
            confidence_threshold=0.5,
            cookie_file=missing_cookie,
        )


def test_print_tracklist_renders_tracks_and_gaps(capsys: pytest.CaptureFixture[str]) -> None:
    """Tracklist output includes identified tracks and unidentified segments."""
    _print_tracklist(
        {
            "tracks": [
                {
                    "position": 1,
                    "start_time_ms": 12_000,
                    "title": "Track One",
                    "artist": "Artist A",
                    "confidence_score": 0.79,
                }
            ],
            "unidentified_segments": [
                {
                    "start_time_ms": 24_000,
                    "end_time_ms": 48_000,
                }
            ],
        },
        json_output=False,
    )

    output = capsys.readouterr().out
    assert "Tracklist:" in output
    assert "Artist A — Track One (79%)" in output
    assert "Unidentified segments:" in output
    assert "00:24 - 00:48" in output


@pytest.mark.asyncio
async def test_run_cli_identify_no_wait(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI identify command returns early when --no-wait is set."""
    with patch("app.cli._submit_job", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = {"id": "job-789"}
        exit_code = await run_cli(
            [
                "identify",
                "https://youtu.be/test",
                "--api-url",
                "http://localhost:8000",
                "--no-wait",
            ]
        )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Submitted job: job-789" in output
