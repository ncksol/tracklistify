"""Tests for standalone local CLI behavior."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import NAMESPACE_URL, uuid5

import pytest

from app.cli import build_parser, main, run_identify
from app.services.aggregator import AggregatedTrack, SegmentResult, UnidentifiedGap
from app.standalone_export import render_identify_result, write_identify_output


@pytest.fixture
def sample_identify_result():
    return {
        "tracks": [
            {
                "position": 1,
                "start_ms": 0,
                "end_ms": 6000,
                "title": "Intro Track",
                "artist": "DJ Example",
                "album": None,
                "avg_confidence": 0.91,
                "is_transition": False,
            }
        ],
        "gaps": [{"start_ms": 6000, "end_ms": 12000}],
        "metadata": {
            "url": "https://www.youtube.com/watch?v=abc123xyz01",
            "title": "Example Set",
            "duration": "00:30:00",
            "description": "Example description",
            "confidence_threshold": 0.5,
            "segment_count": 2,
            "matched_segment_count": 1,
        },
    }


def test_build_parser_parses_identify_defaults():
    parser = build_parser()

    args = parser.parse_args(["identify", "https://www.youtube.com/watch?v=abc123xyz01"])

    assert args.command == "identify"
    assert args.url == "https://www.youtube.com/watch?v=abc123xyz01"
    assert args.cookie_file is None
    assert args.confidence_threshold == pytest.approx(0.5)
    assert args.format == "text"
    assert args.output is None


def test_build_parser_rejects_invalid_url(capsys: pytest.CaptureFixture[str]):
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["identify", "not-a-url"])

    assert exc_info.value.code == 2
    assert "URL must be an absolute http(s) URL." in capsys.readouterr().err


def test_build_parser_rejects_non_youtube_url(capsys: pytest.CaptureFixture[str]):
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["identify", "https://example.com/set"])

    assert exc_info.value.code == 2
    assert "URL must be a valid YouTube watch/share URL." in capsys.readouterr().err


def test_build_parser_rejects_mobile_youtube_url(capsys: pytest.CaptureFixture[str]):
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["identify", "https://m.youtube.com/watch?v=abc123xyz01"])

    assert exc_info.value.code == 2
    assert "URL must be a valid YouTube watch/share URL." in capsys.readouterr().err


def test_build_parser_rejects_missing_cookie_file(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
):
    parser = build_parser()
    missing_cookie = tmp_path / "missing-cookies.txt"

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(
            [
                "identify",
                "https://www.youtube.com/watch?v=abc123xyz01",
                "--cookie-file",
                str(missing_cookie),
            ]
        )

    assert exc_info.value.code == 2
    assert f"File not found: {missing_cookie}" in capsys.readouterr().err


def test_render_identify_result_text_output_orders_tracks_and_gaps():
    result = {
        "tracks": [
            {
                "position": 2,
                "start_ms": 12000,
                "end_ms": 18000,
                "title": "Second Track",
                "artist": "Artist B",
                "album": None,
                "avg_confidence": 0.92,
                "is_transition": False,
            },
            {
                "position": 1,
                "start_ms": 0,
                "end_ms": 6000,
                "title": None,
                "artist": None,
                "album": None,
                "avg_confidence": 0.75,
                "is_transition": False,
            },
        ],
        "gaps": [{"start_ms": 6000, "end_ms": 12000}],
        "metadata": {
            "url": "https://www.youtube.com/watch?v=abc123xyz01",
            "title": "",
            "duration": "",
            "description": "",
            "confidence_threshold": 0.5,
            "segment_count": 3,
            "matched_segment_count": 2,
        },
    }

    rendered = render_identify_result(result=result, output_format="text")

    assert rendered.splitlines() == [
        "01. [00:00:00] Unknown Artist - Unknown Title",
        "-- [00:00:06 - 00:00:12] Unidentified",
        "02. [00:00:12] Artist B - Second Track",
    ]


def test_write_identify_output_writes_json_file(
    sample_identify_result: dict[str, object],
    tmp_path: Path,
):
    output_path = tmp_path / "identify-output.json"

    write_identify_output(
        result=sample_identify_result,
        output_format="json",
        output_path=output_path,
    )

    output_text = output_path.read_text(encoding="utf-8")
    assert output_text.endswith("\n")
    assert json.loads(output_text) == {
        "job_id": str(uuid5(NAMESPACE_URL, "https://www.youtube.com/watch?v=abc123xyz01")),
        "title": "Example Set",
        "url": "https://www.youtube.com/watch?v=abc123xyz01",
        "duration_seconds": 1800,
        "tracks": [
            {
                "position": 1,
                "start_time_ms": 0,
                "end_time_ms": 6000,
                "artist": "DJ Example",
                "title": "Intro Track",
                "confidence_score": 0.91,
            }
        ],
    }


def test_run_identify_orchestrates_services_with_mocks(tmp_path: Path):
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("cookie-content", encoding="utf-8")
    youtube_url = "https://www.youtube.com/watch?v=abc123xyz01"
    segments = [
        {"path": str(tmp_path / "segment_0000.wav"), "start_ms": 0, "end_ms": 6000},
        {"path": str(tmp_path / "segment_0001.wav"), "start_ms": 6000, "end_ms": 12000},
        {"path": str(tmp_path / "segment_0002.wav"), "start_ms": 12000, "end_ms": 18000},
    ]
    fingerprint_results = [
        SegmentResult(
            segment_index=0,
            start_ms=0,
            end_ms=6000,
            title="Track A",
            artist="Artist A",
            album=None,
            confidence=0.95,
        ),
        SegmentResult(
            segment_index=1,
            start_ms=6000,
            end_ms=12000,
            title="Partial Match",
            artist=None,
            album=None,
            confidence=0.99,
        ),
        SegmentResult(
            segment_index=2,
            start_ms=12000,
            end_ms=18000,
            title="Track B",
            artist="Artist B",
            album=None,
            confidence=0.88,
        ),
    ]
    aggregated_tracks = [
        AggregatedTrack(
            position=1,
            start_ms=0,
            end_ms=6000,
            title="Track A",
            artist="Artist A",
            album=None,
            avg_confidence=0.95,
            is_transition=False,
        ),
        AggregatedTrack(
            position=2,
            start_ms=12000,
            end_ms=18000,
            title="Track B",
            artist="Artist B",
            album=None,
            avg_confidence=0.88,
            is_transition=False,
        ),
    ]
    unidentified_gaps = [UnidentifiedGap(start_ms=6000, end_ms=12000)]

    with (
        patch("app.cli.validate_url", new_callable=AsyncMock) as mock_validate,
        patch("app.cli.download_audio", new_callable=AsyncMock) as mock_download,
        patch("app.cli.segment_audio") as mock_segment_audio,
        patch("app.cli._batch_fingerprint_segments", new_callable=AsyncMock) as mock_batch,
        patch("app.cli.aggregate_results") as mock_aggregate,
        patch("app.cli._emit_progress") as mock_progress,
    ):
        mock_validate.return_value = {
            "title": "Example Set",
            "duration": "00:30:00",
            "description": "Mocked set metadata",
        }
        mock_segment_audio.return_value = segments
        mock_batch.return_value = fingerprint_results
        mock_aggregate.return_value = (aggregated_tracks, unidentified_gaps)

        result = run_identify(
            url=youtube_url,
            cookie_file=cookie_file,
            confidence_threshold=0.7,
        )

    mock_validate.assert_awaited_once_with(youtube_url, cookie_path=str(cookie_file))
    mock_download.assert_awaited_once()
    assert mock_download.await_args.args[0] == youtube_url
    assert Path(mock_download.await_args.args[1]).name == "audio.wav"
    assert mock_download.await_args.kwargs["cookie_path"] == str(cookie_file)

    mock_segment_audio.assert_called_once()
    assert Path(mock_segment_audio.call_args.kwargs["input_path"]).name == "audio.wav"
    assert Path(mock_segment_audio.call_args.kwargs["output_dir"]).name == "segments"
    assert mock_segment_audio.call_args.kwargs["window_seconds"] == 12
    assert mock_segment_audio.call_args.kwargs["hop_seconds"] == 6

    mock_batch.assert_awaited_once()
    assert mock_batch.await_args.args[0] == segments
    assert mock_batch.await_args.kwargs["max_concurrent"] == 3
    assert mock_batch.await_args.kwargs["throttle_seconds"] == 0.3
    assert mock_batch.await_args.kwargs["confidence_threshold"] == 0.7
    assert callable(mock_batch.await_args.kwargs["on_progress"])

    mock_aggregate.assert_called_once_with(fingerprint_results, confidence_threshold=0.7)
    progress_phases = [progress_call.args[0] for progress_call in mock_progress.call_args_list]
    assert "COMPLETE" in progress_phases

    assert result["tracks"] == [
        {
            "position": 1,
            "start_ms": 0,
            "end_ms": 6000,
            "title": "Track A",
            "artist": "Artist A",
            "album": None,
            "avg_confidence": 0.95,
            "is_transition": False,
        },
        {
            "position": 2,
            "start_ms": 12000,
            "end_ms": 18000,
            "title": "Track B",
            "artist": "Artist B",
            "album": None,
            "avg_confidence": 0.88,
            "is_transition": False,
        },
    ]
    assert result["gaps"] == [{"start_ms": 6000, "end_ms": 12000}]
    assert result["metadata"] == {
        "url": "https://www.youtube.com/watch?v=abc123xyz01",
        "title": "Example Set",
        "duration": "00:30:00",
        "description": "Mocked set metadata",
        "confidence_threshold": 0.7,
        "segment_count": 3,
        "matched_segment_count": 2,
    }


def test_main_identify_calls_orchestrator_and_renderer(
    sample_identify_result: dict[str, object],
    tmp_path: Path,
):
    output_path = tmp_path / "cli-output.json"

    with (
        patch("app.cli.load_dotenv") as mock_load_dotenv,
        patch("app.cli.run_identify", return_value=sample_identify_result) as mock_run,
        patch("app.cli._render_identify_result") as mock_render,
    ):
        exit_code = main(
            [
                "identify",
                "https://www.youtube.com/watch?v=abc123xyz01",
                "--confidence-threshold",
                "0.75",
                "--format",
                "json",
                "--output",
                str(output_path),
            ]
        )

    assert exit_code == 0
    mock_load_dotenv.assert_called_once_with()
    mock_run.assert_called_once_with(
        url="https://www.youtube.com/watch?v=abc123xyz01",
        cookie_file=None,
        confidence_threshold=0.75,
    )
    mock_render.assert_called_once_with(
        result=sample_identify_result,
        output_format="json",
        output_path=output_path,
    )


def test_main_exits_with_status_one_on_not_implemented(
    capsys: pytest.CaptureFixture[str],
):
    with (
        patch("app.cli.run_identify", side_effect=NotImplementedError("local mode unavailable")),
        pytest.raises(SystemExit) as exc_info,
    ):
        main(["identify", "https://www.youtube.com/watch?v=abc123xyz01"])

    assert exc_info.value.code == 1
    assert "local mode unavailable" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("invalid url"), "Error: invalid url"),
        (RuntimeError("pipeline failed"), "Error: pipeline failed"),
        (FileNotFoundError("ffmpeg not found"), "Error: ffmpeg not found"),
    ],
)
def test_main_exits_with_status_one_on_runtime_errors(
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    expected: str,
):
    with (
        patch("app.cli.run_identify", side_effect=error),
        pytest.raises(SystemExit) as exc_info,
    ):
        main(["identify", "https://www.youtube.com/watch?v=abc123xyz01"])

    assert exc_info.value.code == 1
    assert expected in capsys.readouterr().err
