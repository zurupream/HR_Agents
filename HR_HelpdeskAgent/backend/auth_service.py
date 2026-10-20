"""auth_service.py - Single Sign-On (Google SSO, Work Email 6-Digit Verification Code, and Instant Demo Sign-In)."""

from __future__ import annotations
import hashlib
import hmac
import logging
import os
import re
import secrets
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Dict, Set, Tuple

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"
DEFAULT_OAUTH_CLIENT_ID = GOOGLE_CLIENT_ID

BLOCKED_CONSUMER_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.co.in",
        "yahoo.ca", "yahoo.fr", "yahoo.de", "yahoo.es", "yahoo.it", "yahoo.com.au",
        "yahoo.co.jp", "yahoo.com.br", "yahoo.com.sg", "yahoo.co.za", "yahoo.co.ke",
        "ymail.com", "rocketmail.com", "hotmail.com", "hotmail.co.uk", "hotmail.fr",
        "hotmail.de", "outlook.com", "outlook.co.uk", "outlook.fr", "outlook.de",
        "outlook.in", "live.com", "live.co.uk", "msn.com", "passport.com", "aol.com",
        "aol.co.uk", "aim.com", "icloud.com", "me.com", "mac.com", "proton.me",
        "protonmail.com", "protonmail.ch", "pm.me", "gmx.com", "gmx.de", "gmx.net",
        "web.de", "mail.com", "email.com", "usa.com", "mail.ru", "yandex.com",
        "yandex.ru", "zoho.com", "zohomail.com", "zohomail.in", "qq.com", "163.com",
        "126.com", "naver.com", "daum.net", "rediffmail.com", "rediff.com",
        "fastmail.com", "tutanota.com", "tuta.io", "tuta.com", "hey.com", "hushmail.com",
    }
)

BLOCKED_CONSUMER_PREFIXES: frozenset[str] = frozenset(
    {
        "gmail", "googlemail", "yahoo", "ymail", "rocketmail", "hotmail",
        "outlook", "live", "msn", "aol", "icloud", "protonmail", "gmx",
        "yandex", "zohomail", "rediffmail",
    }
)

BLOCKED_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com", "guerrillamail.com", "sharklasers.com", "10minutemail.com",
        "temp-mail.org", "tempmail.com", "yopmail.com", "trashmail.com", "getnada.com",
        "dispostable.com", "maildrop.cc", "fakeinbox.com", "mailnesia.com",
        "throwawaymail.com", "mohmal.com", "burnermail.io",
    }
)

BLOCKED_DISPOSABLE_PREFIXES: frozenset[str] = frozenset(
    {
        "mailinator", "guerrillamail", "10minutemail", "temp-mail", "tempmail",
        "yopmail", "sharklasers", "trashmail", "getnada", "dispostable",
        "maildrop", "fakeinbox", "throwawaymail", "mailnesia",
    }
)

_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_GOOGLE_REQUEST = google_requests.Request()

AUTH_APPROVAL_MESSAGE = (
    "This preview is limited to approved work accounts. "
    "Please sign in with your work email address, or contact HR to have your organisation added."
)

CONSUMER_DOMAIN_REJECTION_MESSAGE = (
    "Please sign in using your company work email address. "
    "Personal email addresses (such as Gmail, Outlook, or Yahoo) are not accepted."
)

DISPOSABLE_DOMAIN_REJECTION_MESSAGE = (
    "Temporary or disposable email addresses are not accepted. "
    "Please use your company work email."
)

_OTP_STORE: Dict[str, Dict[str, Any]] = {}


def format_name_from_email(email: str) -> str:
    local = (email or "").split("@")[0].strip()
    if not local:
        return ""
    parts = [p for p in re.split(r"[._\-+]+", local) if p]
    return " ".join(p.capitalize() for p in parts) if parts else local.capitalize()


def is_open_business_signup() -> bool:
    return os.getenv("OPEN_BUSINESS_SIGNUP", "1").strip().lower() in ("1", "true", "yes")


def get_allowed_domains() -> Set[str]:
    raw = os.getenv("ALLOWED_DOMAINS", "sybyl.com,kimisitusacco.or.ke")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def get_allowed_emails() -> Set[str]:
    raw = os.getenv("ALLOWED_EMAILS", "guruprem.saginadham@sybyl.com,zuruprem@gmail.com")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_plausible_domain(domain: str) -> bool:
    if not domain or not isinstance(domain, str):
        return False
    d = domain.strip().lower()
    if not d or " " in d or "." not in d or d.startswith(".") or d.endswith(".") or ".." in d:
        return False
    labels = d.split(".")
    if len(labels) < 2:
        return False
    for label in labels:
        if not label or not _DOMAIN_LABEL_RE.match(label):
            return False
    tld = labels[-1]
    return len(tld) >= 2 and (tld.isalpha() or tld.startswith("xn--"))


def is_plausible_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    clean = email.strip().lower()
    if not clean or " " in clean:
        return False
    parts = clean.split("@")
    if len(parts) != 2:
        return False
    local, domain = parts[0], parts[1]
    if not local or local.startswith(".") or local.endswith(".") or ".." in local:
        return False
    return is_plausible_domain(domain)


def is_consumer_domain(domain: str) -> bool:
    if not domain:
        return False
    d = domain.strip().lower()
    if d in BLOCKED_CONSUMER_DOMAINS:
        return True
    labels = [lbl for lbl in d.split(".") if lbl]
    for i in range(1, len(labels) - 1):
        if ".".join(labels[i:]) in BLOCKED_CONSUMER_DOMAINS:
            return True
    return bool(labels and labels[0] in BLOCKED_CONSUMER_PREFIXES)


def is_disposable_domain(domain: str) -> bool:
    if not domain:
        return False
    d = domain.strip().lower()
    if d in BLOCKED_DISPOSABLE_DOMAINS:
        return True
    labels = [lbl for lbl in d.split(".") if lbl]
    for i in range(1, len(labels) - 1):
        if ".".join(labels[i:]) in BLOCKED_DISPOSABLE_DOMAINS:
            return True
    return bool(labels and labels[0] in BLOCKED_DISPOSABLE_PREFIXES)


def is_blocked_domain(domain: str) -> bool:
    return is_consumer_domain(domain) or is_disposable_domain(domain)


def is_domain_allowed(domain: str) -> bool:
    return bool(domain and domain.strip().lower() in get_allowed_domains())


def is_email_allowed(email: str) -> bool:
    return bool(email and email.strip().lower() in get_allowed_emails())


def is_access_allowed(email: str) -> bool:
    if not is_plausible_email(email):
        return False
    clean_email = email.strip().lower()
    if is_email_allowed(clean_email):
        return True
    domain = clean_email.split("@")[-1]
    if is_domain_allowed(domain):
        return True
    if is_open_business_signup():
        return not is_blocked_domain(domain)
    return False


def get_otp_rejection_message(email: str) -> str:
    clean_email = (email or "").strip().lower()
    domain = clean_email.split("@")[-1] if "@" in clean_email else ""
    if is_consumer_domain(domain):
        return CONSUMER_DOMAIN_REJECTION_MESSAGE
    if is_disposable_domain(domain):
        return DISPOSABLE_DOMAIN_REJECTION_MESSAGE
    return AUTH_APPROVAL_MESSAGE


def _hash_code(email: str, code: str) -> str:
    secret = os.getenv("SESSION_SECRET", "hr-helpdesk-agent-otp-secret")
    return hmac.new(secret.encode("utf-8"), f"{email}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def generate_and_store_otp(email: str) -> str:
    clean_email = email.strip().lower()
    code = f"{secrets.randbelow(900000) + 100000:06d}"
    _OTP_STORE[clean_email] = {
        "code_hash": _hash_code(clean_email, code),
        "raw_code": code,
        "expires_at": time.time() + 600.0,
        "attempts": 0,
    }
    return code


def verify_stored_otp(email: str, code: str) -> Tuple[bool, str]:
    clean_email = (email or "").strip().lower()
    clean_code = (code or "").strip()
    entry = _OTP_STORE.get(clean_email)
    if not entry:
        return False, "No active verification code found for this email. Please request a new code."
    if time.time() > entry["expires_at"]:
        _OTP_STORE.pop(clean_email, None)
        return False, "Verification code has expired. Please request a new code."
    if entry["attempts"] >= 5:
        _OTP_STORE.pop(clean_email, None)
        return False, "Too many incorrect attempts. Please request a new verification code."
    expected_hash = _hash_code(clean_email, clean_code)
    if not hmac.compare_digest(entry["code_hash"], expected_hash):
        entry["attempts"] += 1
        return False, "Invalid verification code. Please check the 6-digit code sent to your email."
    _OTP_STORE.pop(clean_email, None)
    return True, "Verified"


def send_otp_email(to_address: str, code: str) -> bool:
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not password:
        logger.info("SMTP_PASSWORD not set; OTP code generated for %s", to_address)
        return False

    from_address = os.getenv("OTP_FROM_ADDRESS", "psrmreports@sybyl.com").strip()
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip())
    user = os.getenv("SMTP_USER", "psrmreports@sybyl.com").strip()
    use_ssl = os.getenv("SMTP_USE_SSL", "0") in ("1", "true", "True") or port == 465
    use_tls = os.getenv("SMTP_USE_TLS", "1") in ("1", "true", "True") and not use_ssl

    msg = EmailMessage()
    msg["Subject"] = "Your Employee HR Helpdesk Agent verification code"
    msg["From"] = from_address
    msg["To"] = to_address
    msg.set_content(
        f"Your verification code for the Employee HR Helpdesk Agent is: {code}\n\n"
        f"This code will expire in 10 minutes.\n\n"
        f"If you did not request this code, please ignore this message.\n"
    )
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=10) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(msg)
    logger.info("Sent OTP verification email to %s", to_address)
    return True


def verify_google_id_token(credential: str) -> Tuple[bool, Dict[str, Any], str]:
    if not credential or not credential.strip():
        return False, {}, "Missing Google credential token."
    try:
        client_id = (
            os.getenv("OAUTH_CLIENT_ID", "").strip()
            or os.getenv("GOOGLE_CLIENT_ID", "").strip()
            or DEFAULT_OAUTH_CLIENT_ID
        )
        claims = google_id_token.verify_oauth2_token(credential, _GOOGLE_REQUEST, client_id)
        if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            return False, {}, "Unexpected token issuer."
        if not claims.get("email_verified"):
            return False, {}, "Google account email is not verified."
        email = (claims.get("email") or "").strip().lower()
        if not email:
            return False, {}, AUTH_APPROVAL_MESSAGE
        hd = (claims.get("hd") or "").strip().lower()
        email_domain = email.split("@")[-1] if "@" in email else ""
        if not (
            is_email_allowed(email)
            or (hd and is_domain_allowed(hd))
            or (email_domain and is_domain_allowed(email_domain))
            or (hd and not is_blocked_domain(hd))
        ):
            return False, {}, AUTH_APPROVAL_MESSAGE
        raw_name = (claims.get("name") or "").strip()
        display_name = raw_name if raw_name else format_name_from_email(email)
        return (
            True,
            {
                "name": display_name,
                "email": email,
                "picture": claims.get("picture", ""),
                "role": "Employee & People Services View",
                "domain": hd or email_domain,
                "provider": "google",
            },
            "",
        )
    except Exception as exc:
        return False, {}, f"Google token verification failed: {exc}"
