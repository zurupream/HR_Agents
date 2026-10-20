"""Offline unit tests for Vertex AI and .env configuration loading."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from scheduler import agent, config

_ENV_KEYS = (
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "SCHEDULER_MODEL",
    "SCHEDULER_BACKEND",
)


@pytest.fixture(autouse=True)
def _restore_config_and_agent(monkeypatch):
    """Restore scheduler.config and scheduler.agent after each test's monkeypatch teardown."""
    yield
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(agent)


def test_dotenv_values_read_when_unset_and_existing_env_var_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "GOOGLE_GENAI_USE_VERTEXAI=1",
                "GOOGLE_CLOUD_PROJECT=dotenv-project-123",
                "GOOGLE_CLOUD_LOCATION=us-central1",
                "SCHEDULER_MODEL=gemini-3.8-flash",
                "SCHEDULER_BACKEND=google",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config.load_config(dotenv_path=dotenv_file)
    assert config.MODEL_NAME == "gemini-3.8-flash"
    assert config.USE_VERTEX is True
    assert config.PROJECT == "dotenv-project-123"
    assert config.BACKEND == "google"

    # Now set environment variables prior to loading .env and verify existing env vars win.
    monkeypatch.setenv("SCHEDULER_MODEL", "gemini-2.5-pro-override")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-override-project")
    monkeypatch.setenv("SCHEDULER_BACKEND", "in-memory")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")

    config.load_config(dotenv_path=dotenv_file)
    assert config.MODEL_NAME == "gemini-2.5-pro-override"
    assert config.PROJECT == "env-override-project"
    assert config.BACKEND == "in-memory"
    assert config.USE_VERTEX is False

    # Also verify reloading scheduler.config against the project's .env respects existing env vars.
    importlib.reload(config)
    assert config.MODEL_NAME == "gemini-2.5-pro-override"
    assert config.PROJECT == "env-override-project"
    assert config.BACKEND == "in-memory"
    assert config.USE_VERTEX is False


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        ("yes", True),
        ("Yes", True),
        (" 1 ", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("", False),
        (None, False),
    ],
)
def test_use_vertex_parsing(
    raw_value: str | None,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if raw_value is None:
        monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    else:
        monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", raw_value)

    config.load_config(dotenv_path=None)
    assert config.USE_VERTEX is expected


def test_agent_built_with_use_vertex_points_client_to_global_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-vertex-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    monkeypatch.setenv("SCHEDULER_MODEL", "gemini-3.8-flash")

    importlib.reload(config)
    importlib.reload(agent)

    model_obj = agent.root_agent.model
    assert isinstance(model_obj, agent.GlobalVertexGemini)
    assert model_obj.model == "gemini-3.8-flash"

    client = model_obj.api_client
    assert client.vertexai is True
    assert client._api_client.location == "global"
    assert client._api_client.project == "test-vertex-project"


def test_agent_built_without_use_vertex_uses_plain_model_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "0")
    monkeypatch.setenv("SCHEDULER_MODEL", "gemini-2.5-flash")

    importlib.reload(config)
    importlib.reload(agent)

    assert isinstance(agent.root_agent.model, str)
    assert agent.root_agent.model == "gemini-2.5-flash"
