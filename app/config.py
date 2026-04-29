"""Configuration values for the RubberDuck application."""

import os
import pathlib


OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("OLLAMA_MODEL", "deepseek-r1:8b")

SESSIONS_DIR: pathlib.Path = pathlib.Path(
	os.getenv("SESSIONS_DIR", "./sessions")
)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
