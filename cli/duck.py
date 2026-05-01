"""RubberDuck CLI — a barebones terminal chat client for Ollama."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid
from datetime import datetime, timezone

import httpx
from rich import box
from rich.columns import Columns
from rich.console import Console
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


def _duck_panel(content: str, title: str = "🦆 RubberDuck") -> Panel:
    """Wrap text in a duck-themed panel with Markdown rendering."""
    return Panel(
        Markdown(content) if content.strip() else Text(""),
        title=title,
        border_style="yellow",
        box=box.ROUNDED,
        padding=(0, 1),
    )


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


def _print_help(model: str) -> None:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="yellow bold")
    table.add_column(style="dim")
    rows = [
        ("/new", "start a new session"),
        (f"/model <name>", f"switch model [yellow](current: {model})[/yellow]"),
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
    console.print("[bold yellow]❯[/bold yellow] ", end="")
    return input()


# ---------------------------------------------------------------------------
# Ollama streaming
# ---------------------------------------------------------------------------


def stream_chat(messages: list[dict], model: str) -> str:
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
    spinner = Spinner("dots", text=Text(" thinking…", style="yellow dim"))

    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST", f"{OLLAMA_URL}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                with Live(
                    spinner,
                    console=console,
                    refresh_per_second=12,
                    transient=True,
                ) as live:
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
                            live.update(_duck_panel(full_text))

    except httpx.HTTPError as exc:
        console.print(
            Panel(
                f"[red]{exc}[/red]",
                title="[red]Error[/red]",
                border_style="red",
                box=box.ROUNDED,
            )
        )

    console.print()
    return full_text


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


def run_repl(initial_prompt: str | None = None) -> None:
    """Run an interactive chat REPL."""
    session_id = str(uuid.uuid4())
    model = DEFAULT_MODEL
    history: list[dict] = []

    _print_welcome(model, session_id)

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

        if stripped.startswith("/model "):
            model = stripped[len("/model "):].strip()
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

        reply = stream_chat(history, model)

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
