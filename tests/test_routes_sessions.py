"""Tests for the sessions API route."""

from unittest.mock import patch

import fastapi
import httpx
import pytest
from httpx import ASGITransport

from app.routes import sessions as sessions_module
from app import history

# Minimal FastAPI app with only the sessions router
_test_app = fastapi.FastAPI()
_test_app.include_router(sessions_module.router, prefix="/api")


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_test_app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/sessions
# ---------------------------------------------------------------------------

async def test_get_sessions_empty(client):
    with (
        patch("app.routes.sessions.history.list_sessions", return_value=[]),
        patch("app.routes.sessions.telemetry.record"),
    ):
        response = await client.get("/api/sessions")

    assert response.status_code == 200
    assert response.json() == {"sessions": []}


async def test_get_sessions_returns_list(client):
    fake_sessions = [
        {"id": "s1", "preview": "Hello there", "updated_at": "2024-01-01T00:00:00+00:00"},
        {"id": "s2", "preview": "Another chat", "updated_at": "2024-01-02T00:00:00+00:00"},
    ]
    with (
        patch("app.routes.sessions.history.list_sessions", return_value=fake_sessions),
        patch("app.routes.sessions.telemetry.record"),
    ):
        response = await client.get("/api/sessions")

    assert response.status_code == 200
    body = response.json()
    assert len(body["sessions"]) == 2
    assert body["sessions"][0]["id"] == "s1"


async def test_get_sessions_records_telemetry(client):
    with (
        patch("app.routes.sessions.history.list_sessions", return_value=[]),
        patch("app.routes.sessions.telemetry.record") as mock_record,
    ):
        await client.get("/api/sessions")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "sessions_listed" in events


# ---------------------------------------------------------------------------
# GET /api/sessions/{session_id}
# ---------------------------------------------------------------------------

async def test_get_session_returns_messages(client):
    fake_messages = [
        {"role": "user", "content": "hi", "id": "1", "timestamp": "t"},
        {"role": "assistant", "content": "hello", "id": "2", "timestamp": "t"},
    ]
    with (
        patch("app.routes.sessions.history.load_session", return_value=fake_messages),
        patch("app.routes.sessions.telemetry.record"),
    ):
        response = await client.get("/api/sessions/sess-abc")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "sess-abc"
    assert len(body["messages"]) == 2


async def test_get_session_404_when_not_found(client):
    with (
        patch("app.routes.sessions.history.load_session", return_value=[]),
        patch("app.routes.sessions.telemetry.record"),
    ):
        response = await client.get("/api/sessions/no-such-session")

    assert response.status_code == 404


async def test_get_session_records_telemetry(client):
    fake_messages = [{"role": "user", "content": "hi", "id": "1", "timestamp": "t"}]
    with (
        patch("app.routes.sessions.history.load_session", return_value=fake_messages),
        patch("app.routes.sessions.telemetry.record") as mock_record,
    ):
        await client.get("/api/sessions/my-session")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "session_viewed" in events


async def test_get_session_404_does_not_record_session_viewed(client):
    with (
        patch("app.routes.sessions.history.load_session", return_value=[]),
        patch("app.routes.sessions.telemetry.record") as mock_record,
    ):
        await client.get("/api/sessions/no-such-session")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "session_viewed" not in events
