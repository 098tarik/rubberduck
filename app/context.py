"""Helpers for building the system prompt sent to the model."""

import datetime
import pathlib


_BASE_SYSTEM_PROMPT = (
    "You are RubberDuck, a helpful and friendly AI assistant. "
    "Keep responses concise and helpful."
)
_MEMORY_FILE = pathlib.Path("./RUBBERDUCK.md")
_TIME_FORMAT = "%Y-%m-%d %H:%M"


def build_system_context() -> str:
    """Build the per-request system prompt for the chat model."""
    prompt_parts = [
        _BASE_SYSTEM_PROMPT,
        (
            "Current date/time (UTC): "
            f"{datetime.datetime.now(datetime.timezone.utc).strftime(_TIME_FORMAT)}"
        ),
    ]

    if _MEMORY_FILE.exists():
        memory_text = _MEMORY_FILE.read_text(encoding="utf-8")
        prompt_parts.append(
            f"\n--- Memory (RUBBERDUCK.md) ---\n{memory_text}"
        )

    return "\n".join(prompt_parts)
