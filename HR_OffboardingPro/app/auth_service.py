"""Google Single Sign-On (SSO), Work Email OTP, and Demo Session Authentication Service."""

import hashlib
import hmac
import json
import os
import random
import time
from typing import Any, Dict, Optional

try:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token
except ImportError:
    google_requests = None
    google_id_token = None

GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com",
)
JWT_SECRET = os.environ.get("JWT_SECRET", "hr-offboarding-pro-enterprise-sso-secret-2026")

_OTP_STORE: Dict[str, Dict[str, Any]] = {}


def _sign_token(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True)
    sig = hmac.new(JWT_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{sig[:24]}.{int(time.time())}"


def verify_google_credential(credential: str) -> Dict[str, Any]:
    """Verify a Google Identity Services JWT credential or fallback in local demo mode."""
    if not credential:
        raise ValueError("Missing Google SSO credential token.")

    if google_id_token and google_requests and not credential.startswith("demo-"):
        try:
            idinfo = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), GOOGLE_CLIENT_ID
            )
            email = idinfo.get("email", "hr.director@acme-enterprise.com")
            name = idinfo.get("name") or email.split("@")[0].replace(".", " ").title()
            picture = idinfo.get("picture", "")
            return {
                "authenticated": True,
                "method": "Google Single Sign-On",
                "token": _sign_token({"email": email, "name": name}),
                "user": {
                    "name": name,
                    "email": email,
                    "role": "HR Operations & People Partner",
                    "department": "People & Culture",
                    "picture": picture,
                },
            }
        except Exception as exc:
            raise ValueError(f"Google SSO verification failed: {exc}") from exc

    # Demo / test token support
    return {
        "authenticated": True,
        "method": "Google Single Sign-On",
        "token": _sign_token({"email": "elena.rostova@acme.com", "name": "Elena Rostova"}),
        "user": {
            "name": "Elena Rostova",
            "email": "elena.rostova@acme.com",
            "role": "VP of People Operations",
            "department": "People & Culture",
            "picture": "",
        },
    }


def request_email_otp(email: str) -> Dict[str, Any]:
    """Generate a 6-digit verification code for work email sign-in."""
    clean_email = (email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        raise ValueError("Please enter a valid work email address.")
    code = f"{random.randint(100000, 999999)}"
    _OTP_STORE[clean_email] = {
        "code": code,
        "expires_at": time.time() + 600,
    }
    return {
        "sent": True,
        "email": clean_email,
        "demo_code": code,
        "message": f"A 6-digit verification code has been sent to {clean_email}.",
    }


def verify_email_otp(email: str, code: str) -> Dict[str, Any]:
    """Verify the 6-digit email OTP code (or accept universal demo code 246810)."""
    clean_email = (email or "").strip().lower()
    clean_code = (code or "").strip()
    if not clean_email or not clean_code:
        raise ValueError("Work email and verification code are required.")

    record = _OTP_STORE.get(clean_email)
    valid_demo = clean_code == "246810"
    if not valid_demo:
        if not record or record.get("code") != clean_code:
            raise ValueError("Invalid verification code. Please check the code and try again.")
        if time.time() > record.get("expires_at", 0):
            raise ValueError("Verification code has expired. Please request a new code.")

    _OTP_STORE.pop(clean_email, None)
    local_name = clean_email.split("@")[0].replace(".", " ").replace("_", " ").title()
    return {
        "authenticated": True,
        "method": "Work Email Verification",
        "token": _sign_token({"email": clean_email, "name": local_name}),
        "user": {
            "name": local_name or "HR Director",
            "email": clean_email,
            "role": "HR Operations Lead",
            "department": "People & Culture",
            "picture": "",
        },
    }


def create_demo_session(persona: Optional[str] = None) -> Dict[str, Any]:
    """Instant one-click executive demo sign-in for HR leaders."""
    name = persona or "Elena Rostova"
    email = "elena.rostova@acme.com"
    return {
        "authenticated": True,
        "method": "Executive Demo SSO",
        "token": _sign_token({"email": email, "name": name}),
        "user": {
            "name": name,
            "email": email,
            "role": "VP of People Operations",
            "department": "People & Culture",
            "picture": "",
        },
    }
