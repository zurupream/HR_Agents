"""Rich Non-IT demo data seeder for the Sybyl People HR Onboarding Application."""

from datetime import datetime, timedelta, timezone
from app.agents import OfferESignAgent, OnboardingOrchestrator
from app.database import get_conn, init_db, utc_now_iso
from app.models import BatchOnboardingRequest, CandidateOfferInput, RoleCategory


def seed_demo_data(force_reset: bool = False, base_url: str = "http://localhost:8080") -> None:
    init_db()
    conn = get_conn()
    existing_count = conn.execute("SELECT COUNT(*) as cnt FROM positions").fetchone()["cnt"]
    legacy_it_pos = conn.execute(
        "SELECT COUNT(*) as cnt FROM positions WHERE id = 'pos-eng-ai'"
    ).fetchone()["cnt"]
    if existing_count > 0 and not force_reset and legacy_it_pos == 0:
        conn.close()
        return

    if force_reset or legacy_it_pos > 0:
        conn.executescript(
            """
            DELETE FROM agent_audit_events;
            DELETE FROM notification_logs;
            DELETE FROM provisioning_tasks;
            DELETE FROM offer_letters;
            DELETE FROM candidates;
            DELETE FROM positions;
            """
        )
        conn.commit()

    # Temporarily pause live SMTP while seeding demo candidates
    conn.execute("UPDATE smtp_settings SET live_mode_enabled = 0 WHERE id = 1")
    conn.commit()

    now = utc_now_iso()
    positions = [
        (
            "pos-sales-mgr",
            "Sales Manager",
            "Commercial & Retail Sales",
            "Rachel Adams",
            "rachel.adams@sybyl.com",
            3,
            "Regional Head Office",
            "OPEN",
            now,
        ),
        (
            "pos-merch",
            "Merchandiser",
            "Retail & Category Merchandising",
            "Daniel Okafor",
            "daniel.okafor@sybyl.com",
            2,
            "Retail Operations Center",
            "OPEN",
            now,
        ),
        (
            "pos-proc-off",
            "Procurement Officer",
            "Supply Chain & Vendor Management",
            "Tariq Mansoor",
            "tariq.mansoor@sybyl.com",
            2,
            "Corporate Head Office",
            "OPEN",
            now,
        ),
        (
            "pos-fin-off",
            "Finance Officer",
            "Corporate Finance & Accounting",
            "Claire Bennett",
            "claire.bennett@sybyl.com",
            2,
            "Corporate Head Office",
            "OPEN",
            now,
        ),
    ]

    conn.executemany(
        """
        INSERT INTO positions (
            id, title, department, hod_name, hod_email,
            headcount_target, location, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        positions,
    )
    conn.commit()
    conn.close()

    # Dispatch initial batch of 7 candidates across Non-IT positions
    batch_req = BatchOnboardingRequest(
        batch_name="Q4 Commercial & Operations Hiring",
        hr_email="hr@sybyl.com",
        ceo_email="ceo@sybyl.com",
        cc_emails="hr@sybyl.com; ceo@sybyl.com",
        candidates=[
            CandidateOfferInput(
                full_name="Aarav Mehta",
                personal_email="aarav.mehta@example.com",
                phone="+1-415-890-2311",
                position_id="pos-sales-mgr",
                role_category=RoleCategory.EMPLOYEE,
                compensation="$115,000 / yr + Sales Commission",
                joining_date="2026-10-26",
                offer_valid_hours=72,
            ),
            CandidateOfferInput(
                full_name="Sophia Chen",
                personal_email="sophia.chen@example.com",
                phone="+1-415-890-4419",
                position_id="pos-proc-off",
                role_category=RoleCategory.EMPLOYEE,
                compensation="$95,000 / yr + Annual Bonus",
                joining_date="2026-10-20",
                offer_valid_hours=72,
            ),
            CandidateOfferInput(
                full_name="Liam O'Connor",
                personal_email="liam.oconnor@example.com",
                phone="+1-212-555-0143",
                position_id="pos-merch",
                role_category=RoleCategory.TRAINEE,
                compensation="$62,000 / yr (Merchandising Trainee)",
                joining_date="2026-10-22",
                offer_valid_hours=72,
            ),
            CandidateOfferInput(
                full_name="Maya Lin",
                personal_email="maya.lin@example.com",
                phone="+1-650-555-0188",
                position_id="pos-fin-off",
                role_category=RoleCategory.INTERN,
                compensation="$2,800 / month Stipend",
                joining_date="2026-10-21",
                offer_valid_hours=72,
            ),
            CandidateOfferInput(
                full_name="Noah Williams",
                personal_email="noah.williams@example.com",
                phone="+1-212-555-0192",
                position_id="pos-merch",
                role_category=RoleCategory.TRAINEE,
                compensation="$62,000 / yr (Merchandising Trainee)",
                joining_date="2026-10-28",
                offer_valid_hours=9,  # Expiring soon (< 24h) for HR Action Center
            ),
            CandidateOfferInput(
                full_name="Chloe Dubois",
                personal_email="chloe.dubois@example.com",
                phone="+1-512-555-0174",
                position_id="pos-sales-mgr",
                role_category=RoleCategory.EMPLOYEE,
                compensation="$110,000 / yr + Sales Commission",
                joining_date="2026-10-27",
                offer_valid_hours=72,
            ),
            CandidateOfferInput(
                full_name="Ethan Brooks",
                personal_email="ethan.brooks@example.com",
                phone="+1-650-555-0120",
                position_id="pos-fin-off",
                role_category=RoleCategory.INTERN,
                compensation="$2,800 / month Stipend",
                joining_date="2026-10-25",
                offer_valid_hours=48,
            ),
        ],
    )

    result = OfferESignAgent.create_batch_offers(batch_req, base_url=base_url)
    offers_by_name = {o["full_name"]: o for o in result["offers"]}

    # 1. Aarav Mehta (Sales Manager - EMPLOYEE) -> Accepted + All 4 onboarding items COMPLETED
    aarav = offers_by_name["Aarav Mehta"]
    OfferESignAgent.accept_offer(
        signing_token=aarav["signing_token"],
        signer_name="Aarav Mehta",
        signature_type="drawn",
        comments="Delighted to join the Commercial & Retail Sales team!",
    )
    OnboardingOrchestrator.run_all_subagents_for_candidate(aarav["candidate_id"])

    # 2. Sophia Chen (Procurement Officer - EMPLOYEE) -> Accepted + EMAIL completed, LAPTOP & UBER in progress, INSURANCE delayed
    sophia = offers_by_name["Sophia Chen"]
    OfferESignAgent.accept_offer(
        signing_token=sophia["signing_token"],
        signer_name="Sophia Chen",
        signature_type="typed",
        comments="Looking forward to joining the Procurement team on Oct 20.",
    )
    conn = get_conn()
    sophia_tasks = {
        r["task_type"]: r["id"]
        for r in conn.execute(
            "SELECT id, task_type FROM provisioning_tasks WHERE candidate_id = ?",
            (sophia["candidate_id"],),
        ).fetchall()
    }
    conn.close()
    OnboardingOrchestrator.advance_task_stage(sophia_tasks["EMAIL"], complete_immediately=True)
    OnboardingOrchestrator.advance_task_stage(sophia_tasks["LAPTOP"])
    OnboardingOrchestrator.advance_task_stage(sophia_tasks["LAPTOP"])
    OnboardingOrchestrator.advance_task_stage(sophia_tasks["UBER"])
    OnboardingOrchestrator.simulate_task_blocker(
        sophia_tasks["INSURANCE"],
        "Waiting for family member details from candidate to complete health insurance registration",
    )

    # 3. Liam O'Connor (Merchandiser - TRAINEE) -> Accepted + EMAIL completed, LAPTOP completed, UBER at stage 3/5
    liam = offers_by_name["Liam O'Connor"]
    OfferESignAgent.accept_offer(
        signing_token=liam["signing_token"],
        signer_name="Liam O'Connor",
        signature_type="drawn",
    )
    conn = get_conn()
    liam_tasks = {
        r["task_type"]: r["id"]
        for r in conn.execute(
            "SELECT id, task_type FROM provisioning_tasks WHERE candidate_id = ?",
            (liam["candidate_id"],),
        ).fetchall()
    }
    conn.close()
    OnboardingOrchestrator.advance_task_stage(liam_tasks["EMAIL"], complete_immediately=True)
    OnboardingOrchestrator.advance_task_stage(liam_tasks["LAPTOP"], complete_immediately=True)
    OnboardingOrchestrator.advance_task_stage(liam_tasks["UBER"])
    OnboardingOrchestrator.advance_task_stage(liam_tasks["UBER"])

    # 4. Maya Lin (Finance Officer - INTERN) -> Accepted + Only EMAIL required -> Completed!
    maya = offers_by_name["Maya Lin"]
    OfferESignAgent.accept_offer(
        signing_token=maya["signing_token"],
        signer_name="Maya Lin",
        signature_type="typed",
    )
    OnboardingOrchestrator.run_all_subagents_for_candidate(maya["candidate_id"])

    # 5. Noah Williams (Merchandiser - TRAINEE) -> Offer SENT & VIEWED, expiring in 9 hours
    noah = offers_by_name["Noah Williams"]
    conn = get_conn()
    conn.execute(
        "UPDATE offer_letters SET status = 'VIEWED', viewed_at = ? WHERE signing_token = ?",
        (utc_now_iso(), noah["signing_token"]),
    )
    conn.commit()
    conn.close()

    # 6. Chloe Dubois (Sales Manager - EMPLOYEE) -> Offer DECLINED
    chloe = offers_by_name["Chloe Dubois"]
    OfferESignAgent.decline_offer(
        signing_token=chloe["signing_token"],
        decline_reason="Accepted a Regional Sales Director role closer to home",
        comments="Thank you to Rachel Adams and the Sybyl team for the wonderful interview process.",
    )

    # 7. Ethan Brooks (Finance Officer - INTERN) -> Offer LAPSED
    ethan = offers_by_name["Ethan Brooks"]
    past_expiry = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_conn()
    conn.execute(
        "UPDATE offer_letters SET expires_at = ? WHERE candidate_id = ?",
        (past_expiry, ethan["candidate_id"]),
    )
    conn.commit()
    conn.close()
    OfferESignAgent.lapse_offer(
        ethan["candidate_id"],
        reason="Offer validity window expired (48h elapsed without candidate signature)",
    )

    # Ensure live SMTP with psrmreports@sybyl.com is active after demo seed completes
    conn = get_conn()
    conn.execute(
        """
        UPDATE smtp_settings
        SET sender_email = 'psrmreports@sybyl.com',
            app_password = CASE WHEN app_password = '' OR app_password IS NULL THEN 'kfbx btjf hcfk rwyb' ELSE app_password END,
            smtp_host = 'smtp.gmail.com',
            smtp_port = 587,
            use_tls = 1,
            live_mode_enabled = 1,
            default_cc_emails = COALESCE(NULLIF(default_cc_emails, ''), 'hr@sybyl.com; ceo@sybyl.com'),
            updated_at = ?
        WHERE id = 1
        """,
        (utc_now_iso(),),
    )
    conn.commit()
    conn.close()

