"""RubberDuck CLI — a barebones terminal chat client for Ollama."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Configuration (mirrors app/config.py, no shared dependency)
# ---------------------------------------------------------------------------

OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")
SESSIONS_DIR: pathlib.Path = pathlib.Path(
    os.getenv("SESSIONS_DIR", pathlib.Path.home() / ".rubberduck" / "sessions")
)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

MAX_HISTORY = 100

SYSTEM_PROMPT = (
    "You are RubberDuck, a helpful and friendly AI assistant. "
    "Keep responses concise and helpful."
)

console = Console()

COMMANDS = ["/new", "/model", "/history", "/help", "/quit"]

SPINNER_STATUS_LABELS = {
    "preparing": "Preparing context...",
    "connecting": "Contacting Ollama...",
    "waiting": "Waiting for first token...",
    "responding": "Streaming response...",
}

MEMORY_ERROR_FRAGMENT = "model requires more system memory"


class TrieNode:
    def __init__(self) -> None:
        self.children: dict[str, "TrieNode"] = {}
        self.is_terminal = False


class CommandTrie:
    def __init__(self, commands: list[str]) -> None:
        self.root = TrieNode()
        for command in commands:
            self.insert(command)

    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            node = node.children.setdefault(char, TrieNode())
        node.is_terminal = True

    def search(self, prefix: str) -> list[str]:
        node = self.root
        for char in prefix:
            node = node.children.get(char)
            if node is None:
                return []
        matches: list[str] = []
        self._collect(node, prefix, matches)
        return matches

    def _collect(self, node: TrieNode, prefix: str, matches: list[str]) -> None:
        if node.is_terminal:
            matches.append(prefix)
        for char in sorted(node.children):
            self._collect(node.children[char], prefix + char, matches)


COMMAND_TRIE = CommandTrie(COMMANDS)

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _session_path(session_id: str) -> pathlib.Path:
    return SESSIONS_DIR / f"{session_id}.json"


def load_session(session_id: str) -> list[dict]:
    path = _session_path(session_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session_id: str, messages: list[dict]) -> None:
    path = _session_path(session_id)
    path.write_text(
        json.dumps(messages[-MAX_HISTORY:], indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _duck_panel(content: str | Text, title: str = "🦆 RubberDuck") -> Panel:
    """Wrap text in a duck-themed panel with Markdown rendering."""
    if isinstance(content, Text):
        renderable = content if content.plain else Text("")
    else:
        renderable = Markdown(content) if content.strip() else Text("")

    return Panel(
        renderable,
        title=title,
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def _spinner_status_message(phase: str) -> str:
    """Return the status text shown beside the live spinner."""
    return SPINNER_STATUS_LABELS[phase]


def _extract_error_message(response: httpx.Response) -> str:
    """Extract the most useful Ollama error message from a failed response."""
    raw_text = response.text
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text

    return str(payload.get("error") or raw_text)


def _is_memory_pressure_error(error_text: str) -> bool:
    """Return True when Ollama reports the selected model does not fit in RAM."""
    return MEMORY_ERROR_FRAGMENT in error_text.lower()


def _local_models_from_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    """Extract local Ollama models sorted from smallest to largest."""
    local_models: list[dict[str, object]] = []
    for item in payload.get("models", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name or name.endswith(":cloud"):
            continue
        size = item.get("size")
        local_models.append(
            {
                "name": name,
                "size": size if isinstance(size, int) else 0,
            }
        )

    return sorted(local_models, key=lambda item: (item["size"], item["name"]))


def _find_smaller_model(client: httpx.Client, current_model: str) -> str | None:
    """Return the next smaller installed local model, if one exists."""
    response = client.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
    response.raise_for_status()
    models = _local_models_from_payload(response.json())

    current_entry = next((item for item in models if item["name"] == current_model), None)
    if current_entry is not None:
        for item in models:
            if item["name"] != current_model and item["size"] < current_entry["size"]:
                return str(item["name"])

    for item in models:
        if item["name"] != current_model:
            return str(item["name"])

    return None


def _fallback_error_notice(
    requested_model: str,
    fallback_model: str,
    error_text: str,
) -> str:
    """Build the CLI notice shown when a model is downshifted for memory."""
    return (
        f"[yellow dim]  !  {requested_model} failed: {error_text}[/yellow dim]\n"
        f"[yellow dim]  ✓  Using {fallback_model} for this response.[/yellow dim]\n"
    )


def _stream_panel(content: str, is_loading: bool, status_text: str = "") -> Group:
    """Render the assistant panel with an optional loading indicator."""
    panel_content: str | Text
    if content:
        panel_content = content
    else:
        panel_content = Text("Waiting for model response...", style="dim")
    renderables = [_duck_panel(panel_content)]
    if is_loading:
        renderables.append(Spinner("dots", text=Text(status_text, style="yellow dim")))
    return Group(*renderables)


def _print_welcome(model: str, session_id: str) -> None:
    header = Text.assemble(
        ("🦆 RubberDuck", "bold yellow"),
        ("  —  AI assistant powered by Ollama", "dim"),
    )
    subtitle = Text.assemble(
        ("model: ", "dim"),
        (model, "yellow"),
        ("   session: ", "dim"),
        (session_id[:8], "yellow"),
    )
    console.print(
        Panel(
            header,
            subtitle=subtitle,
            border_style="yellow",
            box=box.DOUBLE_EDGE,
            padding=(0, 2),
        )
    )
    console.print(
        "[dim]  /help  for commands · /quit  to exit[/dim]\n"
    )


def _render_session_ui(model: str, session_id: str, history: list[dict]) -> None:
    """Redraw the visible CLI state with the current model and session."""
    console.clear()
    _print_welcome(model, session_id)
    if history:
        _print_history(history)


def _print_help(model: str) -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="yellow bold")
    table.add_column(style="dim")
    rows = [
        ("/new", "start a new session"),
        (
            "/model [name]",
            f"switch model or open selector [yellow](current: {model})[/yellow]",
        ),
        ("/history", "print conversation history"),
        ("/quit", "exit"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)
    console.print(
        Panel(table, title="Commands", border_style="yellow", box=box.ROUNDED)
    )


def _print_history(history: list[dict]) -> None:
    if not history:
        console.print("[dim]  No messages in this session yet.[/dim]\n")
        return
    for msg in history:
        role = msg["role"]
        if role == "user":
            console.print(
                Panel(
                    msg["content"],
                    title="[bold]You[/bold]",
                    border_style="blue",
                    box=box.ROUNDED,
                    padding=(0, 1),
                )
            )
        else:
            console.print(_duck_panel(msg["content"]))


def _prompt_user() -> str:
    """Display a styled prompt and return the user's input."""
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
    except ImportError:
        console.print("[bold yellow]❯[/bold yellow] ", end="")
        return input()

    class TrieCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/"):
                return
            for command in COMMAND_TRIE.search(text):
                yield Completion(command, start_position=-len(text))

    bindings = KeyBindings()

    @bindings.add("enter")
    def _enter(event) -> None:
        if _accept_top_completion(event.current_buffer):
            return
        event.current_buffer.validate_and_handle()

    session = PromptSession(completer=TrieCompleter(), key_bindings=bindings)
    return session.prompt(ANSI("\x1b[1;33m❯ \x1b[0m"), complete_while_typing=True)


def _accept_top_completion(buffer) -> bool:
    """Accept the active completion, or the top completion if none is selected yet."""
    complete_state = getattr(buffer, "complete_state", None)
    if complete_state is None:
        return False

    completions = list(getattr(complete_state, "completions", []))
    if not completions:
        return False

    completion = getattr(complete_state, "current_completion", None) or completions[0]
    buffer.apply_completion(completion)
    cancel_completion = getattr(buffer, "cancel_completion", None)
    if callable(cancel_completion):
        cancel_completion()
    return True


def fetch_available_models() -> list[str]:
    """Return model names exposed by the local Ollama instance."""
    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[red]Error[/red]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        return []

    models = []
    seen = set()
    for item in response.json().get("models", []):
        name = item.get("name", "").strip()
        if name and name not in seen:
            seen.add(name)
            models.append(name)
    return models


def _model_picker_text(
    models: list[str], current_model: str, cursor_index: int
) -> list[tuple[str, str]]:
    """Build formatted text for the interactive model picker."""
    fragments: list[tuple[str, str]] = []
    for index, model_name in enumerate(models):
        pointer = "› " if index == cursor_index else "  "
        current_suffix = " [current]" if model_name == current_model else ""
        style = "class:selected" if index == cursor_index else ""
        fragments.append((style, pointer))
        fragments.append((style, f"{model_name}{current_suffix}"))
        fragments.append(("", "\n"))
    return fragments


def prompt_model_selection(models: list[str], current_model: str) -> str | None:
    """Show an in-terminal selector for available models."""
    if not models:
        console.print("[yellow dim]  No Ollama models found.[/yellow dim]\n")
        return None

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import Box, Frame, Label
    except ImportError:
        console.print(
            "[red]prompt_toolkit is not installed. Reinstall the CLI dependencies.[/red]\n"
        )
        return None

    cursor_index = models.index(current_model) if current_model in models else 0
    style = Style.from_dict(
        {
            "selected": "reverse bold",
        }
    )

    def _move_cursor(step: int) -> None:
        nonlocal cursor_index
        cursor_index = max(0, min(len(models) - 1, cursor_index + step))

    bindings = KeyBindings()

    @bindings.add("up")
    def _move_up(event) -> None:
        _move_cursor(-1)
        event.app.invalidate()

    @bindings.add("down")
    def _move_down(event) -> None:
        _move_cursor(1)
        event.app.invalidate()

    @bindings.add("enter")
    def _select_model(event) -> None:
        event.app.exit(result=models[cursor_index])

    @bindings.add("escape")
    @bindings.add("c-c")
    def _cancel(event) -> None:
        event.app.exit(result=None)

    picker_control = FormattedTextControl(
        lambda: _model_picker_text(models, current_model, cursor_index),
        focusable=True,
    )

    container = Box(
        Frame(
            HSplit(
                [
                    Label(
                        "Use Up and Down to choose a model, then press Enter. Esc cancels."
                    ),
                    Window(height=1, char=" "),
                    Window(content=picker_control, always_hide_cursor=True),
                ]
            ),
            title="RubberDuck Models",
        ),
        padding=1,
    )
    application = Application(
        layout=Layout(container),
        key_bindings=bindings,
        full_screen=False,
        mouse_support=True,
        style=style,
    )

    return application.run()


# ---------------------------------------------------------------------------
# Ollama streaming
# ---------------------------------------------------------------------------


def stream_chat(messages: list[dict], model: str) -> tuple[str, str]:
    """Stream a response from Ollama, rendering it live in a duck panel."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in messages],
        ],
        "stream": True,
    }

    full_text = ""
    started_at = time.monotonic()
    minimum_loading_seconds = 1.0
    active_model = model
    fallback_error_text: str | None = None

    def _update_live_status(
        live_display: Live,
        phase: str,
        content: str,
        *,
        label: str | None = None,
    ) -> None:
        show_content = content if time.monotonic() - started_at >= minimum_loading_seconds else ""
        live_display.update(
            _stream_panel(
                show_content,
                is_loading=True,
                status_text=label or _spinner_status_message(phase),
            )
        )

    try:
        with Live(
            _stream_panel(
                "",
                is_loading=True,
                status_text=_spinner_status_message("preparing"),
            ),
            console=console,
            refresh_per_second=12,
            transient=False,
        ) as live_display:
            with httpx.Client(timeout=120.0) as client:
                tried_fallback = False
                while True:
                    payload["model"] = active_model
                    _update_live_status(live_display, "connecting", full_text)
                    with client.stream(
                        "POST", f"{OLLAMA_URL}/api/chat", json=payload
                    ) as response:
                        if response.is_error:
                            response.read()
                            error_text = _extract_error_message(response)
                            if not tried_fallback and _is_memory_pressure_error(error_text):
                                fallback_model = _find_smaller_model(client, active_model)
                                if fallback_model is not None:
                                    tried_fallback = True
                                    fallback_error_text = error_text
                                    active_model = fallback_model
                                    _update_live_status(
                                        live_display,
                                        "preparing",
                                        full_text,
                                        label=f"Switching to {fallback_model} to fit memory...",
                                    )
                                    continue

                            response.raise_for_status()

                        _update_live_status(live_display, "waiting", full_text)
                        for line in response.iter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if chunk.get("done"):
                                break
                            text = chunk.get("message", {}).get("content", "")
                            if text:
                                full_text += text
                                _update_live_status(live_display, "responding", full_text)
                        break

                remaining_loading = minimum_loading_seconds - (
                    time.monotonic() - started_at
                )
                if remaining_loading > 0:
                    time.sleep(remaining_loading)

                if full_text:
                    live_display.update(_stream_panel(full_text, is_loading=False))

    except httpx.HTTPError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[red]Error[/red]",
                border_style="red",
                box=box.ROUNDED,
            )
        )

    if full_text:
        console.print()
    if active_model != model:
        if fallback_error_text:
            console.print(
                _fallback_error_notice(model, active_model, fallback_error_text)
            )
        else:
            console.print(
                f"[yellow dim]  ✓  Switched to model: {active_model}[/yellow dim]\n"
            )
    return full_text, active_model


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def run_repl(initial_prompt: str | None = None) -> None:
    """Run an interactive chat REPL."""
    session_id = str(uuid.uuid4())
    model = DEFAULT_MODEL
    history: list[dict] = []

    _render_session_ui(model, session_id, history)

    def _handle(user_input: str) -> None:
        nonlocal session_id, model, history

        stripped = user_input.strip()
        if not stripped:
            return

        if stripped == "/quit":
            console.print("\n[yellow dim]Goodbye 🦆[/yellow dim]\n")
            raise SystemExit(0)

        if stripped == "/new":
            session_id = str(uuid.uuid4())
            history = []
            _render_session_ui(model, session_id, history)
            console.print(
                f"[yellow dim]  ↺  New session started: {session_id[:8]}[/yellow dim]\n"
            )
            return

        if stripped == "/help":
            _print_help(model)
            return

        if stripped == "/history":
            _print_history(history)
            return

        if stripped == "/model":
            selected_model = prompt_model_selection(
                fetch_available_models(), current_model=model
            )
            if not selected_model:
                console.print("[dim]  Model unchanged.[/dim]\n")
                return

            model = selected_model
            _render_session_ui(model, session_id, history)
            console.print(
                f"[yellow dim]  ✓  Switched to model: {model}[/yellow dim]\n"
            )
            return

        if stripped.startswith("/model "):
            model = stripped[len("/model "):].strip()
            _render_session_ui(model, session_id, history)
            console.print(
                f"[yellow dim]  ✓  Switched to model: {model}[/yellow dim]\n"
            )
            return

        # Regular message
        history.append(
            {
                "role": "user",
                "content": stripped,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        stream_result = stream_chat(history, model)
        if isinstance(stream_result, tuple):
            reply, model = stream_result
        else:
            reply = stream_result

        if not reply.strip():
            save_session(session_id, history)
            return

        history.append(
            {
                "role": "assistant",
                "content": reply,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_session(session_id, history)

    if initial_prompt:
        _handle(initial_prompt)
        return

    while True:
        try:
            user_input = _prompt_user()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow dim]Goodbye 🦆[/yellow dim]\n")
            break
        _handle(user_input)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point — accepts an optional inline prompt."""
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run_repl(initial_prompt=prompt)


if __name__ == "__main__":
    main()
