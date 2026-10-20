"""Entrypoint module for running uvicorn screening_webapp.main:app."""

from .app import app

__all__ = ["app"]
