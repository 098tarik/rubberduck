"""Tests for the chat API route."""

from unittest.mock import patch

import fastapi
import httpx
import pytest
from httpx import ASGITransport

from app.routes import chat as chat_module
from app import query_engine, runtime

# Minimal FastAPI app with only the chat router (avoids static file mount)
_test_app = fastapi.FastAPI()
_test_app.include_router(chat_module.router, prefix="/api")


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_test_app), base_url="http://test"
    ) as c:
        yield c


def _runtime_model(name: str = "qwen3-4b-q4_k_m.gguf") -> runtime.ModelRecommendation:
    return runtime.ModelRecommendation(
        name=name,
        url="https://example.com/model.gguf",
        n_ctx=4096,
        n_gpu_layers=0,
    )


async def test_chat_returns_streaming_response(client):
    async def _mock_query(self, user_content, abort_event=None):
        yield 'data: {"text": "hi"}\n\n'
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model()),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello"}
        ) as response:
            assert response.status_code == 200
            chunks = [chunk async for chunk in response.aiter_text()]

    content = "".join(chunks)
    assert "hi" in content
    assert "[DONE]" in content


async def test_chat_includes_session_id_header(client):
    async def _mock_query(self, user_content, abort_event=None):
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model()),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream("POST", "/api/chat", json={"message": "hello"}) as response:
            session_id = response.headers.get("X-Session-Id")
            async for _ in response.aiter_bytes():
                pass

    assert session_id is not None
    assert len(session_id) > 0


async def test_chat_uses_provided_session_id(client):
    async def _mock_query(self, user_content, abort_event=None):
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model()),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST",
            "/api/chat",
            json={"message": "hello", "session_id": "my-session-id"},
        ) as response:
            returned_session_id = response.headers.get("X-Session-Id")
            async for _ in response.aiter_bytes():
                pass

    assert returned_session_id == "my-session-id"


async def test_chat_cache_control_header(client):
    async def _mock_query(self, user_content, abort_event=None):
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model()),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream("POST", "/api/chat", json={"message": "hello"}) as response:
            cache_control = response.headers.get("Cache-Control")
            async for _ in response.aiter_bytes():
                pass

    assert cache_control == "no-cache"


async def test_chat_records_runtime_selected_model_on_completion(client):
    async def _mock_query(self, user_content, abort_event=None):
        self.model = "qwen3-4b-q4_k_m.gguf"
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model("qwen3-4b-q4_k_m.gguf")),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record") as mock_record,
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "ignored"}
        ) as response:
            async for _ in response.aiter_bytes():
                pass

    completed_call = next(
        call for call in mock_record.call_args_list if call.args[0] == "chat_completed"
    )
    assert completed_call.kwargs["requested_model"] == "qwen3-4b-q4_k_m.gguf"
    assert completed_call.kwargs["model"] == "qwen3-4b-q4_k_m.gguf"


async def test_chat_uses_runtime_model_over_requested_model(client):
    captured = {}

    def _capture_init(self, session_id, model):
        captured["model"] = model
        self.session_id = session_id
        self.model = model
        self._messages = []

    async def _mock_query(self, user_content, abort_event=None):
        yield "data: [DONE]\n\n"

    with (
        patch("app.routes.chat.runtime.ensure_ready", return_value=_runtime_model("auto.gguf")),
        patch.object(query_engine.QueryEngine, "__init__", _capture_init),
        patch.object(query_engine.QueryEngine, "query", _mock_query),
        patch("app.routes.chat.telemetry.record"),
    ):
        async with client.stream(
            "POST", "/api/chat", json={"message": "hello", "model": "ignored.gguf"}
        ) as response:
            async for _ in response.aiter_bytes():
                pass

    assert captured["model"] == "auto.gguf"


async def test_chat_requires_message_field(client):
    response = await client.post("/api/chat", json={})
    assert response.status_code == 422
