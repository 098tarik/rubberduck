"""Abort-controller helpers for in-flight requests."""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any


AbortCallback = Callable[[], Awaitable[None] | None]


class AbortController(asyncio.Event):
    """An abort event that can also tear down live upstream work."""

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: list[AbortCallback] = []

    def add_callback(self, callback: AbortCallback) -> None:
        """Register cleanup that should run when the request is aborted."""
        self._callbacks.append(callback)
        if self.is_set():
            self._invoke(callback)

    def abort(self) -> None:
        """Mark the request aborted and run registered cleanup callbacks."""
        if self.is_set():
            return

        self.set()
        for callback in list(self._callbacks):
            self._invoke(callback)

    @staticmethod
    def _invoke(callback: AbortCallback) -> None:
        result = callback()
        if not inspect.isawaitable(result):
            return

        try:
            asyncio.get_running_loop().create_task(result)
        except RuntimeError:
            asyncio.run(result)


_abort_events: dict[str, AbortController] = {}


def create_abort_controller(request_id: str) -> AbortController:
    """Create and register an abort controller for one request."""
    event = AbortController()
    _abort_events[request_id] = event
    return event


def request_abort(request_id: str) -> bool:
    """Signal cancellation for a request if it is still registered."""
    event = _abort_events.get(request_id)
    if event:
        event.abort()
        return True
    return False


def cleanup_abort_controller(request_id: str) -> None:
    """Remove a request's abort event from the registry."""
    _abort_events.pop(request_id, None)
