"""Configuration values for the RubberDuck application."""

import os
import pathlib


OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")
LLAMA_SERVER_HOST: str = os.getenv("LLAMA_SERVER_HOST", "127.0.0.1")
LLAMA_SERVER_PORT: int = int(os.getenv("LLAMA_SERVER_PORT", "8080"))
LLAMA_SERVER_URL: str = os.getenv(
    "LLAMA_SERVER_URL",
    f"http://{LLAMA_SERVER_HOST}:{LLAMA_SERVER_PORT}/v1",
)
LLAMA_CPP_SERVER_BIN: pathlib.Path = pathlib.Path(
    os.getenv("LLAMA_CPP_SERVER_BIN", "./runtime/llama-server")
)
MODELS_DIR: pathlib.Path = pathlib.Path(
    os.getenv("MODELS_DIR", "./models")
)

SESSIONS_DIR: pathlib.Path = pathlib.Path(
	os.getenv("SESSIONS_DIR", "./sessions")
)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

TELEMETRY_LOG: pathlib.Path = pathlib.Path(
    os.getenv("TELEMETRY_LOG", "./telemetry.jsonl")
)
