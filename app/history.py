"""Session history persistence helpers."""

import datetime
import json
import pathlib
from typing import Any, TypeAlias

from rubberduck.app import config


SessionMessages: TypeAlias = list[dict[str, Any]]

MAX_HISTORY_ITEMS = 100


def session_path(session_id: str) -> pathlib.Path:
    """Return the on-disk path for a session transcript."""
    return config.SESSIONS_DIR / f"{session_id}.json"


def load_session(session_id: str) -> SessionMessages:
    """Load a persisted session transcript if it exists."""
    path = session_path(session_id)
    if not path.exists():
        return []

    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session_id: str, messages: SessionMessages) -> None:
    """Persist a session transcript with a bounded history length."""
    path = session_path(session_id)
    serialized = json.dumps(messages[-MAX_HISTORY_ITEMS:], indent=2)
    path.write_text(serialized, encoding="utf-8")


def list_sessions() -> list[dict[str, str]]:
    """Return lightweight metadata for all persisted sessions."""
    sessions = []
    session_files = sorted(
        config.SESSIONS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    for session_file in session_files:
        raw_messages = json.loads(session_file.read_text(encoding="utf-8"))
        first_user_message = next(
            (
                message
                for message in raw_messages
                if message.get("role") == "user"
            ),
            None,
        )
        preview = "(empty)"
        if first_user_message:
            preview = str(first_user_message.get("content", ""))[:80]

        updated_at = datetime.datetime.fromtimestamp(
            session_file.stat().st_mtime,
            tz=datetime.timezone.utc,
        ).isoformat()
        sessions.append(
            {
                "id": session_file.stem,
                "preview": preview,
                "updated_at": updated_at,
            }
        )

    return sessions
