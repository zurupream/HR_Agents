"""Demo seed data for HR Offboarding Pro across Interns, Trainees, and Full-Time Employees."""

from .agents import ClearanceESignAgent, OffboardingOrchestrator
from .database import get_db
from .models import EmployeeExitCreate, RoleCategory


def seed_demo_data_if_empty():
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM candidates").fetchone()["c"]
        if count > 0:
            return

    # 1. Full-Time Employee — 100% Offboarded & Certificate of Service Issued
    emp1 = ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Dr. Aris Thorne",
            personal_email="aris.thorne@stanford-alumni.org",
            phone="+1 (415) 891-2240",
            role_category=RoleCategory.EMPLOYEE,
            job_title="Principal AI Research Scientist",
            department="AI Platform & Core ML",
            manager_name="Elena Rostova",
            location="San Francisco, CA (HQ)",
            compensation_amount=215000.0,
            compensation_period="per year",
            join_date="2022-02-14",
            notice_date="2026-04-15",
            last_working_day="2026-05-15",
            exit_type="Voluntary Resignation",
            exit_reason="Joining academic research fellowship",
            days_worked_final_month=11,
            unused_leave_days=7.0,
            asset_deduction=0.0,
            deduction_notes="MacBook Pro 16-inch & security key returned in mint condition",
            assigned_laptop_serial="MBP16-ACME-4012",
            custom_notes="All patent disclosures and model weight handovers verified by VP of Engineering.",
        )
    )
    ClearanceESignAgent.accept_clearance(
        emp1["offer"]["signing_token"],
        "Dr. Aris Thorne",
        forwarding_address="aris.thorne@stanford-alumni.org",
    )
    emp1_detail = OffboardingOrchestrator.get_candidate_detail(emp1["id"])
    for t in emp1_detail["tasks"]:
        if t["task_type"] != "EMAIL":
            for _ in range(5):
                OffboardingOrchestrator.advance_task_stage(t["id"])
    emp1_detail = OffboardingOrchestrator.get_candidate_detail(emp1["id"])
    for t in emp1_detail["tasks"]:
        if t["task_type"] == "EMAIL":
            for _ in range(5):
                OffboardingOrchestrator.advance_task_stage(t["id"])

    # 2. Full-Time Employee — Clearance Signed, Benefits & Uber Revoked, Laptop Wipe in Progress
    emp2 = ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Sophia Martinez",
            personal_email="sophia.martinez@gmail.com",
            phone="+1 (650) 442-9811",
            role_category=RoleCategory.EMPLOYEE,
            job_title="Senior Product Marketing Manager",
            department="Global Growth & Brand",
            manager_name="Marcus Sterling",
            location="New York, NY (Hybrid)",
            compensation_amount=156000.0,
            compensation_period="per year",
            join_date="2023-06-01",
            notice_date="2026-05-01",
            last_working_day="2026-05-22",
            exit_type="Voluntary Resignation",
            exit_reason="Relocation to Austin, TX",
            days_worked_final_month=16,
            unused_leave_days=5.5,
            asset_deduction=0.0,
            deduction_notes="All equipment scheduled for IT drop-off",
            assigned_laptop_serial="MBP14-ACME-4088",
            custom_notes="Q2 launch playbook handed over to Product Marketing lead.",
        )
    )
    ClearanceESignAgent.accept_clearance(
        emp2["offer"]["signing_token"],
        "Sophia Martinez",
        forwarding_address="sophia.martinez@gmail.com",
    )
    emp2_detail = OffboardingOrchestrator.get_candidate_detail(emp2["id"])
    for t in emp2_detail["tasks"]:
        if t["task_type"] in ("INSURANCE", "UBER"):
            for _ in range(5):
                OffboardingOrchestrator.advance_task_stage(t["id"])
        elif t["task_type"] == "LAPTOP":
            OffboardingOrchestrator.advance_task_stage(t["id"])
            OffboardingOrchestrator.advance_task_stage(t["id"])

    # 3. Graduate Trainee — Active IT Equipment Blocker (Missing Charger & Badge)
    emp3 = ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Liam O'Connor",
            personal_email="liam.oconnor@outlook.com",
            phone="+1 (312) 774-5190",
            role_category=RoleCategory.TRAINEE,
            job_title="Rotational Operations Trainee",
            department="Supply Chain & Logistics",
            manager_name="Priya Nair",
            location="Chicago, IL (On-Site)",
            compensation_amount=78000.0,
            compensation_period="per year",
            join_date="2025-06-15",
            notice_date="2026-05-04",
            last_working_day="2026-05-25",
            exit_type="End of Rotational Contract",
            exit_reason="Completion of 12-month graduate rotational program",
            days_worked_final_month=17,
            unused_leave_days=4.0,
            asset_deduction=79.0,
            deduction_notes="Pending 96W USB-C Power Adapter replacement ($79.00)",
            assigned_laptop_serial="MBP14-ACME-4155",
            custom_notes="Eligible for re-hire in Q4 Supply Chain Analyst cohort.",
        )
    )
    ClearanceESignAgent.accept_clearance(
        emp3["offer"]["signing_token"],
        "Liam O'Connor",
        forwarding_address="liam.oconnor@outlook.com",
    )
    emp3_detail = OffboardingOrchestrator.get_candidate_detail(emp3["id"])
    for t in emp3_detail["tasks"]:
        if t["task_type"] == "UBER":
            for _ in range(5):
                OffboardingOrchestrator.advance_task_stage(t["id"])
        elif t["task_type"] == "LAPTOP":
            OffboardingOrchestrator.advance_task_stage(t["id"])
            OffboardingOrchestrator.flag_task_blocker(
                t["id"],
                "Returned MacBook Pro 14-inch is missing its 96W USB-C power adapter and building access badge — awaiting physical return or HR deduction sign-off.",
            )

    # 4. Intern — Internship Completion, IT Email Deactivation In Progress
    emp4 = ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Chloe Takahashi",
            personal_email="chloe.takahashi@berkeley.edu",
            phone="+1 (510) 602-3319",
            role_category=RoleCategory.INTERN,
            job_title="UX Research Intern",
            department="Design & User Experience",
            manager_name="Hannah Abbott",
            location="San Francisco, CA (Hybrid)",
            compensation_amount=5200.0,
            compensation_period="per month",
            join_date="2026-01-12",
            notice_date="2026-05-05",
            last_working_day="2026-05-29",
            exit_type="End of Internship Term",
            exit_reason="Returning to UC Berkeley for final semester",
            days_worked_final_month=20,
            unused_leave_days=2.0,
            asset_deduction=0.0,
            deduction_notes="No physical laptop issued (cloud VDI workstation)",
            custom_notes="Strong recommendation for 2027 Graduate Trainee intake.",
        )
    )
    ClearanceESignAgent.mark_viewed(emp4["offer"]["signing_token"])
    emp4_detail = OffboardingOrchestrator.get_candidate_detail(emp4["id"])
    for t in emp4_detail["tasks"]:
        if t["task_type"] == "EMAIL":
            OffboardingOrchestrator.advance_task_stage(t["id"])

    # 5. Full-Time Employee — Final Settlement Query / Dispute Raised (Needs HR Attention)
    emp5 = ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Devon Brooks",
            personal_email="devon.brooks@proton.me",
            phone="+1 (206) 914-8821",
            role_category=RoleCategory.EMPLOYEE,
            job_title="Staff Cloud Security Architect",
            department="Infrastructure & Security",
            manager_name="Vikram Desai",
            location="Seattle, WA (Remote)",
            compensation_amount=192000.0,
            compensation_period="per year",
            join_date="2021-09-20",
            notice_date="2026-05-02",
            last_working_day="2026-05-26",
            exit_type="Voluntary Resignation",
            exit_reason="Transitioning to cybersecurity advisory role",
            days_worked_final_month=18,
            unused_leave_days=7.0,
            asset_deduction=0.0,
            deduction_notes="All hardware verified",
            assigned_laptop_serial="MBP16-ACME-3904",
        )
    )
    ClearanceESignAgent.dispute_clearance(
        emp5["offer"]["signing_token"],
        "My accrued unused vacation balance should be 11.5 days rather than 7.0 days after Q1 carryover approval from Vikram Desai.",
    )

    # 6. Graduate Trainee — Fresh Exit Notice Sent (Awaiting Employee E-Signature)
    ClearanceESignAgent.create_employee_exit_and_send_clearance(
        EmployeeExitCreate(
            full_name="Nadia Al-Mansoor",
            personal_email="nadia.almansoor@nyu.edu",
            phone="+1 (212) 509-7430",
            role_category=RoleCategory.TRAINEE,
            job_title="Finance & Treasury Graduate Trainee",
            department="Corporate Finance",
            manager_name="claire.dupont@acme.com",
            location="New York, NY (HQ)",
            compensation_amount=84000.0,
            compensation_period="per year",
            join_date="2025-07-01",
            notice_date="2026-05-10",
            last_working_day="2026-05-31",
            exit_type="Voluntary Resignation",
            exit_reason="Enrolling in full-time MBA program",
            days_worked_final_month=21,
            unused_leave_days=5.0,
            asset_deduction=0.0,
            deduction_notes="Standard corporate laptop handover scheduled",
            assigned_laptop_serial="MBP14-ACME-4209",
        )
    )
