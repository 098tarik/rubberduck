"""Tests for the QueryEngine class."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.abort import AbortController
import app.config as config
from app.query_engine import QueryEngine


@pytest.fixture(autouse=True)
def patch_sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)


def test_parse_stream_line_invalid_json():
    full, stop, frame = QueryEngine._parse_stream_line("data: not-json", "acc")
    assert full == "acc"
    assert stop is False
    assert frame is None


def test_parse_stream_line_ignores_non_data_lines():
    full, stop, frame = QueryEngine._parse_stream_line("event: ping", "acc")
    assert full == "acc"
    assert stop is False
    assert frame is None


def test_parse_stream_line_done_true():
    full, stop, frame = QueryEngine._parse_stream_line("data: [DONE]", "acc")
    assert full == "acc"
    assert stop is True
    assert frame == "data: [DONE]\n\n"


def test_parse_stream_line_with_text():
    line = json.dumps({"choices": [{"delta": {"content": " world"}}]})
    full, stop, frame = QueryEngine._parse_stream_line(f"data: {line}", "hello")
    assert full == "hello world"
    assert stop is False
    assert frame is not None
    payload = json.loads(frame.removeprefix("data: ").removesuffix("\n\n"))
    assert payload["text"] == " world"


def test_status_frame_contains_phase_and_label():
    frame = QueryEngine._status_frame("waiting")
    payload = json.loads(frame.removeprefix("data: ").removesuffix("\n\n"))
    assert payload == {
        "status": {
            "phase": "waiting",
            "label": "Waiting for first token...",
        }
    }


def test_build_messages_starts_with_system():
    engine = QueryEngine("test-session")
    result = engine._build_ollama_messages("You are helpful.")
    assert result[0] == {"role": "system", "content": "You are helpful."}


def test_append_persists_to_disk(tmp_path):
    engine = QueryEngine("sess-persist")
    engine.append({"role": "user", "content": "stored", "id": "x", "timestamp": "t"})
    path = tmp_path / "sess-persist.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["content"] == "stored"


def _make_mock_stream(lines):
    """Return a mocked httpx.AsyncClient for streaming."""

    async def _aiter_lines():
        for line in lines:
            yield line

    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = _aiter_lines
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    return mock_client


async def test_query_yields_text_frames():
    lines = [
        f'data: {json.dumps({"choices": [{"delta": {"content": "Hello"}}]})}',
        "data: [DONE]",
    ]
    mock_client = _make_mock_stream(lines)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q1")
        frames = [f async for f in engine.query("hi")]

    text_frames = [f for f in frames if '"text":' in f]
    status_frames = [f for f in frames if '"status":' in f]
    done_frames = [f for f in frames if "[DONE]" in f]
    assert len(text_frames) == 1
    assert [
        json.loads(frame.removeprefix("data: ").removesuffix("\n\n"))["status"]["phase"]
        for frame in status_frames
    ] == ["preparing", "connecting", "waiting", "responding"]
    payload = json.loads(text_frames[0].removeprefix("data: ").removesuffix("\n\n"))
    assert payload["text"] == "Hello"
    assert len(done_frames) == 1


async def test_query_yields_error_frame_on_http_error():
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q3")
        frames = [f async for f in engine.query("hello")]

    payload = json.loads(frames[-1].removeprefix("data: ").removesuffix("\n\n"))
    assert "error" in payload


async def test_query_abort_closes_active_stream():
    lines = [f'data: {json.dumps({"choices": [{"delta": {"content": "ignored"}}]})}']
    mock_client = _make_mock_stream(lines)
    mock_client.stream.return_value.is_error = False
    mock_client.stream.return_value.aclose = AsyncMock(return_value=None)
    abort_event = AbortController()
    abort_event.abort()

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q6")
        frames = [f async for f in engine.query("hello", abort_event)]

    await asyncio.sleep(0)
    done_frames = [f for f in frames if "[DONE]" in f]
    assert len(done_frames) == 1
    mock_client.stream.return_value.aclose.assert_awaited_once()
