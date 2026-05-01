"""Tests for the models API route."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import fastapi
import httpx
import pytest
from httpx import ASGITransport

from app.routes import models as models_module
import app.config as config

# Minimal FastAPI app with only the models router
_test_app = fastapi.FastAPI()
_test_app.include_router(models_module.router, prefix="/api")


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=ASGITransport(app=_test_app), base_url="http://test"
    ) as c:
        yield c


def _make_mock_client(json_data):
    """Return a mocked httpx.AsyncClient whose GET returns the given dict."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.return_value = mock_response

    return mock_client


async def test_list_models_returns_model_names(client):
    mock_client = _make_mock_client(
        {"models": [{"name": "llama3"}, {"name": "mistral:7b"}]}
    )
    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    assert response.status_code == 200
    body = response.json()
    assert "llama3" in body["models"]
    assert "mistral:7b" in body["models"]


async def test_list_models_filters_cloud_models(client):
    mock_client = _make_mock_client(
        {"models": [{"name": "llama3"}, {"name": "gpt-4:cloud"}]}
    )
    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    body = response.json()
    assert "gpt-4:cloud" not in body["models"]
    assert "llama3" in body["models"]


async def test_list_models_returns_default(client, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_MODEL", "deepseek-r1:8b")
    mock_client = _make_mock_client({"models": [{"name": "deepseek-r1:8b"}]})
    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    body = response.json()
    assert body["default"] == "deepseek-r1:8b"


async def test_list_models_ignores_entries_without_name(client):
    mock_client = _make_mock_client(
        {"models": [{"name": "llama3"}, {}, {"name": ""}]}
    )
    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    body = response.json()
    assert body["models"] == ["llama3"]


async def test_list_models_graceful_on_http_error(client, monkeypatch):
    monkeypatch.setattr(config, "DEFAULT_MODEL", "deepseek-r1:8b")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.side_effect = httpx.ConnectError("refused")

    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record"),
    ):
        response = await client.get("/api/models")

    assert response.status_code == 200
    body = response.json()
    # Falls back to default model and includes an error key
    assert body["default"] == "deepseek-r1:8b"
    assert "error" in body


async def test_list_models_records_telemetry_on_success(client):
    mock_client = _make_mock_client({"models": [{"name": "llama3"}]})
    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record") as mock_record,
    ):
        await client.get("/api/models")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "models_listed" in events


async def test_list_models_records_telemetry_on_error(client):
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get.side_effect = httpx.ConnectError("refused")

    with (
        patch("app.routes.models.httpx.AsyncClient", return_value=mock_client),
        patch("app.routes.models.telemetry.record") as mock_record,
    ):
        await client.get("/api/models")

    events = [call.args[0] for call in mock_record.call_args_list]
    assert "models_listed_error" in events
