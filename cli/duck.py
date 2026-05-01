"""RubberDuck CLI — a barebones terminal chat client for Ollama."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid
from datetime import datetime, timezone

import httpx

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
# Ollama streaming
# ---------------------------------------------------------------------------


def stream_chat(
    messages: list[dict],
    model: str,
) -> str:
    """Stream a chat response from Ollama and print it; return full text."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in messages],
        ],
        "stream": True,
    }

    full_text = ""
    try:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST", f"{OLLAMA_URL}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
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
                        print(text, end="", flush=True)
                        full_text += text
    except httpx.HTTPError as exc:
        print(f"\n[error] {exc}", file=sys.stderr)

    print()  # trailing newline
    return full_text


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------

HELP_TEXT = """\
Commands:
  /new          start a new session
  /model <name> switch model (current: {model})
  /history      show message history for this session
  /quit         exit
"""


def run_repl(initial_prompt: str | None = None) -> None:
    """Run an interactive chat REPL."""
    session_id = str(uuid.uuid4())
    model = DEFAULT_MODEL
    history: list[dict] = []

    print(f"🦆 RubberDuck CLI  (model: {model}  session: {session_id[:8]})")
    print('Type /quit to exit, /new for a new session, or /help for commands.\n')

    def _handle(prompt: str) -> None:
        nonlocal session_id, model, history

        stripped = prompt.strip()
        if not stripped:
            return

        if stripped == "/quit":
            raise SystemExit(0)

        if stripped == "/new":
            session_id = str(uuid.uuid4())
            history = []
            print(f"[new session: {session_id[:8]}]\n")
            return

        if stripped == "/help":
            print(HELP_TEXT.format(model=model))
            return

        if stripped == "/history":
            if not history:
                print("[no messages yet]\n")
            for msg in history:
                role = msg["role"].upper()
                print(f"[{role}] {msg['content']}\n")
            return

        if stripped.startswith("/model "):
            model = stripped[len("/model "):].strip()
            print(f"[model switched to: {model}]\n")
            return

        # Regular message
        history.append(
            {
                "role": "user",
                "content": stripped,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        print(f"\n🦆  ", end="", flush=True)
        reply = stream_chat(history, model)
        print()

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
            prompt = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        _handle(prompt)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point — accepts an optional inline prompt."""
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run_repl(initial_prompt=prompt)


if __name__ == "__main__":
    main()
