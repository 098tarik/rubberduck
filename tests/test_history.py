"""Tests for the history module."""

import json
import pathlib

import pytest

import app.config as config
from app import history


@pytest.fixture(autouse=True)
def patch_sessions_dir(tmp_path, monkeypatch):
    """Redirect SESSIONS_DIR to a temporary directory for isolation."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)


def test_session_path_returns_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path)
    path = history.session_path("abc123")
    assert path == tmp_path / "abc123.json"


def test_load_session_returns_empty_for_missing_file():
    result = history.load_session("nonexistent-session")
    assert result == []


def test_load_session_returns_messages_when_file_exists(tmp_path):
    messages = [{"role": "user", "content": "hello"}]
    (tmp_path / "my-session.json").write_text(json.dumps(messages), encoding="utf-8")
    result = history.load_session("my-session")
    assert result == messages


def test_save_session_writes_json_file(tmp_path):
    messages = [{"role": "user", "content": "hi"}]
    history.save_session("test-session", messages)
    path = tmp_path / "test-session.json"
    assert path.exists()
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == messages


def test_save_session_truncates_to_max_history(tmp_path):
    messages = [{"role": "user", "content": str(i)} for i in range(150)]
    history.save_session("big-session", messages)
    stored = json.loads((tmp_path / "big-session.json").read_text(encoding="utf-8"))
    assert len(stored) == history.MAX_HISTORY_ITEMS
    # Should keep the last MAX_HISTORY_ITEMS messages
    assert stored[0]["content"] == str(150 - history.MAX_HISTORY_ITEMS)


def test_save_session_keeps_all_messages_under_limit(tmp_path):
    messages = [{"role": "user", "content": str(i)} for i in range(10)]
    history.save_session("small-session", messages)
    stored = json.loads((tmp_path / "small-session.json").read_text(encoding="utf-8"))
    assert len(stored) == 10


def test_list_sessions_empty_when_no_files():
    result = history.list_sessions()
    assert result == []


def test_list_sessions_returns_metadata(tmp_path):
    messages = [{"role": "user", "content": "What is Python?"}]
    (tmp_path / "sess-1.json").write_text(json.dumps(messages), encoding="utf-8")

    result = history.list_sessions()
    assert len(result) == 1
    assert result[0]["id"] == "sess-1"
    assert result[0]["preview"] == "What is Python?"
    assert "updated_at" in result[0]


def test_list_sessions_preview_is_empty_when_no_user_message(tmp_path):
    messages = [{"role": "assistant", "content": "I am the assistant."}]
    (tmp_path / "sess-asst.json").write_text(json.dumps(messages), encoding="utf-8")

    result = history.list_sessions()
    assert result[0]["preview"] == "(empty)"


def test_list_sessions_preview_truncated_at_80_chars(tmp_path):
    long_content = "A" * 200
    messages = [{"role": "user", "content": long_content}]
    (tmp_path / "sess-long.json").write_text(json.dumps(messages), encoding="utf-8")

    result = history.list_sessions()
    assert len(result[0]["preview"]) == 80


def test_list_sessions_sorted_by_mtime_newest_first(tmp_path):
    import time

    (tmp_path / "older.json").write_text(json.dumps([{"role": "user", "content": "old"}]), encoding="utf-8")
    time.sleep(0.05)
    (tmp_path / "newer.json").write_text(json.dumps([{"role": "user", "content": "new"}]), encoding="utf-8")

    result = history.list_sessions()
    ids = [s["id"] for s in result]
    assert ids.index("newer") < ids.index("older")


def test_load_and_save_roundtrip(tmp_path):
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    history.save_session("roundtrip", messages)
    loaded = history.load_session("roundtrip")
    assert loaded == messages
