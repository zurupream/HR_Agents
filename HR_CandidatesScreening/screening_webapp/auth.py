"""Google Sign-In authentication and database-backed access control (T016, T017, T018).

- Verifies Google OAuth ID tokens server-side against Client ID:
  259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com
- Enforces database-backed access control (root_admins.json + allowed_users + allowed_domains).
- Migrates demo_allowed_emails.json and allowed_emails.json into allowed_users once on first start,
  keeping JSON files only as a documented fallback for tests when ALLOWED_EMAILS_FILE is set.
- Never stores or uses a client secret.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from screening_agent import agent as agent_module

from .database import AllowedDomain, AllowedUser, AuditLog, get_session, init_db

WEBAPP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEBAPP_DIR.parent.resolve()
DEFAULT_ALLOWED_EMAILS_PATH = WEBAPP_DIR / "config" / "allowed_emails.json"
DEFAULT_DEMO_ALLOWED_EMAILS_PATH = WEBAPP_DIR / "config" / "demo_allowed_emails.json"
DEFAULT_ROOT_ADMINS_PATH = WEBAPP_DIR / "config" / "root_admins.json"
GOOGLE_CLIENT_ID = agent_module.GOOGLE_OAUTH_CLIENT_ID

UNAUTHORIZED_PORTAL_MESSAGE = (
    "Your Google account signed in, but it is not authorised to use this app. "
    "Ask an admin to add your email."
)


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_demo_test_auth_enabled() -> bool:
    """Return True only when DEMO_TEST_AUTH is explicitly enabled for local demo mode."""
    return os.environ.get("DEMO_TEST_AUTH", "").strip().lower() in ("1", "true", "yes")


def _resolve_path_cross_platform(
    config_path: str | Path | None,
    env_var_name: str,
    default_path: Path,
) -> Path:
    """Resolve a configuration path across Linux and Windows (normalising backslashes)."""
    if config_path is not None:
        raw = str(config_path).strip().replace("\\", "/")
        candidate = Path(raw)
    elif os.environ.get(env_var_name):
        raw = os.environ[env_var_name].strip().replace("\\", "/")
        candidate = Path(raw)
    else:
        return default_path

    if candidate.is_absolute() or candidate.exists():
        return candidate
    rooted = PROJECT_ROOT / candidate
    if rooted.exists():
        return rooted
    return candidate


def _resolve_allowlist_path(config_path: str | Path | None = None) -> Path:
    """Resolve the allow-list file path across Linux and Windows (normalising backslashes)."""
    return _resolve_path_cross_platform(
        config_path, "ALLOWED_EMAILS_FILE", DEFAULT_ALLOWED_EMAILS_PATH
    )


def get_allowlist_filename(config_path: str | Path | None = None) -> str:
    """Return only the file name (basename) of the active allow-list file, never an internal path."""
    resolved = _resolve_allowlist_path(config_path)
    return resolved.name or DEFAULT_ALLOWED_EMAILS_PATH.name


def _read_emails_from_json_file(file_path: Path) -> list[str]:
    """Read and normalise a list of lowercase email addresses from a JSON file."""
    emails: list[str] = []
    if not file_path.exists():
        return emails
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        raw_list: list[Any] = []
        if isinstance(raw, list):
            raw_list = raw
        elif isinstance(raw, dict):
            val = (
                raw.get("allowed_emails")
                or raw.get("root_admins")
                or raw.get("emails")
                or []
            )
            if isinstance(val, list):
                raw_list = val
        for item in raw_list:
            cleaned = str(item).strip().lower()
            if cleaned and "@" in cleaned and cleaned not in emails:
                emails.append(cleaned)
    except Exception:
        pass
    return emails


def load_root_admins(config_path: str | Path | None = None) -> list[str]:
    """Load bootstrap root admin emails from screening_webapp/config/root_admins.json."""
    resolved_path = _resolve_path_cross_platform(
        config_path, "ROOT_ADMINS_FILE", DEFAULT_ROOT_ADMINS_PATH
    )
    return _read_emails_from_json_file(resolved_path)


def is_root_admin(email: str | None, config_path: str | Path | None = None) -> bool:
    """Return True if the given email is listed in root_admins.json."""
    if not email:
        return False
    cleaned = email.strip().lower()
    return bool(cleaned and cleaned in load_root_admins(config_path))


def load_allowed_emails(config_path: str | Path | None = None) -> list[str]:
    """Load the allowed HR email list from the JSON configuration file (test fallback).

    Default is empty ([]), which means nobody can access the app via fallback unless configured.
    """
    resolved_path = _resolve_allowlist_path(config_path)
    emails = _read_emails_from_json_file(resolved_path)

    env_emails = os.environ.get("ALLOWED_EMAILS", "").strip()
    if env_emails:
        for part in env_emails.split(","):
            cleaned = part.strip().lower()
            if cleaned and cleaned not in emails:
                emails.append(cleaned)

    return emails


def is_allowlist_enforced() -> bool:
    """Return True only when strict allow-list enforcement is explicitly enabled via ENFORCE_ALLOWLIST=1."""
    return os.environ.get("ENFORCE_ALLOWLIST", "").strip().lower() in ("1", "true", "yes")


def migrate_access_control(
    db: Session | None = None,
    demo_json_path: Path | None = None,
    prod_json_path: Path | None = None,
    root_admins_path: Path | None = None,
) -> dict[str, Any]:
    """Import emails from demo_allowed_emails.json, allowed_emails.json, and root_admins.json once.

    - Imports emails from demo_allowed_emails.json and allowed_emails.json as role='hr'.
    - Imports/promotes emails from root_admins.json (e.g. guruprem.saginadham@sybyl.com) as role='admin'.
    - Writes an audit_log entry ('migrate_allowlist') on first start and never duplicates users on subsequent starts.
    """
    init_db()
    owns_session = db is None
    session = db if db is not None else get_session()
    try:
        already_migrated = (
            session.query(AuditLog)
            .filter(AuditLog.action == "migrate_allowlist")
            .first()
            is not None
        )
        root_emails = load_root_admins(root_admins_path)
        now_utc = _utc_now_iso()

        if not already_migrated:
            d_path = demo_json_path or DEFAULT_DEMO_ALLOWED_EMAILS_PATH
            p_path = prod_json_path or DEFAULT_ALLOWED_EMAILS_PATH
            json_hr_emails: list[str] = []
            for addr in _read_emails_from_json_file(d_path) + _read_emails_from_json_file(p_path):
                if addr not in json_hr_emails:
                    json_hr_emails.append(addr)

            imported_hr: list[str] = []
            for email in json_hr_emails:
                existing = (
                    session.query(AllowedUser).filter(AllowedUser.email == email).first()
                )
                if existing is None:
                    session.add(
                        AllowedUser(
                            email=email,
                            role="hr",
                            added_by="system:migration",
                            added_at_utc=now_utc,
                            active=True,
                        )
                    )
                    imported_hr.append(email)

            session.flush()

            imported_admins: list[str] = []
            for admin_email in root_emails:
                existing = (
                    session.query(AllowedUser)
                    .filter(AllowedUser.email == admin_email)
                    .first()
                )
                if existing is None:
                    session.add(
                        AllowedUser(
                            email=admin_email,
                            role="admin",
                            added_by="system:root_admins.json",
                            added_at_utc=now_utc,
                            active=True,
                        )
                    )
                    imported_admins.append(admin_email)
                else:
                    existing.role = "admin"
                    existing.active = True
                    existing.added_by = "system:root_admins.json"
                    imported_admins.append(admin_email)

            session.add(
                AuditLog(
                    at_utc=now_utc,
                    actor_email="system",
                    action="migrate_allowlist",
                    detail=(
                        f"Migrated initial allow-list JSON files ({len(json_hr_emails)} HR email(s): "
                        f"{', '.join(json_hr_emails) if json_hr_emails else 'none'}) and "
                        f"root_admins.json ({len(root_emails)} root admin(s): "
                        f"{', '.join(root_emails) if root_emails else 'none'}) into allowed_users."
                    ),
                )
            )
            session.commit()
            return {
                "migrated": True,
                "imported_hr": imported_hr,
                "root_admins": imported_admins,
            }

        # On subsequent starts, ensure root_admins exist as active admin without re-importing JSON files
        changed = False
        for admin_email in root_emails:
            existing = (
                session.query(AllowedUser)
                .filter(AllowedUser.email == admin_email)
                .first()
            )
            if existing is None:
                session.add(
                    AllowedUser(
                        email=admin_email,
                        role="admin",
                        added_by="system:root_admins.json",
                        added_at_utc=now_utc,
                        active=True,
                    )
                )
                changed = True
            elif existing.role != "admin" or not existing.active:
                existing.role = "admin"
                existing.active = True
                changed = True

        if changed:
            session.commit()

        return {
            "migrated": False,
            "imported_hr": [],
            "root_admins": root_emails,
        }
    finally:
        if owns_session:
            session.close()


def verify_google_token(raw_token: str) -> dict[str, Any]:
    """Verify a Google ID token against GOOGLE_CLIENT_ID.

    When DEMO_TEST_AUTH=1 is set for the local demo flow, also accepts a mocked demo token
    ('demo-hr-token' or 'demo-token:<email>') so HR can test the UI before live OAuth setup.
    """
    if not raw_token or not raw_token.strip():
        raise ValueError("Missing Google ID token.")

    token = raw_token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise ValueError("Empty Bearer token.")

    if is_demo_test_auth_enabled():
        if token == "demo-hr-token":
            return {
                "email": "hr.demo@example.com",
                "name": "Demo HR Reviewer (Demo Only)",
                "sub": "demo-hr-001",
                "aud": GOOGLE_CLIENT_ID,
                "iss": "https://accounts.google.com",
                "demo_mode": True,
            }
        if token.startswith("demo-token:"):
            demo_email = token.split(":", 1)[1].strip() or "hr.demo@example.com"
            return {
                "email": demo_email,
                "name": demo_email.split("@")[0].replace(".", " ").title(),
                "sub": f"demo-{demo_email}",
                "aud": GOOGLE_CLIENT_ID,
                "iss": "https://accounts.google.com",
                "demo_mode": True,
            }

    return agent_module.verify_google_id_token(token)


def _is_test_json_fallback_active() -> bool:
    """Return True when ALLOWED_EMAILS_FILE or ALLOWED_EMAILS is explicitly set for legacy tests."""
    return bool(
        os.environ.get("ALLOWED_EMAILS_FILE", "").strip()
        or os.environ.get("ALLOWED_EMAILS", "").strip()
    )


def require_hr_auth(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency that verifies the Google ID token (401) against GOOGLE_CLIENT_ID.

    By default, any user who authenticates with a valid Google ID token issued for
    GOOGLE_CLIENT_ID is allowed to log in as HR (or Admin if listed in root_admins.json / allowed_users),
    unless explicitly deactivated by an admin or strict allow-list mode (ENFORCE_ALLOWLIST=1) is enabled.
    """
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Google ID token.",
        )

    try:
        claims = verify_google_token(authorization)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {exc}",
        ) from exc

    user_email = str(claims.get("email") or "").strip().lower()
    display_email = user_email or "unknown"

    # When ALLOWED_EMAILS_FILE is explicitly set to a custom test file (e.g. tmp_path/allowed_emails.json),
    # use the documented JSON fallback for legacy tests unless the user was explicitly added/modified in DB.
    fallback_active = _is_test_json_fallback_active()
    if not fallback_active:
        migrate_access_control()

    init_db()
    db = get_session()
    try:
        root_flag = is_root_admin(user_email)
        user_row = (
            db.query(AllowedUser).filter(AllowedUser.email == user_email).first()
            if user_email
            else None
        )

        # 1. If user is in allowed_users and explicitly deactivated (and not root admin), always deny with T018 message
        if user_row is not None and not user_row.active and not root_flag:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_PORTAL_MESSAGE,
            )

        # 2. Active allowed_users check (or root admin present in allowed_users)
        if user_row is not None and (user_row.active or root_flag):
            role = "admin" if root_flag else (user_row.role if user_row.role in ("admin", "hr") else "hr")
            claims["email"] = user_email
            claims["role"] = role
            claims["is_admin"] = role == "admin"
            claims["is_root_admin"] = root_flag
            claims["is_demo_user"] = (
                user_email == "hr.demo@example.com" or bool(claims.get("demo_mode"))
            )
            return claims

        # 3. Domain check in allowed_domains (if configured)
        user_domain = (
            user_email.split("@", 1)[1].strip().lower() if "@" in user_email else ""
        )
        if user_domain:
            domain_row = (
                db.query(AllowedDomain)
                .filter(AllowedDomain.domain == user_domain)
                .first()
            )
            if domain_row is not None:
                if not domain_row.active and not root_flag:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=UNAUTHORIZED_PORTAL_MESSAGE,
                    )
                role = "admin" if root_flag else (domain_row.role if domain_row.role in ("admin", "hr") else "hr")
                claims["email"] = user_email
                claims["role"] = role
                claims["is_admin"] = role == "admin"
                claims["is_root_admin"] = root_flag
                claims["is_demo_user"] = False
                return claims

        # 4. Documented fallback for legacy tests when ALLOWED_EMAILS_FILE / ALLOWED_EMAILS is set
        if fallback_active:
            allowed_emails = load_allowed_emails()
            allowlist_file = get_allowlist_filename()
            if not allowed_emails:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Access denied for '{display_email}': your Google account signed in fine, "
                        f"but the HR allow-list is empty. An administrator must add '{display_email}' "
                        f"to the allow-list file ({allowlist_file}) named in the settings."
                    ),
                )
            if user_email and user_email in allowed_emails:
                role = "admin" if root_flag else "hr"
                claims["email"] = user_email
                claims["role"] = role
                claims["is_admin"] = role == "admin"
                claims["is_root_admin"] = root_flag
                claims["is_demo_user"] = (
                    user_email == "hr.demo@example.com" or bool(claims.get("demo_mode"))
                )
                return claims
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied for '{display_email}': your Google account signed in fine, "
                    f"but '{display_email}' is not in the HR allow-list. An administrator must add "
                    f"'{display_email}' to the allow-list file ({allowlist_file}) named in the settings."
                ),
            )

        # 5. Root admin check (always allowed even if not yet in allowed_users)
        if root_flag:
            claims["email"] = user_email
            claims["role"] = "admin"
            claims["is_admin"] = True
            claims["is_root_admin"] = True
            claims["is_demo_user"] = False
            return claims

        # 6. Default OAuth Client rule: allow any user who authenticated with a valid token
        # from the configured Google OAuth Client ID (unless ENFORCE_ALLOWLIST=1 is set).
        if not is_allowlist_enforced():
            claims["email"] = user_email
            claims["role"] = "hr"
            claims["is_admin"] = False
            claims["is_root_admin"] = False
            claims["is_demo_user"] = (
                user_email == "hr.demo@example.com" or bool(claims.get("demo_mode"))
            )
            return claims

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNAUTHORIZED_PORTAL_MESSAGE,
        )
    finally:
        db.close()


def require_admin_auth(
    claims: dict[str, Any] = Depends(require_hr_auth),
) -> dict[str, Any]:
    """FastAPI dependency that ensures the signed-in user is an admin (returns 403 otherwise)."""
    if claims.get("role") != "admin" and not claims.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: only administrators can view or modify access settings.",
        )
    return claims
