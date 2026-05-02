"""Tests for the terminal CLI helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


CLI_PATH = Path(__file__).resolve().parents[1] / "cli" / "duck.py"
SPEC = importlib.util.spec_from_file_location("rubberduck_cli_duck", CLI_PATH)
assert SPEC is not None and SPEC.loader is not None
duck = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(duck)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_fetch_available_models_returns_unique_names(monkeypatch) -> None:
    monkeypatch.setattr(
        duck.httpx,
        "get",
        lambda *args, **kwargs: _FakeResponse(
            {
                "models": [
                    {"name": "deepseek-r1:8b"},
                    {"name": "llama3"},
                    {"name": "deepseek-r1:8b"},
                    {"name": ""},
                ]
            }
        ),
    )

    assert duck.fetch_available_models() == ["deepseek-r1:8b", "llama3"]


def test_command_trie_returns_matching_commands() -> None:
    trie = duck.CommandTrie(["/new", "/model", "/history", "/help", "/quit"])

    assert trie.search("/h") == ["/help", "/history"]
    assert trie.search("/model") == ["/model"]
    assert trie.search("/missing") == []


def test_accept_top_completion_uses_first_result_when_none_selected() -> None:
    applied = []
    cancelled = []

    class FakeCompletionState:
        completions = ["/model", "/models"]
        current_completion = None

    class FakeBuffer:
        complete_state = FakeCompletionState()

        def apply_completion(self, completion) -> None:
            applied.append(completion)

        def cancel_completion(self) -> None:
            cancelled.append(True)

    assert duck._accept_top_completion(FakeBuffer()) is True
    assert applied == ["/model"]
    assert cancelled == [True]


def test_model_picker_text_marks_cursor_and_current_model() -> None:
    fragments = duck._model_picker_text(
        ["deepseek-r1:8b", "qwen2.5:0.5b"],
        current_model="deepseek-r1:8b",
        cursor_index=1,
    )

    rendered = "".join(text for _, text in fragments)
    assert "deepseek-r1:8b [current]" in rendered
    assert "› qwen2.5:0.5b" in rendered


def test_spinner_status_message_is_phase_aware() -> None:
    assert duck._spinner_status_message("waiting") == "Waiting for first token..."


def test_local_models_from_payload_filters_and_sorts() -> None:
    payload = {
        "models": [
            {"name": "phi3:mini", "size": 200},
            {"name": "gpt-4:cloud", "size": 1},
            {"name": "qwen2.5:0.5b", "size": 100},
        ]
    }

    assert duck._local_models_from_payload(payload) == [
        {"name": "qwen2.5:0.5b", "size": 100},
        {"name": "phi3:mini", "size": 200},
    ]


def test_fallback_error_notice_surfaces_exact_error() -> None:
    message = duck._fallback_error_notice(
        "phi3:mini",
        "qwen2.5:0.5b",
        "model requires more system memory (3.5 GiB) than is available (3.1 GiB)",
    )

    assert "phi3:mini failed:" in message
    assert "model requires more system memory" in message
    assert "Using qwen2.5:0.5b for this response." in message


def test_stream_panel_placeholder_uses_dim_text_not_markup() -> None:
    group = duck._stream_panel("", is_loading=False)
    panel = group.renderables[0]

    assert isinstance(panel.renderable, duck.Text)
    assert panel.renderable.plain == "Waiting for model response..."


def test_run_repl_model_command_uses_selector(monkeypatch) -> None:
    printed: list[str] = []

    monkeypatch.setattr(duck, "fetch_available_models", lambda: ["llama3", "mistral"])
    monkeypatch.setattr(
        duck,
        "prompt_model_selection",
        lambda models, current_model: "mistral",
    )
    monkeypatch.setattr(duck.console, "print", lambda *args, **kwargs: printed.append(str(args[0])))

    duck.run_repl(initial_prompt="/model")

    assert any("Switched to model: mistral" in item for item in printed)


def test_run_repl_skips_empty_assistant_reply(monkeypatch) -> None:
    saved_histories: list[list[dict]] = []

    monkeypatch.setattr(duck, "stream_chat", lambda history, model: "")
    monkeypatch.setattr(duck, "save_session", lambda session_id, history: saved_histories.append(list(history)))
    monkeypatch.setattr(duck.console, "print", lambda *args, **kwargs: None)
    monkeypatch.setattr(duck.console, "clear", lambda: None)

    duck.run_repl(initial_prompt="hello")

    assert saved_histories
    assert len(saved_histories[-1]) == 1
    assert saved_histories[-1][0]["role"] == "user"