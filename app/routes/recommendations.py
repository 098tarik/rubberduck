"""Hardware-aware model recommendation API route.

GET /api/recommendations
  Detects CPU/GPU/RAM, queries the Ollama library for available models,
  and returns the top 5 recommendations with tradeoff analysis.
"""

from __future__ import annotations

import asyncio
from typing import Any

import fastapi
import httpx

from app import config, telemetry
from app.hardware import HardwareProfile, detect_hardware
from app.model_catalog import CATALOG, ModelSpec

router = fastapi.APIRouter()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compatibility_label(spec: ModelSpec, hw: HardwareProfile) -> str:
    """Return 'full_gpu' | 'partial_gpu' | 'cpu_ok' | 'too_large'."""
    if hw.total_vram_gb >= spec.min_vram_gb and spec.min_vram_gb > 0:
        return "full_gpu"
    if hw.total_vram_gb > 0 and hw.total_vram_gb >= spec.min_vram_gb * 0.5:
        return "partial_gpu"
    if hw.ram_gb >= spec.min_ram_gb:
        return "cpu_ok"
    return "too_large"


def _score(spec: ModelSpec, hw: HardwareProfile) -> float:
    """Composite score (higher = better recommendation for this hardware)."""
    compat = _compatibility_label(spec, hw)

    if compat == "too_large":
        return -1.0  # cannot run

    # Base: quality + adjusted speed
    base = spec.quality_score * 0.55 + spec.speed_score * 0.35

    # Bonus for running on GPU
    gpu_bonus = {"full_gpu": 1.5, "partial_gpu": 0.5, "cpu_ok": 0.0}.get(compat, 0.0)

    # Penalise models that are massively over-spec (prefer snug fit)
    if hw.effective_memory_gb > 0:
        headroom_ratio = hw.effective_memory_gb / max(spec.min_vram_gb or spec.min_ram_gb, 0.5)
        overspec_penalty = max(0.0, (headroom_ratio - 4) * 0.1)  # light penalty when >4× headroom
    else:
        overspec_penalty = 0.0

    return base + gpu_bonus * 0.10 - overspec_penalty


def _rank_models(hw: HardwareProfile, top_n: int = 5) -> list[dict[str, Any]]:
    """Score every catalog entry against the hardware and return top_n."""
    scored: list[tuple[float, ModelSpec]] = []
    for spec in CATALOG:
        # Skip embedding-only models from chat recommendations
        if "embedding" in spec.tags:
            continue
        s = _score(spec, hw)
        if s >= 0:
            scored.append((s, spec))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for rank, (score, spec) in enumerate(scored[:top_n], 1):
        compat = _compatibility_label(spec, hw)
        results.append(_format_recommendation(rank, spec, hw, compat, score))

    return results


def _compat_description(compat: str, hw: HardwareProfile, spec: ModelSpec) -> str:
    if compat == "full_gpu":
        gpu = hw.primary_gpu
        gpu_name = gpu.name if gpu else "GPU"
        return f"Fully offloaded to {gpu_name} ({hw.total_vram_gb:.1f} GB VRAM)"
    if compat == "partial_gpu":
        return (
            f"Partial GPU offload ({hw.total_vram_gb:.1f} GB VRAM available, "
            f"{spec.min_vram_gb:.1f} GB needed for full offload) — some layers on CPU"
        )
    return f"CPU-only ({hw.ram_gb:.1f} GB RAM, model needs ~{spec.min_ram_gb:.1f} GB)"


def _format_recommendation(
    rank: int,
    spec: ModelSpec,
    hw: HardwareProfile,
    compat: str,
    score: float,
) -> dict[str, Any]:
    speed_labels = {range(1, 4): "slow", range(4, 7): "moderate", range(7, 11): "fast"}
    speed_label = next(
        (label for r, label in speed_labels.items() if int(spec.speed_score) in r), "moderate"
    )
    quality_labels = {range(1, 5): "basic", range(5, 7): "good", range(7, 9): "great", range(9, 11): "excellent"}
    quality_label = next(
        (label for r, label in quality_labels.items() if int(spec.quality_score) in r), "good"
    )

    tradeoffs: list[str] = []
    if compat == "full_gpu":
        tradeoffs.append("Fastest possible — full GPU acceleration")
    elif compat == "partial_gpu":
        tradeoffs.append("Moderate speed — partial GPU offload, some CPU bottleneck")
    else:
        tradeoffs.append("CPU inference — slower than GPU but still usable")

    if spec.min_ram_gb > hw.ram_gb * 0.7:
        tradeoffs.append("High memory pressure — close to your RAM limit")

    if spec.speed_score >= 8:
        tradeoffs.append("Very responsive for interactive use")

    if spec.quality_score >= 8.5:
        tradeoffs.append("Near frontier model quality")
    elif spec.quality_score <= 5:
        tradeoffs.append("Limited output quality — best for simple tasks")

    if "embedding" in spec.tags:
        tradeoffs.append("Embedding-only model — not for conversational use")

    return {
        "rank": rank,
        "model": spec.name,
        "display_name": spec.display_name,
        "parameters": f"{spec.param_billions:.1f}B",
        "context_window": f"{spec.context_k}k tokens",
        "compatibility": compat,
        "compatibility_detail": _compat_description(compat, hw, spec),
        "speed": speed_label,
        "quality": quality_label,
        "strengths": spec.strengths,
        "weaknesses": spec.weaknesses,
        "use_cases": spec.use_cases,
        "tradeoffs": tradeoffs,
        "tags": spec.tags,
        "score": round(score, 3),
        "ollama_pull": f"ollama pull {spec.name}",
    }


# ---------------------------------------------------------------------------
# Ollama library fetch
# ---------------------------------------------------------------------------

async def _fetch_ollama_popular(client: httpx.AsyncClient) -> list[str]:
    """
    Query the Ollama registry search endpoint.
    Returns a list of model names available in the library.
    Falls back to an empty list on any error.
    """
    try:
        resp = await client.get(
            "https://ollama.com/search",
            params={"q": "", "p": "1"},
            headers={"Accept": "text/html"},
            timeout=8.0,
            follow_redirects=True,
        )
        # Parse model names from href="/library/<name>" patterns in HTML
        import re
        names = re.findall(r'href="/library/([a-zA-Z0-9._:-]+)"', resp.text)
        seen: set[str] = set()
        unique = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        return unique[:50]  # top 50 from search page
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("/recommendations")
async def get_recommendations() -> dict[str, Any]:
    """
    Detect hardware capabilities and return top 5 Ollama model recommendations
    with tradeoff analysis.
    """
    # Run hardware detection in a thread (subprocess calls)
    hw: HardwareProfile = await asyncio.get_event_loop().run_in_executor(
        None, detect_hardware
    )

    telemetry.record(
        "recommendations_requested",
        ram_gb=hw.ram_gb,
        cpu_cores=hw.cpu_cores,
        gpu_count=len(hw.gpus),
        total_vram_gb=hw.total_vram_gb,
    )

    # Fetch Ollama library concurrently with scoring
    async with httpx.AsyncClient() as client:
        ollama_popular_task = asyncio.create_task(_fetch_ollama_popular(client))

        top5 = _rank_models(hw, top_n=5)

        ollama_popular = await ollama_popular_task

    # Mark which recommendations are already in the Ollama library list
    ollama_set = set(ollama_popular)
    for rec in top5:
        base_name = rec["model"].split(":")[0]
        rec["in_ollama_library"] = (
            rec["model"] in ollama_set or base_name in ollama_set
        )

    hardware_summary = {
        "platform": hw.platform,
        "cpu_cores": hw.cpu_cores,
        "cpu_threads": hw.cpu_threads,
        "ram_gb": hw.ram_gb,
        "gpus": [
            {"name": g.name, "vram_gb": g.vram_gb, "type": g.gpu_type}
            for g in hw.gpus
        ],
        "total_vram_gb": hw.total_vram_gb,
        "effective_memory_gb": round(hw.effective_memory_gb, 1),
        "has_discrete_gpu": hw.has_discrete_gpu,
        "has_apple_silicon": hw.has_apple_silicon,
    }

    return {
        "hardware": hardware_summary,
        "recommendations": top5,
        "ollama_library_sample": ollama_popular[:20],
    }
