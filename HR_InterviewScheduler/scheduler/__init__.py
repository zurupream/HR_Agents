import os

from . import config  # noqa: F401
from . import agent  # noqa: F401  (ADK discovers `root_agent` from this package)

if os.environ.get("SCHEDULER_SEED") == "merchandiser":
    from .sample_data import seed_merchandiser

    seed_merchandiser()
