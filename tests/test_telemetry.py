"""Tests for the telemetry module."""

import json
import logging
import pathlib

import pytest

import app.config as config
from app import telemetry


@pytest.fixture(autouse=True)
def patch_telemetry_log(tmp_path, monkeypatch):
    """Redirect TELEMETRY_LOG to a temp file for isolation."""
    log_file = tmp_path / "telemetry.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)


def test_record_creates_file(tmp_path, monkeypatch):
    log_file = tmp_path / "tel.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)
    telemetry.record("test_event")
    assert log_file.exists()


def test_record_writes_valid_json(tmp_path, monkeypatch):
    log_file = tmp_path / "tel.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)
    telemetry.record("my_event")
    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert entry["event"] == "my_event"


def test_record_includes_timestamp(tmp_path, monkeypatch):
    log_file = tmp_path / "tel.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)
    telemetry.record("ts_event")
    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert "timestamp" in entry


def test_record_includes_extra_kwargs(tmp_path, monkeypatch):
    log_file = tmp_path / "tel.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)
    telemetry.record("chat_started", session_id="s123", model="llama3")
    entry = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert entry["session_id"] == "s123"
    assert entry["model"] == "llama3"


def test_record_appends_multiple_entries(tmp_path, monkeypatch):
    log_file = tmp_path / "tel.jsonl"
    monkeypatch.setattr(config, "TELEMETRY_LOG", log_file)
    telemetry.record("event_one")
    telemetry.record("event_two")
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "event_one"
    assert json.loads(lines[1])["event"] == "event_two"


def test_record_handles_oserror_without_raising(tmp_path, monkeypatch, caplog):
    """An OSError must be swallowed and logged as a warning."""
    monkeypatch.setattr(config, "TELEMETRY_LOG", pathlib.Path("/no/such/dir/file.jsonl"))
    with caplog.at_level(logging.WARNING, logger="rubberduck.telemetry"):
        telemetry.record("bad_event")
    assert any("bad_event" in m for m in caplog.messages)
