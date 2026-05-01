"""Tests for the context module."""

import pathlib

import pytest

import app.context as context_module


@pytest.fixture(autouse=True)
def reset_memory_file(monkeypatch, tmp_path):
    """Point _MEMORY_FILE to a path that does not exist by default."""
    monkeypatch.setattr(context_module, "_MEMORY_FILE", tmp_path / "RUBBERDUCK.md")


def test_build_system_context_contains_base_prompt():
    result = context_module.build_system_context()
    assert "RubberDuck" in result


def test_build_system_context_contains_datetime():
    result = context_module.build_system_context()
    assert "Current date/time (UTC):" in result


def test_build_system_context_no_memory_section_when_file_absent():
    result = context_module.build_system_context()
    assert "Memory" not in result
    assert "RUBBERDUCK.md" not in result


def test_build_system_context_includes_memory_when_file_present(tmp_path, monkeypatch):
    memory_file = tmp_path / "RUBBERDUCK.md"
    memory_file.write_text("Remember: always be concise.", encoding="utf-8")
    monkeypatch.setattr(context_module, "_MEMORY_FILE", memory_file)

    result = context_module.build_system_context()
    assert "Memory" in result
    assert "Remember: always be concise." in result


def test_build_system_context_is_string():
    result = context_module.build_system_context()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_system_context_newline_separated_parts():
    result = context_module.build_system_context()
    parts = result.split("\n")
    assert len(parts) >= 2
