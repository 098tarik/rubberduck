"""Tests for the QueryEngine class."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.config as config
from app.query_engine import QueryEngine


@pytest.fixture(autouse=True)
def patch_sessions_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# _parse_stream_line (static method – no engine instance needed)
# ---------------------------------------------------------------------------

def test_parse_stream_line_invalid_json():
    full, stop, frame = QueryEngine._parse_stream_line("not-json", "acc")
    assert full == "acc"
    assert stop is False
    assert frame is None


def test_parse_stream_line_done_true():
    line = json.dumps({"done": True})
    full, stop, frame = QueryEngine._parse_stream_line(line, "acc")
    assert full == "acc"
    assert stop is True
    assert frame == "data: [DONE]\n\n"


def test_parse_stream_line_with_text():
    line = json.dumps({"message": {"content": " world"}, "done": False})
    full, stop, frame = QueryEngine._parse_stream_line(line, "hello")
    assert full == "hello world"
    assert stop is False
    assert frame is not None
    payload = json.loads(frame.removeprefix("data: ").removesuffix("\n\n"))
    assert payload["text"] == " world"


def test_parse_stream_line_empty_content():
    line = json.dumps({"message": {"content": ""}, "done": False})
    full, stop, frame = QueryEngine._parse_stream_line(line, "acc")
    assert full == "acc"
    assert stop is False
    assert frame is None


def test_parse_stream_line_missing_message_key():
    line = json.dumps({"done": False})
    full, stop, frame = QueryEngine._parse_stream_line(line, "acc")
    assert full == "acc"
    assert stop is False
    assert frame is None


# ---------------------------------------------------------------------------
# _build_ollama_messages
# ---------------------------------------------------------------------------

def test_build_ollama_messages_starts_with_system(tmp_path):
    engine = QueryEngine("test-session")
    result = engine._build_ollama_messages("You are helpful.")
    assert result[0] == {"role": "system", "content": "You are helpful."}


def test_build_ollama_messages_includes_history(tmp_path):
    engine = QueryEngine("test-session")
    engine._messages = [
        {"role": "user", "content": "hi", "id": "1", "timestamp": "now"},
        {"role": "assistant", "content": "hello", "id": "2", "timestamp": "now"},
    ]
    result = engine._build_ollama_messages("sys")
    assert len(result) == 3  # system + 2 messages
    assert result[1] == {"role": "user", "content": "hi"}
    assert result[2] == {"role": "assistant", "content": "hello"}


# ---------------------------------------------------------------------------
# append / get_history
# ---------------------------------------------------------------------------

def test_append_adds_to_history():
    engine = QueryEngine("sess-append")
    msg = {"role": "user", "content": "test", "id": "x", "timestamp": "t"}
    engine.append(msg)
    assert msg in engine._messages


def test_append_persists_to_disk(tmp_path):
    engine = QueryEngine("sess-persist")
    engine.append({"role": "user", "content": "stored", "id": "x", "timestamp": "t"})
    path = tmp_path / "sess-persist.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["content"] == "stored"


def test_get_history_returns_copy():
    engine = QueryEngine("sess-hist")
    engine._messages = [{"role": "user", "content": "a", "id": "1", "timestamp": "t"}]
    hist = engine.get_history()
    hist.append({"extra": "item"})
    # Original must be unchanged
    assert len(engine._messages) == 1


# ---------------------------------------------------------------------------
# query – streaming happy path
# ---------------------------------------------------------------------------

def _make_mock_stream(lines):
    """Return a mocked httpx.AsyncClient for streaming."""

    async def _aiter_lines():
        for line in lines:
            yield line

    mock_response = MagicMock()
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
        json.dumps({"message": {"content": "Hello"}, "done": False}),
        json.dumps({"done": True}),
    ]
    mock_client = _make_mock_stream(lines)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q1")
        frames = [f async for f in engine.query("hi")]

    text_frames = [f for f in frames if "[DONE]" not in f]
    done_frames = [f for f in frames if "[DONE]" in f]
    assert len(text_frames) == 1
    payload = json.loads(text_frames[0].removeprefix("data: ").removesuffix("\n\n"))
    assert payload["text"] == "Hello"
    assert len(done_frames) == 1


async def test_query_appends_assistant_message_after_stream():
    lines = [
        json.dumps({"message": {"content": "Hi there"}, "done": False}),
        json.dumps({"done": True}),
    ]
    mock_client = _make_mock_stream(lines)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q2")
        async for _ in engine.query("hello"):
            pass

    # Last message should be the assistant message
    last = engine._messages[-1]
    assert last["role"] == "assistant"
    assert last["content"] == "Hi there"


async def test_query_yields_error_frame_on_http_error():
    import httpx

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q3")
        frames = [f async for f in engine.query("hello")]

    assert len(frames) == 1
    payload = json.loads(frames[0].removeprefix("data: ").removesuffix("\n\n"))
    assert "error" in payload


async def test_query_user_message_prepended_to_history():
    lines = [json.dumps({"done": True})]
    mock_client = _make_mock_stream(lines)

    with patch("app.query_engine.httpx.AsyncClient", return_value=mock_client):
        engine = QueryEngine("sess-q4")
        async for _ in engine.query("my question"):
            pass

    # First message should be the user message
    assert engine._messages[0]["role"] == "user"
    assert engine._messages[0]["content"] == "my question"
