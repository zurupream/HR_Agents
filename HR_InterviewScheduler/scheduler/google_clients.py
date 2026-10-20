"""Google OAuth credentials and API service builders for Calendar and Gmail."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DEFAULT_CLIENT_ID = (
    "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"
)
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = PROJECT_ROOT / "secrets"
TOKEN_FILE = SECRETS_DIR / "google_token.json"
TOKEN_PATH = TOKEN_FILE


def get_client_id() -> str:
    """Return the Google OAuth client ID from env or the default value."""
    return os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or DEFAULT_CLIENT_ID


def get_oauth_secret() -> str:
    """Read GOOGLE_OAUTH_CLIENT_SECRET from the environment at runtime."""
    secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not secret:
        raise RuntimeError(
            "Environment variable GOOGLE_OAUTH_CLIENT_SECRET is not set. "
            "Set GOOGLE_OAUTH_CLIENT_SECRET in your environment before authorizing or refreshing credentials."
        )
    return secret


def save_token(creds: Credentials, token_path: Path | str | None = None) -> Path:
    """Save OAuth token data (without any OAuth secret) with strict permissions."""
    path = Path(token_path) if token_path is not None else TOKEN_FILE
    secrets_dir = path.parent
    secrets_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(secrets_dir, 0o700)

    payload: dict[str, Any] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri or TOKEN_URI,
        "client_id": creds.client_id or get_client_id(),
        "scopes": list(creds.scopes) if creds.scopes else list(SCOPES),
    }
    if creds.expiry:
        payload["expiry"] = creds.expiry.isoformat().rstrip("Z") + "Z"

    serialized = json.dumps(payload, indent=2) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
    finally:
        if os.path.exists(path):
            os.chmod(path, 0o600)
    return path


def get_credentials(token_path: Path | str | None = None) -> Credentials:
    """Load the OAuth token file, refresh if expired, and return Credentials."""
    path = Path(token_path) if token_path is not None else TOKEN_FILE
    if not path.is_file():
        raise FileNotFoundError(
            f"Google OAuth token file not found at {path}. "
            "Run scripts/authorize_google.py to complete one-time OAuth consent."
        )

    info = json.loads(path.read_text(encoding="utf-8"))
    info.setdefault("client_id", get_client_id())
    info.setdefault("token_uri", TOKEN_URI)
    info["client_secret"] = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            get_oauth_secret()
            creds.refresh(Request())
            save_token(creds, path)
        else:
            raise RuntimeError(
                "Stored Google OAuth credentials are invalid and cannot be refreshed. "
                "Run scripts/authorize_google.py to re-authorize."
            )
    return creds


def build_calendar_service(credentials: Credentials | None = None) -> Any:
    """Build and return the Google Calendar v3 API service client."""
    creds = credentials or get_credentials()
    return build("calendar", "v3", credentials=creds)


def build_gmail_service(credentials: Credentials | None = None) -> Any:
    """Build and return the Gmail v1 API service client."""
    creds = credentials or get_credentials()
    return build("gmail", "v1", credentials=creds)
