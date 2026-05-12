"""Configuration values for the RubberDuck application."""

import os
import pathlib


OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")

SESSIONS_DIR: pathlib.Path = pathlib.Path(
	os.getenv("SESSIONS_DIR", "./sessions")
)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

TELEMETRY_LOG: pathlib.Path = pathlib.Path(
    os.getenv("TELEMETRY_LOG", "./telemetry.jsonl")
)
