"""Tests for the models API route."""

from unittest.mock import patch

import fastapi
import httpx
import pytest
from httpx import ASGITransport

from app.routes import models as models_module
from app import runtime

# Minimal FastAPI app with only the models router
_test_app = fastapi.FastAPI()
_test_app.include_router(models_module.router, prefix="/api")


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


async def test_list_models_returns_single_auto_selected_model(client):
    with (
        patch("app.routes.models.runtime.ensure_ready", return_value=_runtime_model("auto.gguf")),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    assert response.status_code == 200
    body = response.json()
    assert body["models"] == ["auto.gguf"]
    assert body["default"] == "auto.gguf"
    assert body["runtime"] == "embedded-llama.cpp"


async def test_list_models_records_telemetry(client):
    with (
        patch("app.routes.models.runtime.ensure_ready", return_value=_runtime_model("auto.gguf")),
        patch("app.routes.models.telemetry.record") as mock_record,
    ):
        await client.get("/api/models")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "models_listed" in events
