"""Tests for embedded runtime bootstrap helpers."""

from unittest.mock import AsyncMock, patch

from app import runtime


def test_get_selected_model_returns_singleton(monkeypatch):
    monkeypatch.setattr(runtime, "_cached_recommendation", None)
    first = runtime.get_selected_model()
    second = runtime.get_selected_model()
    assert first == second


def test_recommended_model_prefers_smaller_variant_on_low_memory(monkeypatch):
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime, "_total_memory_gib", lambda: 8.0)
    recommended = runtime._recommended_model_for_machine()
    assert recommended.name == "qwen3-4b-q4_k_m.gguf"


async def test_ensure_ready_returns_selected_model(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_cached_recommendation", None)
    monkeypatch.setattr(runtime.config, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(
        runtime,
        "_download_if_missing",
        AsyncMock(),
    )
    monkeypatch.setattr(runtime, "_start_server", AsyncMock())
    model = runtime.ModelRecommendation(
        name="auto.gguf",
        url="https://example.com/model.gguf",
        n_ctx=4096,
        n_gpu_layers=0,
    )
    monkeypatch.setattr(runtime, "get_selected_model", lambda: model)

    ready = await runtime.ensure_ready()
    assert ready.name == "auto.gguf"
