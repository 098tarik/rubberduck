"""Embedded llama.cpp runtime bootstrap and model selection."""

from __future__ import annotations

import asyncio
import ctypes
import os
import pathlib
import platform
import subprocess
from dataclasses import dataclass

import httpx

from app import config, telemetry


@dataclass(frozen=True)
class ModelRecommendation:
    """A single recommended model for the current machine profile."""

    name: str
    url: str
    n_ctx: int
    n_gpu_layers: int


_ready_lock = asyncio.Lock()
_cached_recommendation: ModelRecommendation | None = None
_server_process: subprocess.Popen[str] | None = None


def _total_memory_gib() -> float:
    """Best-effort total system memory detection in GiB."""
    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            if isinstance(page_size, int) and isinstance(pages, int):
                return (page_size * pages) / (1024**3)
        except (OSError, ValueError):
            pass

    if platform.system() == "Windows":
        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024**3)

    return 8.0


def _recommended_model_for_machine() -> ModelRecommendation:
    """Pick exactly one recommended model for this machine."""
    machine = platform.machine().lower()
    mem_gib = _total_memory_gib()

    if machine in {"arm64", "aarch64"} and platform.system() == "Darwin":
        return ModelRecommendation(
            name="qwen3-4b-q4_k_m.gguf",
            url="https://huggingface.co/bartowski/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true",
            n_ctx=4096,
            n_gpu_layers=99,
        )

    if mem_gib >= 16:
        return ModelRecommendation(
            name="qwen3-8b-q4_k_m.gguf",
            url="https://huggingface.co/bartowski/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true",
            n_ctx=4096,
            n_gpu_layers=35,
        )

    return ModelRecommendation(
        name="qwen3-4b-q4_k_m.gguf",
        url="https://huggingface.co/bartowski/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true",
        n_ctx=4096,
        n_gpu_layers=0,
    )


def get_selected_model() -> ModelRecommendation:
    """Return the singleton model recommendation for this environment."""
    global _cached_recommendation
    if _cached_recommendation is None:
        _cached_recommendation = _recommended_model_for_machine()
    return _cached_recommendation


async def _download_if_missing(model: ModelRecommendation) -> pathlib.Path:
    """Download the recommended model once if missing locally."""
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = config.MODELS_DIR / model.name
    if model_path.exists() and model_path.stat().st_size > 0:
        return model_path

    tmp_path = model_path.with_suffix(model_path.suffix + ".part")
    timeout = httpx.Timeout(connect=20.0, read=300.0, write=60.0, pool=60.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", model.url) as response:
            response.raise_for_status()
            with tmp_path.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        handle.write(chunk)
    tmp_path.replace(model_path)
    telemetry.record("runtime_model_downloaded", model=model.name, path=str(model_path))
    return model_path


async def _server_healthy() -> bool:
    """Return True when llama-server health endpoint responds."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{config.LLAMA_SERVER_URL}/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _start_server(model_path: pathlib.Path, model: ModelRecommendation) -> None:
    """Start llama.cpp server if it is not already running."""
    global _server_process
    if await _server_healthy():
        return

    if not config.LLAMA_CPP_SERVER_BIN.exists():
        telemetry.record(
            "runtime_server_missing",
            binary=str(config.LLAMA_CPP_SERVER_BIN),
        )
        return

    cmd = [
        str(config.LLAMA_CPP_SERVER_BIN),
        "--model",
        str(model_path),
        "--ctx-size",
        str(model.n_ctx),
        "--port",
        str(config.LLAMA_SERVER_PORT),
    ]
    if model.n_gpu_layers > 0:
        cmd.extend(["--n-gpu-layers", str(model.n_gpu_layers)])

    _server_process = subprocess.Popen(  # noqa: S603
        cmd,
        cwd=str(config.LLAMA_CPP_SERVER_BIN.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    telemetry.record(
        "runtime_server_started",
        binary=str(config.LLAMA_CPP_SERVER_BIN),
        model=model.name,
        port=config.LLAMA_SERVER_PORT,
    )

    for _ in range(40):
        if await _server_healthy():
            return
        await asyncio.sleep(0.25)


async def ensure_ready() -> ModelRecommendation:
    """Ensure embedded runtime is ready and return the selected model."""
    async with _ready_lock:
        selected = get_selected_model()
        model_path = await _download_if_missing(selected)
        await _start_server(model_path, selected)
        return selected
