"""One-time Google OAuth consent script for Calendar and Gmail access."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google_auth_oauthlib.flow import InstalledAppFlow

from scheduler import config  # noqa: F401
from scheduler.google_clients import (
    AUTH_URI,
    SCOPES,
    TOKEN_FILE,
    TOKEN_URI,
    get_client_id,
    get_oauth_secret,
    save_token,
)

REDIRECT_URI = "http://localhost:8765/"


def _extract_code(user_input: str) -> str:
    """Extract the OAuth authorization code from either a redirect URL or raw code."""
    cleaned = user_input.strip()
    if not cleaned:
        raise ValueError("No authorization code provided.")
    if cleaned.startswith(("http://", "https://")) or "code=" in cleaned:
        parsed = urlparse(cleaned)
        query_code = parse_qs(parsed.query).get("code")
        if query_code and query_code[0]:
            return query_code[0]
    return cleaned


def build_flow() -> InstalledAppFlow:
    """Create the InstalledAppFlow from environment credentials and required scopes."""
    get_oauth_secret()
    client_config = {
        "installed": {
            "client_id": get_client_id(),
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [REDIRECT_URI],
        }
    }
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    flow.redirect_uri = REDIRECT_URI
    return flow


def authorize(token_path: Path | str | None = None) -> Path:
    """Run the manual OAuth consent flow and save the token file with mode 600."""
    flow = build_flow()
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    print("Open the following URL in your browser to authorize access:\n")
    print(auth_url)
    print(
        "\nAfter granting access, copy the authorization code (or the full "
        f"{REDIRECT_URI}?code=... redirect URL) and paste it below."
    )

    raw_response = input("Authorization code or redirect URL: ")
    code = _extract_code(raw_response)
    flow.fetch_token(code=code)

    saved_path = save_token(flow.credentials, token_path=token_path or TOKEN_FILE)
    print(f"Credentials saved to {saved_path}")
    return saved_path


def main() -> None:
    authorize()


if __name__ == "__main__":
    main()
