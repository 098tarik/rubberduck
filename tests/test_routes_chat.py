"""Tests for the chat API route."""

import json
from unittest.mock import patch

import fastapi
import httpx
import pytest
from httpx import ASGITransport

from app.routes.chat import _is_cloud_model
from app.routes import chat as chat_module
from app import query_engine

# Minimal FastAPI app with only the chat router (avoids static file mount)
_test_app = fastapi.FastAPI()
_test_app.include_router(chat_module.router, prefix="/api")


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_test_app), base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# _is_cloud_model helper
# ---------------------------------------------------------------------------

def test_is_cloud_model_true():
    assert _is_cloud_model("gpt-4:cloud") is True


def test_is_cloud_model_true_any_prefix():
    assert _is_cloud_model("deepseek-r1:cloud") is True


def test_is_cloud_model_false_for_local():
    assert _is_cloud_model("llama3") is False


def test_is_cloud_model_false_for_model_with_tag():
    assert _is_cloud_model("llama3:8b") is False


# ---------------------------------------------------------------------------
# Route: POST /api/chat
# ---------------------------------------------------------------------------

async def test_chat_rejects_cloud_model(client):
    response = await client.post(
        "/api/chat", json={"message": "hello", "model": "gpt-4:cloud"}
    )
    assert response.status_code == 400
    assert "cloud" in response.json()["detail"].lower()


async def test_chat_returns_streaming_response(client):
    async def _mock_query(self, user_content):
        yield 'data: {"text": "hi"}\n\n'
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "llama3"}
        ) as response:
            assert response.status_code == 200
            chunks = [chunk async for chunk in response.aiter_text()]

    content = "".join(chunks)
    assert "hi" in content
    assert "[DONE]" in content


async def test_chat_includes_session_id_header(client):
    async def _mock_query(self, user_content):
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "llama3"}
        ) as response:
            session_id = response.headers.get("X-Session-Id")
            async for _ in response.aiter_bytes():
                pass

    assert session_id is not None
    assert len(session_id) > 0


async def test_chat_uses_provided_session_id(client):
    async def _mock_query(self, user_content):
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST",
            "/api/chat",
            json={"message": "hello", "session_id": "my-session-id", "model": "llama3"},
        ) as response:
            returned_session_id = response.headers.get("X-Session-Id")
            async for _ in response.aiter_bytes():
                pass

    assert returned_session_id == "my-session-id"


async def test_chat_generates_new_session_id_when_omitted(client):
    async def _mock_query(self, user_content):
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "llama3"}
        ) as response:
            session_id = response.headers.get("X-Session-Id")
            async for _ in response.aiter_bytes():
                pass

    assert session_id is not None


async def test_chat_cache_control_header(client):
    async def _mock_query(self, user_content):
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "llama3"}
        ) as response:
            cache_control = response.headers.get("Cache-Control")
            async for _ in response.aiter_bytes():
                pass

    assert cache_control == "no-cache"


async def test_chat_records_telemetry_on_start(client):
    async def _mock_query(self, user_content):
        yield "data: [DONE]\n\n"

    with (
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record") as mock_record,
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "llama3"}
        ) as response:
            async for _ in response.aiter_bytes():
                pass

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "chat_started" in events


async def test_chat_records_telemetry_error_for_cloud_model(client):
    with patch("app.routes.chat.telemetry.record") as mock_record:
        await client.post(
            "/api/chat", json={"message": "hello", "model": "gpt-4:cloud"}
        )

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "chat_error" in events


async def test_chat_requires_message_field(client):
    response = await client.post("/api/chat", json={"model": "llama3"})
    assert response.status_code == 422
