"""Module entrypoint for `python -m screening_webapp`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the HR web app on localhost only."""
    uvicorn.run(
        "screening_webapp.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8080")),
    )


if __name__ == "__main__":
    main()
