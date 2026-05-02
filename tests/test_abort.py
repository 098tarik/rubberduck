"""Tests for the abort module."""

import asyncio

import pytest

import app.abort as abort_module


@pytest.fixture(autouse=True)
def clear_abort_events():
    """Ensure the global abort-event registry is empty before and after each test."""
    abort_module._abort_events.clear()
    yield
    abort_module._abort_events.clear()


def test_create_abort_controller_returns_event():
    event = abort_module.create_abort_controller("req-1")
    assert isinstance(event, asyncio.Event)


def test_create_abort_controller_registers_event():
    abort_module.create_abort_controller("req-2")
    assert "req-2" in abort_module._abort_events


def test_create_abort_controller_not_set_initially():
    event = abort_module.create_abort_controller("req-3")
    assert not event.is_set()


def test_request_abort_returns_true_for_registered():
    abort_module.create_abort_controller("req-4")
    result = abort_module.request_abort("req-4")
    assert result is True


def test_request_abort_sets_event():
    event = abort_module.create_abort_controller("req-5")
    abort_module.request_abort("req-5")
    assert event.is_set()


def test_request_abort_returns_false_for_unknown():
    result = abort_module.request_abort("no-such-request")
    assert result is False


def test_request_abort_runs_registered_async_callback():
    event = abort_module.create_abort_controller("req-async")
    callbacks: list[str] = []

    async def _cleanup():
        callbacks.append("called")

    event.add_callback(_cleanup)

    result = abort_module.request_abort("req-async")

    assert result is True
    assert callbacks == ["called"]


def test_cleanup_abort_controller_removes_entry():
    abort_module.create_abort_controller("req-6")
    abort_module.cleanup_abort_controller("req-6")
    assert "req-6" not in abort_module._abort_events


def test_cleanup_abort_controller_safe_for_unknown():
    # Must not raise
    abort_module.cleanup_abort_controller("never-registered")


def test_multiple_controllers_are_independent():
    e1 = abort_module.create_abort_controller("r1")
    e2 = abort_module.create_abort_controller("r2")
    abort_module.request_abort("r1")
    assert e1.is_set()
    assert not e2.is_set()
