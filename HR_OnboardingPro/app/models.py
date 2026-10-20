"""Data models, enums, and role-based onboarding policy definitions."""

from enum import Enum
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RoleCategory(str, Enum):
    INTERN = "INTERN"
    TRAINEE = "TRAINEE"
    EMPLOYEE = "EMPLOYEE"


class OfferStatus(str, Enum):
    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    LAPSED = "LAPSED"


class TaskType(str, Enum):
    EMAIL = "EMAIL"
    LAPTOP = "LAPTOP"
    UBER = "UBER"
    INSURANCE = "INSURANCE"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


# Role-Based Post-Acceptance Onboarding Matrix
ROLE_ONBOARDING_STEPS: Dict[str, List[str]] = {
    RoleCategory.INTERN.value: [
        TaskType.EMAIL.value,
    ],
    RoleCategory.TRAINEE.value: [
        TaskType.EMAIL.value,
        TaskType.LAPTOP.value,
        TaskType.UBER.value,
    ],
    RoleCategory.EMPLOYEE.value: [
        TaskType.EMAIL.value,
        TaskType.LAPTOP.value,
        TaskType.UBER.value,
        TaskType.INSURANCE.value,
    ],
}

SUBAGENT_METADATA: Dict[str, Dict] = {
    TaskType.EMAIL.value: {
        "agent_id": "subagent-it-email",
        "agent_name": "IT Email Setup",
        "icon": "mail",
        "department": "IT Support",
        "depends_on": None,
        "applicable_roles": ["INTERN", "TRAINEE", "EMPLOYEE"],
        "stages": [
            "Request Sent to IT",
            "Checking Name & Email Availability",
            "Creating @sybyl.com Email Account",
            "Adding Department Mailing Lists",
            "Work Email Ready",
        ],
    },
    TaskType.LAPTOP.value: {
        "agent_id": "subagent-laptop-asset",
        "agent_name": "Laptop Request",
        "icon": "laptop",
        "department": "IT Equipment",
        "depends_on": None,
        "applicable_roles": ["TRAINEE", "EMPLOYEE"],
        "stages": [
            "Request Sent to IT Equipment",
            "Selecting Laptop Model for Role",
            "Assigning Laptop from Inventory",
            "Installing Standard Company Apps",
            "Laptop Ready for Pickup",
        ],
    },
    TaskType.UBER.value: {
        "agent_id": "subagent-uber-commute",
        "agent_name": "Uber Commute Pass",
        "icon": "car",
        "department": "Workplace & Transport",
        "depends_on": "EMAIL",
        "applicable_roles": ["TRAINEE", "EMPLOYEE"],
        "stages": [
            "Waiting for Work Email",
            "Creating Corporate Uber Profile",
            "Setting Monthly Commute Allowance",
            "Sending Welcome Invite to Email",
            "Uber Commute Pass Active",
        ],
    },
    TaskType.INSURANCE.value: {
        "agent_id": "subagent-health-insurance",
        "agent_name": "Health Insurance",
        "icon": "shield-check",
        "department": "People & Benefits",
        "depends_on": "EMAIL",
        "applicable_roles": ["EMPLOYEE"],
        "stages": [
            "Waiting for Work Email",
            "Selecting Employee Health Plan",
            "Registering with Insurance Provider",
            "Preparing Digital Health Card",
            "Health Insurance Active",
        ],
    },
}


def parse_cc_emails(
    cc_emails: Optional[str] = None,
    hr_email: Optional[str] = None,
    hod_email: Optional[str] = None,
    ceo_email: Optional[str] = None,
) -> List[str]:
    """Parses semicolon (;) or comma (,) separated CC email strings into a clean list."""
    raw_items: List[str] = []
    if cc_emails and cc_emails.strip():
        parts = re.split(r"[;,]+", cc_emails)
        raw_items.extend(parts)
    else:
        for e in (hr_email, hod_email, ceo_email):
            if e:
                raw_items.extend(re.split(r"[;,]+", e))

    # Also ensure department HoD email is included if not already present and if hod_email is provided
    seen = set()
    cleaned: List[str] = []
    for item in raw_items:
        addr = item.strip()
        if addr and "@" in addr and addr.lower() not in seen:
            seen.add(addr.lower())
            cleaned.append(addr)

    if not cleaned:
        cleaned = ["hr@sybyl.com", "ceo@sybyl.com"]
    return cleaned


class CandidateOfferInput(BaseModel):
    full_name: str = Field(..., description="Candidate full name")
    personal_email: str = Field(..., description="Candidate personal email")
    phone: Optional[str] = Field(default="+1-555-0199")
    position_id: str = Field(..., description="Position ID")
    role_category: RoleCategory = Field(..., description="INTERN, TRAINEE, or EMPLOYEE")
    compensation: Optional[str] = Field(default=None, description="Annual salary or monthly stipend")
    compensation_package: Optional[str] = Field(default=None, description="Alias for compensation")
    joining_date: str = Field(..., description="YYYY-MM-DD")
    offer_valid_hours: int = Field(default=72, description="Hours before offer expires")
    esign_provider: str = Field(default="ONLINE", description="Signature method")


class BatchOnboardingRequest(BaseModel):
    batch_name: str = Field(default="Hiring Wave")
    cc_emails: Optional[str] = Field(
        default=None,
        description="Multiple CC emails separated by semicolon (;), e.g., hr@sybyl.com; hod@sybyl.com; ceo@sybyl.com",
    )
    hr_email: str = Field(default="hr@sybyl.com")
    ceo_email: str = Field(default="ceo@sybyl.com")
    offer_expires_in_hours: Optional[int] = Field(default=72)
    candidates: List[CandidateOfferInput]


class PositionCreateRequest(BaseModel):
    title: str
    department: str
    hod_name: str
    hod_email: str
    headcount_target: int = 3
    location: str = "Head Office"


class OfferAcceptRequest(BaseModel):
    signer_name: str
    signature_data: Optional[str] = None
    signature_type: str = "typed"  # typed | drawn
    comments: Optional[str] = None


class OfferDeclineRequest(BaseModel):
    decline_reason: str = "Accepted another offer"
    comments: Optional[str] = None


class DocuSealWebhookPayload(BaseModel):
    event_type: str
    signing_token: str
    signer_name: Optional[str] = None
    decline_reason: Optional[str] = None


class SMTPConfigRequest(BaseModel):
    sender_email: str = "psrmreports@sybyl.com"
    app_password: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    live_mode_enabled: bool = True
    default_cc_emails: str = "hr@sybyl.com; hod@sybyl.com; ceo@sybyl.com"
    default_hr_email: str = "hr@sybyl.com"
    default_ceo_email: str = "ceo@sybyl.com"
    override_recipient_for_demo: Optional[str] = None


class OfferTemplateUpdateRequest(BaseModel):
    role_category: RoleCategory
    template_name: Optional[str] = None
    title: Optional[str] = None
    header_title: Optional[str] = None
    subject_line: Optional[str] = None
    email_subject: Optional[str] = None
    email_subject_template: Optional[str] = None
    intro_text: Optional[str] = None
    opening_text: Optional[str] = None
    terms_text: Optional[str] = None
    body_text: Optional[str] = None
    closing_text: Optional[str] = "Warm regards,\nPeople & Culture Team — Sybyl"

