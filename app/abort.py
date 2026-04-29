"""Abort-controller helpers for in-flight requests."""

import asyncio

_abort_events: dict[str, asyncio.Event] = {}


def create_abort_controller(request_id: str) -> asyncio.Event:
    """Create and register an abort event for one request."""
    event = asyncio.Event()
    _abort_events[request_id] = event
    return event


def request_abort(request_id: str) -> bool:
    """Signal cancellation for a request if it is still registered."""
    event = _abort_events.get(request_id)
    if event:
        event.set()
        return True
    return False


def cleanup_abort_controller(request_id: str) -> None:
    """Remove a request's abort event from the registry."""
    _abort_events.pop(request_id, None)
