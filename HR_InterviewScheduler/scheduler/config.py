"""Configuration loader for the Interview Scheduler agent."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_MODEL_NAME = "gemini-3.8-flash"
DEFAULT_BACKEND = "in-memory"
_TRUTHY_VERTEX_VALUES = {"1", "true", "yes"}


def parse_use_vertex(value: str | None) -> bool:
    """Return True when GOOGLE_GENAI_USE_VERTEXAI is 1, true, or yes (case-insensitive)."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VERTEX_VALUES


def load_config(dotenv_path: Path | str | None = ENV_PATH) -> None:
    """Load .env without overriding existing environment variables and refresh settings."""
    global MODEL_NAME, USE_VERTEX, PROJECT, BACKEND
    if dotenv_path is not None:
        load_dotenv(dotenv_path=dotenv_path, override=False)
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and not Path(creds_path).exists():
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    MODEL_NAME = os.environ.get("SCHEDULER_MODEL") or DEFAULT_MODEL_NAME
    USE_VERTEX = parse_use_vertex(os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"))
    PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
    BACKEND = (os.environ.get("SCHEDULER_BACKEND") or DEFAULT_BACKEND).strip()


MODEL_NAME: str = DEFAULT_MODEL_NAME
USE_VERTEX: bool = False
PROJECT: str | None = None
BACKEND: str = DEFAULT_BACKEND

load_config()
