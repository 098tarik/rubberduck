"""Integration tests that query every model available on the Ollama instance."""

import json
import os

import httpx
import pytest


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
TEST_PROMPT = "Reply with exactly one word: hello"


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests that declare the ``model`` fixture with live Ollama models."""
    if "model" in metafunc.fixturenames:
        try:
            response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            pytest.skip(f"Ollama server unavailable: {exc}")
        models = [
            item["name"]
            for item in response.json().get("models", [])
            if item.get("name")
        ]
        metafunc.parametrize("model", models)


@pytest.mark.asyncio
async def test_model_returns_response(model: str) -> None:
    """Each available model must return at least one streamed content chunk."""
    received_text = ""

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": TEST_PROMPT}],
                "stream": True,
            },
            timeout=120.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                payload = json.loads(line)
                if payload.get("done"):
                    break
                received_text += payload.get("message", {}).get("content", "")

    assert received_text.strip(), (
        f"Model '{model}' returned an empty response to the test prompt."
    )
