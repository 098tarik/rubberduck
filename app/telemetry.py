"""Lightweight telemetry for tracking feature usage.

Events are appended as newline-delimited JSON (JSONL) to the file specified
by the ``TELEMETRY_LOG`` config value (default: ``./telemetry.jsonl``).

Each record contains at minimum:
    - ``timestamp``  ISO 8601 UTC string
    - ``event``      snake_case event name

Additional keyword arguments are merged into the record as extra fields.

The log file can be queried with any JSON-aware tool, e.g.::

    # Count events by type
    jq -r '.event' telemetry.jsonl | sort | uniq -c | sort -rn

    # Show all chat_completed events with their model and session
    jq 'select(.event == "chat_completed")' telemetry.jsonl
"""

import datetime
import json
import logging

from app import config


_logger = logging.getLogger("rubberduck.telemetry")


def record(event: str, **kwargs: object) -> None:
    """Append a telemetry event to the JSONL log file.

    Args:
        event: Snake-case name describing the event (e.g. ``chat_started``).
        **kwargs: Arbitrary extra fields merged into the log record.
    """
    entry: dict[str, object] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": event,
        **kwargs,
    }
    try:
        with config.TELEMETRY_LOG.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        _logger.warning("Failed to write telemetry event '%s': %s", event, exc)
