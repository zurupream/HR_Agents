"""Domain models, role-based reverse offboarding matrices, and request schemas."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class RoleCategory(str, Enum):
    INTERN = "INTERN"
    TRAINEE = "TRAINEE"
    EMPLOYEE = "EMPLOYEE"


class ClearanceStatus(str, Enum):
    SENT = "SENT"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


# Alias for backward/cross-suite compatibility
OfferStatus = ClearanceStatus


class TaskType(str, Enum):
    INSURANCE = "INSURANCE"
    UBER = "UBER"
    LAPTOP = "LAPTOP"
    EMAIL = "EMAIL"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


# Exact Reverse Role-Based Offboarding Matrix:
# - Full-Time Employees first cancel Health Insurance, revoke Uber Pass, return Laptop, and finally deactivate Email
# - Trainees revoke Uber Pass, return Laptop, and finally deactivate Email
# - Interns only deactivate Work Email & Single Sign-On
ROLE_OFFBOARDING_STEPS: Dict[RoleCategory, List[TaskType]] = {
    RoleCategory.EMPLOYEE: [
        TaskType.INSURANCE,
        TaskType.UBER,
        TaskType.LAPTOP,
        TaskType.EMAIL,
    ],
    RoleCategory.TRAINEE: [
        TaskType.UBER,
        TaskType.LAPTOP,
        TaskType.EMAIL,
    ],
    RoleCategory.INTERN: [
        TaskType.EMAIL,
    ],
}

# Compatibility alias
ROLE_ONBOARDING_STEPS = ROLE_OFFBOARDING_STEPS


SUBAGENT_METADATA: Dict[TaskType, dict] = {
    TaskType.INSURANCE: {
        "agent_name": "Health Insurance Cancellation Agent",
        "title": "Health Insurance & Benefits Termination",
        "department": "People & Benefits",
        "icon": "shield-off",
        "description": "Terminates group medical policy, calculates final coverage date, and deactivates digital health cards.",
        "stages": [
            "Cancellation Request Sent to Benefits",
            "Verifying Final Coverage Date & Dependents",
            "Notifying Insurance Provider to Terminate Cover",
            "Deactivating Digital Health Card (HC)",
            "Health Insurance Cancelled",
        ],
        "depends_on": None,
        "applicable_roles": ["EMPLOYEE"],
    },
    TaskType.UBER: {
        "agent_name": "Uber Commute Pass Revocation Agent",
        "title": "Uber Commute Pass Revocation",
        "department": "Workplace & Transport",
        "icon": "car",
        "description": "Audits final month commute trips, cancels monthly ride allowance, and removes employee from corporate Uber account.",
        "stages": [
            "Revocation Request Sent to Transport",
            "Auditing Final Month Commute Usage",
            "Cancelling Monthly Commute Allowance",
            "Removing Employee from Corporate Uber Profile",
            "Uber Commute Pass Revoked",
        ],
        "depends_on": None,
        "applicable_roles": ["TRAINEE", "EMPLOYEE"],
    },
    TaskType.LAPTOP: {
        "agent_name": "Laptop Return & Asset Clearance Agent",
        "title": "Workstation & Equipment Recovery",
        "department": "IT Equipment",
        "icon": "laptop",
        "description": "Schedules physical device handover, inspects hardware condition, backs up work files, and wipes workstation.",
        "stages": [
            "Return Request Sent to IT Equipment",
            "Scheduling Laptop Handover Inspection",
            "Inspecting Physical Device Condition",
            "Backing Up & Wiping Company Data",
            "Laptop Returned to Inventory",
        ],
        "depends_on": None,
        "applicable_roles": ["TRAINEE", "EMPLOYEE"],
    },
    TaskType.EMAIL: {
        "agent_name": "IT Email & Access Deactivation Agent",
        "title": "Work Email & Single Sign-On Revocation",
        "department": "IT Support",
        "icon": "mail-x",
        "description": "Configures auto-reply forwarding, removes mailing list access, revokes Single Sign-On sessions, and archives mailbox.",
        "stages": [
            "Waiting for Asset & Benefit Clearance",
            "Setting Auto-Reply & Forwarding to Department Head",
            "Removing from Department Mailing Lists",
            "Revoking Single Sign-On & Cloud Sessions",
            "Work Email Deactivated & Archived",
        ],
        "depends_on": TaskType.LAPTOP,
        "applicable_roles": ["INTERN", "TRAINEE", "EMPLOYEE"],
    },
}


class EmployeeExitCreate(BaseModel):
    full_name: str = Field(..., min_length=2, example="Marcus Vance")
    personal_email: str = Field(..., example="marcus.vance@gmail.com")
    phone: str = Field(default="+1 (555) 390-4820")
    role_category: RoleCategory = Field(default=RoleCategory.EMPLOYEE)
    job_title: str = Field(..., example="Senior Product Designer")
    department: str = Field(..., example="Design & User Experience")
    manager_name: str = Field(..., example="Elena Rostova")
    location: str = Field(default="San Francisco, CA (Hybrid)")
    compensation_amount: float = Field(..., gt=0, example=148000.0)
    compensation_period: str = Field(default="per year")
    join_date: str = Field(default="2023-04-10", example="2023-04-10")
    notice_date: str = Field(default="2026-05-01", example="2026-05-01")
    last_working_day: Optional[str] = Field(default=None, example="2026-05-22")
    start_date: Optional[str] = Field(default=None, description="Alias for last_working_day")
    exit_type: str = Field(default="Voluntary Resignation")
    exit_reason: str = Field(default="Career progression & relocation")
    days_worked_final_month: int = Field(default=18, ge=0, le=31)
    unused_leave_days: float = Field(default=7.5, ge=0, le=60)
    asset_deduction: float = Field(default=0.0, ge=0)
    deduction_notes: Optional[str] = Field(default="All company equipment accounted for")
    assigned_laptop_serial: Optional[str] = Field(default=None)
    custom_notes: Optional[str] = None


# Alias for onboarding test/client compatibility
CandidateCreate = EmployeeExitCreate


class BatchExitCreate(BaseModel):
    employees: Optional[List[EmployeeExitCreate]] = None
    candidates: Optional[List[EmployeeExitCreate]] = None


BatchCandidateCreate = BatchExitCreate


class SignActionRequest(BaseModel):
    signature_name: Optional[str] = None
    forwarding_address: Optional[str] = None
    handover_confirmed: bool = True
    reason: Optional[str] = None


class TaskAdvanceRequest(BaseModel):
    notes: Optional[str] = None


class TaskBlockerRequest(BaseModel):
    blocker_reason: str = Field(..., min_length=3)


class SMTPConfigUpdate(BaseModel):
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    from_email: str = Field(default="people-exits@acme-enterprise.com")
    from_name: str = Field(default="Acme People Operations — Exit & Clearance Team")
    enabled: bool = Field(default=False)


class TemplateUpdate(BaseModel):
    company_name: str
    title: str
    intro_text: str
    terms_json: List[str]
    benefits_json: List[str]
    footer_text: str
