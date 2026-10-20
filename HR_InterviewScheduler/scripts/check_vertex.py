"""Verify Vertex AI configuration from .env without making any live API calls."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scheduler import config
from scheduler.agent import GlobalVertexGemini, root_agent


def main() -> None:
    env_found = config.ENV_PATH.is_file()
    model = root_agent.model
    if isinstance(model, GlobalVertexGemini):
        model_name = model.model
        client_location = model.api_client._api_client.location
    else:
        model_name = str(model)
        client_location = None

    print(f".env found: {env_found}")
    print(f"USE_VERTEX: {config.USE_VERTEX}")
    print(f"project: {config.PROJECT}")
    print(f"model: {model_name}")
    print(f"location: {client_location}")


if __name__ == "__main__":
    main()
