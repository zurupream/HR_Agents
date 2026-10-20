"""seed_data.py - Official Employee Handbook Knowledge Base & Sample HR Helpdesk Requests."""

from __future__ import annotations
from typing import Any, Dict, List, Optional

EMPLOYEE_HANDBOOK_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": "annual_maternity_leave",
        "title": "Annual & Maternity/Paternity Leave",
        "short_description": "Annual vacation days, maternity & paternity entitlements, sick leave, and leave carry-over rules.",
        "handbook_section": "Employee Handbook • Section 4.1 — Annual, Parental & Sick Leave",
        "policy_rule": (
            "All permanent and fixed-term employees earn 21 working days of paid Annual Leave per calendar year "
            "(accrued at 1.75 days per month). Female employees are entitled to 90 calendar days of fully paid "
            "Maternity Leave, and male employees are entitled to 14 calendar days of fully paid Paternity Leave. "
            "Up to 5 unused annual leave days may be carried forward to Q1 of the following year."
        ),
        "entitlements_at_a_glance": [
            {"label": "Annual Leave", "value": "21 Working Days / Year", "note": "Accrues at 1.75 days per month"},
            {"label": "Maternity Leave", "value": "90 Calendar Days", "note": "100% full pay • Annual leave still accrues"},
            {"label": "Paternity Leave", "value": "14 Calendar Days", "note": "100% full pay within 30 days of birth"},
            {"label": "Sick Leave", "value": "30 Days Full + 15 Half Pay", "note": "Doctor's note required after 2 consecutive days"},
            {"label": "Max Carry-Over", "value": "5 Working Days", "note": "Must be used by 31 March of the next year"},
        ],
        "steps_to_follow": [
            "Check your available leave balance on the Self-Service Portal or ask the HR Helpdesk Agent.",
            "Submit annual leave requests at least 5 working days in advance (14 days for leave longer than 5 days).",
            "For Maternity or Paternity Leave, attach the hospital notification or birth certificate at least 4 weeks before the expected date (or within 48 hours of delivery).",
            "Once your line manager approves, HR automatically updates your leave balance and payroll calendar.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' if you need to carry over more than 5 unused leave days, "
            "register official Maternity/Paternity dates, or correct your accrued leave balance."
        ),
        "suggested_request_subject": "Assistance with Leave Balance / Parental Leave Registration",
        "keywords": [
            "annual", "leave", "vacation", "holiday", "maternity", "paternity", "parental",
            "baby", "pregnancy", "sick", "illness", "doctor", "carry over", "carryover", "balance", "days off"
        ],
        "sample_questions": [
            {
                "q": "How many annual leave days do I get per year, and can I carry unused days to next year?",
                "a": (
                    "You receive **21 working days of paid Annual Leave** every calendar year (earned at 1.75 days per month). "
                    "You can automatically carry forward up to **5 unused working days** into the new year, provided you take them by **31 March**. "
                    "Any days above 5 require written approval from your Department Head and HR."
                ),
            },
            {
                "q": "What is the company policy for Maternity and Paternity Leave, and does it reduce my annual leave?",
                "a": (
                    "Maternity Leave is **90 calendar days at 100% full pay**, and Paternity Leave is **14 calendar days at 100% full pay**. "
                    "Taking Maternity or Paternity Leave **does not reduce your 21 days of Annual Leave**—your annual vacation days continue to accrue normally."
                ),
            },
            {
                "q": "How many paid sick leave days am I allowed, and when do I need a doctor's note?",
                "a": (
                    "After confirmation, you are covered for up to **30 working days of Sick Leave at full pay** followed by **15 working days at half pay** per year. "
                    "For a 1-day or 2-day mild illness, simply notify your manager before 9:00 AM. A medical certificate from a registered doctor is required for any absence of **3 or more consecutive days**."
                ),
            },
        ],
    },
    {
        "id": "medical_dental_insurance",
        "title": "Medical & Dental Insurance Cover",
        "short_description": "Inpatient & outpatient limits, dental & optical allowances, maternity cover, and adding dependents.",
        "handbook_section": "Employee Handbook • Section 5.2 — Staff Medical, Dental & Optical Insurance",
        "policy_rule": (
            "Every employee and their eligible dependents (1 legal spouse and up to 4 biological or legally adopted "
            "children under age 25) are covered from Day 1 under the Company Group Medical Scheme. Access at panel "
            "hospitals is cashless using your Smart Biometric Medical Card or mobile app."
        ),
        "entitlements_at_a_glance": [
            {"label": "Inpatient Cover", "value": "KES 2,500,000 / Family", "note": "Standard private en-suite bed at panel hospitals"},
            {"label": "Outpatient Cover", "value": "KES 250,000 / Family", "note": "100% cashless at appointed panel clinics"},
            {"label": "Dental Cover", "value": "KES 50,000 / Person", "note": "Covers fillings, root canal, extractions & scaling"},
            {"label": "Optical Cover", "value": "KES 50,000 / Person", "note": "Eye test + prescription lenses & frames (every 2 yrs)"},
            {"label": "Eligible Dependents", "value": "Spouse + Up to 4 Children", "note": "Newborns covered immediately upon HR notification"},
        ],
        "steps_to_follow": [
            "Present your Smart Medical Card (or registered National ID + biometric fingerprint) at any approved panel hospital or clinic.",
            "For Dental, Optical, or specialist diagnostics above KES 20,000, the clinic will request instant pre-authorization from the insurer.",
            "If you visit a non-panel doctor in an emergency, keep the ETIMS invoice, stamped receipt, and prescription, and submit a reimbursement request within 30 days.",
            "To add a new spouse or newborn child, click 'Send Request to HR Team' with a copy of the marriage certificate or birth notification.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' if you need to add a newborn or spouse to your medical card, "
            "request hospital pre-authorization support, or follow up on a medical reimbursement claim."
        ),
        "suggested_request_subject": "Add Dependent / Medical Insurance Card Assistance",
        "keywords": [
            "medical", "insurance", "dental", "optical", "glasses", "hospital", "clinic", "inpatient",
            "outpatient", "dependent", "spouse", "child", "newborn", "card", "smart card", "tooth", "eye", "health"
        ],
        "sample_questions": [
            {
                "q": "What are my annual limits for Inpatient, Outpatient, Dental, and Optical medical cover?",
                "a": (
                    "Your family Group Medical Cover provides **KES 2,500,000 Inpatient**, **KES 250,000 Outpatient**, **KES 50,000 Dental per member**, "
                    "and **KES 50,000 Optical per member** per policy year, plus **KES 150,000 Maternity delivery cover**."
                ),
            },
            {
                "q": "How do I add my newborn baby or spouse to the company medical insurance scheme?",
                "a": (
                    "You can cover **1 spouse and up to 4 children**. To enroll a newborn or spouse, click **Send Request to HR Team** and provide the "
                    "Birth Notification (for newborns) or Marriage Certificate / ID (for a spouse). HR activates cover within **24 working hours**."
                ),
            },
            {
                "q": "Can I buy prescription glasses under the Optical cover, and is there a co-pay?",
                "a": (
                    "Yes! Your **KES 50,000 Optical allowance** covers eye consultations, prescription lenses, and frames (frames capped at KES 20,000 every 2 years) "
                    "with **zero co-pay** at any panel optician."
                ),
            },
        ],
    },
    {
        "id": "payroll_payslip",
        "title": "Payroll Dates & Payslip Questions",
        "short_description": "Monthly salary payment date, payroll cut-off, statutory deductions (PAYE, NSSF, SHIF, Housing Levy), and P9 tax forms.",
        "handbook_section": "Employee Handbook • Section 3.1 — Monthly Payroll Schedule, Statutory Deductions & Payslips",
        "policy_rule": (
            "Monthly salaries are paid via bank transfer on or before the 25th day of every month. If the 25th falls on a "
            "Saturday, Sunday, or Public Holiday, salaries are credited on the preceding working Friday. All payroll changes "
            "(bank account updates, overtime, or allowances) must reach HR by the 15th of the month."
        ),
        "entitlements_at_a_glance": [
            {"label": "Salary Pay Date", "value": "25th of Every Month", "note": "Paid on preceding Friday if 25th is a weekend/holiday"},
            {"label": "Payroll Cut-Off Date", "value": "15th of Every Month", "note": "Deadline for bank account updates & variable allowances"},
            {"label": "NSSF Pension (Tier I & II)", "value": "6% Employee + 6% Employer", "note": "Capped at KES 4,320 employee / KES 4,320 employer"},
            {"label": "SHIF Health Deduction", "value": "2.75% of Gross Pay", "note": "Statutory Social Health Insurance Fund contribution"},
            {"label": "Affordable Housing Levy", "value": "1.5% of Gross Pay", "note": "Matched 1.5% by the employer (tax-deductible)"},
        ],
        "steps_to_follow": [
            "Encrypted PDF payslips are emailed automatically to your work email on the 24th of each month (password is your National ID / Passport number).",
            "To update your salary bank account, submit a signed bank instruction letter and cancelled cheque/account confirmation before the 15th of the month.",
            "Annual KRA P9 Tax Deduction Cards are issued by 28 February each year for annual tax filing.",
            "If you notice an unfamiliar deduction or need a stamped payslip for a bank loan, click 'Send Request to HR Team'.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' if you need a stamped payslip or employment confirmation letter for a bank, "
            "want to update your salary bank account before the 15th cut-off, or have a question on your net pay."
        ),
        "suggested_request_subject": "Payslip Breakdown / Bank Account Update / P9 Tax Card Request",
        "keywords": [
            "payroll", "salary", "payday", "pay date", "payslip", "tax", "paye", "nssf", "shif", "nhif",
            "housing levy", "p9", "bank account", "deduction", "net pay", "gross pay", "25th", "loan letter"
        ],
        "sample_questions": [
            {
                "q": "What date is salary paid each month, and what happens if the 25th falls on a weekend?",
                "a": (
                    "Salaries are credited to your bank account on the **25th of every month**. Whenever the 25th falls on a Saturday, Sunday, or Public Holiday, "
                    "payroll is released early so funds arrive on the **preceding working Friday**."
                ),
            },
            {
                "q": "How are statutory deductions (PAYE, NSSF, SHIF, and Housing Levy) calculated on my payslip?",
                "a": (
                    "Every monthly payslip reflects Kenyan statutory deductions calculated deterministically: **NSSF (6% up to KES 4,320)**, "
                    "**SHIF (2.75% of gross salary)**, and **Affordable Housing Levy (1.5% of gross salary)**. All three are tax-deductible before computing **PAYE**, "
                    "and **KES 2,400 Personal Relief** is automatically credited to reduce your PAYE tax."
                ),
            },
            {
                "q": "What is the deadline to change my salary bank account for this month's payroll?",
                "a": (
                    "The monthly payroll cut-off date is the **15th of each month**. Bank account changes submitted on or before the 15th take effect in the same month's salary; "
                    "changes submitted after the 15th take effect the following month."
                ),
            },
        ],
    },
    {
        "id": "transport_expense_claims",
        "title": "Transport & Expense Claims",
        "short_description": "Official mileage rates, late-night Uber/taxi transport, travel per diems, and weekly expense reimbursement.",
        "handbook_section": "Employee Handbook • Section 6.3 — Staff Transport, Travel Per Diems & Expense Reimbursements",
        "policy_rule": (
            "Employees incurring approved business expenses (client travel, official mileage, or late-evening office work "
            "past 8:00 PM) are reimbursed 100% every Friday. Claims must be submitted within 7 working days of the expense "
            "accompanied by a valid ETIMS tax invoice or corporate transport receipt."
        ),
        "entitlements_at_a_glance": [
            {"label": "Personal Car Mileage", "value": "KES 65 per km", "note": "For pre-approved client or field visits"},
            {"label": "Late-Evening Taxi / Uber", "value": "Up to KES 2,500 / Trip", "note": "Available when working at the office past 8:00 PM"},
            {"label": "Domestic Per Diem", "value": "KES 8,500 – 14,000 / Night", "note": "Covers meals & incidentals outside home station"},
            {"label": "Claim Submission Window", "value": "Within 7 Working Days", "note": "Requires valid ETIMS invoice or digital receipt"},
            {"label": "Reimbursement Payout", "value": "Every Friday", "note": "For claims approved by line manager by Wednesday 5 PM"},
        ],
        "steps_to_follow": [
            "Obtain line manager approval before booking out-of-town travel or incurring client hospitality expenses.",
            "Keep the digital Uber receipt or ETIMS-compliant invoice showing the merchant PIN and date.",
            "Submit your claim within 7 working days. Claims approved by Wednesday at 5:00 PM are paid in Friday's weekly reimbursement run.",
            "If your reimbursement is delayed or you need corporate Uber business profile activation, click 'Send Request to HR Team'.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' if you need access to the corporate Uber Commute profile, "
            "travel advance approval, or status on a submitted expense claim."
        ),
        "suggested_request_subject": "Expense Reimbursement Follow-Up / Corporate Uber Access",
        "keywords": [
            "transport", "expense", "reimbursement", "claim", "uber", "taxi", "mileage", "fuel",
            "per diem", "travel", "receipt", "etims", "allowance", "late", "cab"
        ],
        "sample_questions": [
            {
                "q": "When are approved staff expense claims paid out, and what documents are required?",
                "a": (
                    "Approved expense claims are paid **every Friday** via direct bank transfer (separate from monthly payroll). "
                    "Submit your claim within **7 working days** of the expense with a valid **ETIMS receipt or Uber digital invoice**; "
                    "claims approved by your manager by **Wednesday 5:00 PM** are paid that same Friday."
                ),
            },
            {
                "q": "Can I claim a taxi or Uber home if I work late at the office?",
                "a": (
                    "Yes. If approved official duties require you to work at the office past **8:00 PM**, you can use the **Corporate Uber Business Profile** "
                    "or claim safe door-to-door taxi reimbursement of up to **KES 2,500 per trip**."
                ),
            },
            {
                "q": "What is the reimbursement rate when I use my personal car for official client visits?",
                "a": (
                    "Approved business travel using your personal vehicle is reimbursed at **KES 65 per kilometre**, which covers fuel and wear-and-tear. "
                    "Simply log the starting point, client destination, and total kilometres in your expense claim."
                ),
            },
        ],
    },
    {
        "id": "working_hours_remote",
        "title": "Working Hours & Remote Work",
        "short_description": "Standard office hours, hybrid remote work days (up to 2 days/week), core availability hours, and dress code.",
        "handbook_section": "Employee Handbook • Section 2.4 — Standard Working Hours, Hybrid Remote Work & Flexibility",
        "policy_rule": (
            "Standard working hours are Monday to Friday, 8:30 AM to 5:00 PM (40 hours per week), including a 1-hour "
            "lunch break between 12:30 PM and 2:30 PM. Eligible roles may work remotely up to 2 days per week under the "
            "Hybrid Work Policy, provided core collaboration hours (9:30 AM – 4:00 PM) are maintained."
        ),
        "entitlements_at_a_glance": [
            {"label": "Standard Office Hours", "value": "8:30 AM – 5:00 PM", "note": "Monday to Friday (40-hour workweek)"},
            {"label": "Daily Lunch Break", "value": "1 Hour", "note": "Flexible between 12:30 PM and 2:30 PM"},
            {"label": "Hybrid Remote Work", "value": "Up to 2 Days / Week", "note": "Notify line manager by 4:00 PM the previous day"},
            {"label": "Core Online Hours", "value": "9:30 AM – 4:00 PM", "note": "Reachable on Slack/Teams & Google Meet"},
            {"label": "Office Dress Code", "value": "Smart Business Casual", "note": "Formal attire required for external client meetings"},
        ],
        "steps_to_follow": [
            "Agree your weekly remote work days (up to 2 days per week) with your line manager and mark 'Working Remotely' on your Google Calendar.",
            "Ensure stable internet connectivity and stay reachable on team channels during Core Hours (9:30 AM – 4:00 PM).",
            "If you need temporary full-time remote work due to family caregiving or medical recovery, submit a short request to HR.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' if you need a temporary extended remote-work arrangement "
            "or ergonomic home-office equipment support."
        ),
        "suggested_request_subject": "Flexible / Extended Remote Work Arrangement Request",
        "keywords": [
            "working hours", "remote", "work from home", "wfh", "hybrid", "flexible", "hours",
            "lunch", "schedule", "dress code", "office hours", "time", "start time"
        ],
        "sample_questions": [
            {
                "q": "How many days per week can I work from home under the Hybrid Work Policy?",
                "a": (
                    "Eligible employees can work remotely for **up to 2 days per week**. Just confirm your planned remote days with your line manager "
                    "by **4:00 PM the day before** and remain online during **Core Hours (9:30 AM – 4:00 PM)**."
                ),
            },
            {
                "q": "What are the official office working hours and lunch break times?",
                "a": (
                    "Standard working hours are **Monday to Friday, 8:30 AM to 5:00 PM**, with a **1-hour lunch break** taken flexibly between 12:30 PM and 2:30 PM."
                ),
            },
        ],
    },
    {
        "id": "public_holidays_compassionate",
        "title": "Public Holidays & Compassionate Leave",
        "short_description": "Gazetted national public holidays, paid bereavement/compassionate leave, and professional exam study leave.",
        "handbook_section": "Employee Handbook • Section 4.4 — Public Holidays, Compassionate Leave & Exam Study Leave",
        "policy_rule": (
            "The Company observes all gazetted Public Holidays. When a Public Holiday falls on a Sunday, the following "
            "Monday is observed as an official holiday. Employees are also entitled to up to 5 working days of paid "
            "Compassionate Leave for bereavement of an immediate family member, and up to 5 working days of Study Leave "
            "per year for approved professional certification exams."
        ),
        "entitlements_at_a_glance": [
            {"label": "Public Holidays", "value": "All Gazetted Holidays", "note": "100% paid • Compensatory day off if on shift duty"},
            {"label": "Compassionate Leave", "value": "5 Working Days (Paid)", "note": "For immediate family bereavement (spouse, child, parent, sibling)"},
            {"label": "Study & Exam Leave", "value": "5 Working Days / Year", "note": "For approved CPA,acca, CIPD, Engineering or IT exams"},
            {"label": "Holiday Shift Compensation", "value": "1 Lieu Day + Overtime", "note": "For essential support staff scheduled on a public holiday"},
        ],
        "steps_to_follow": [
            "For Compassionate Leave, simply message or call your line manager or HR—urgent bereavement leave is approved immediately.",
            "For Study & Exam Leave, submit your exam timetable at least 10 working days before the examination date.",
            "If your role requires working on a gazetted Public Holiday, your manager will log a compensatory day off (Day-in-Lieu) automatically.",
        ],
        "when_to_contact_hr": (
            "Click 'Send Request to HR Team' to notify HR of Compassionate Leave, request Study & Exam Leave approval, "
            "or claim a compensatory day off after working on a Public Holiday."
        ),
        "suggested_request_subject": "Compassionate Leave / Exam Study Leave Notification",
        "keywords": [
            "public holiday", "compassionate", "bereavement", "funeral", "family", "death",
            "study leave", "exam", "holiday", "lieu", "gazetted", "christmas", "easter", "eid", "madaraka", "mashujaa", "jamhuri"
        ],
        "sample_questions": [
            {
                "q": "How many days of paid Compassionate Leave am I given if I lose a close family member?",
                "a": (
                    "You are entitled to **up to 5 paid working days of Compassionate Leave** in the event of the loss of an immediate family member "
                    "(spouse, child, parent, parent-in-law, or sibling). These days are completely separate from your Annual Leave."
                ),
            },
            {
                "q": "Does the company provide paid Study Leave when I am sitting for professional exams?",
                "a": (
                    "Yes! Permanent staff sitting for approved professional certifications (such as CPA, ACCA, SHRM/CHRP, Cloud, or Engineering boards) "
                    "receive up to **5 paid working days of Study & Exam Leave per calendar year**. Submit your exam timetable at least 10 days in advance."
                ),
            },
        ],
    },
]


INITIAL_HELPDESK_REQUESTS: List[Dict[str, Any]] = [
    {
        "request_id": "HR-2026-1041",
        "created_at": "2026-10-20 08:45 EAT",
        "employee_name": "Grace Wanjiku",
        "employee_email": "grace.wanjiku@sybyl.com",
        "department": "Customer Success & Support",
        "category_id": "medical_dental_insurance",
        "category_title": "Medical & Dental Insurance Cover",
        "subject": "Add newborn daughter to Group Medical Insurance cover",
        "details": "Hello HR Team, we welcomed our daughter at Nairobi Hospital yesterday. Kindly add her to my family medical cover using Birth Notification #BN-884120.",
        "handbook_reference": "Section 5.2 — Staff Medical, Dental & Optical Insurance",
        "status": "In Progress",
        "hr_owner": "People Services Desk",
        "hr_response": "Congratulations Grace! We have forwarded Birth Notification #BN-884120 to AAR Insurance; your newborn's smart card profile will be active by 2:00 PM today.",
    },
    {
        "request_id": "HR-2026-1042",
        "created_at": "2026-10-19 16:10 EAT",
        "employee_name": "David Ochieng",
        "employee_email": "david.ochieng@sybyl.com",
        "department": "Cloud Infrastructure & IT",
        "category_id": "payroll_payslip",
        "category_title": "Payroll Dates & Payslip Questions",
        "subject": "Request for stamped 3-month payslips & employment confirmation letter",
        "details": "Hi HR, I am applying for a personal asset finance facility with Stanbic Bank and need stamped copies of my last 3 payslips plus an employment confirmation letter.",
        "handbook_reference": "Section 3.1 — Monthly Payroll Schedule, Statutory Deductions & Payslips",
        "status": "Resolved",
        "hr_owner": "Payroll & Benefits Specialist",
        "hr_response": "Signed employment letter and stamped July–September payslips have been emailed to david.ochieng@sybyl.com.",
    },
    {
        "request_id": "HR-2026-1043",
        "created_at": "2026-10-20 09:15 EAT",
        "employee_name": "Amina Hassan",
        "employee_email": "amina.hassan@sybyl.com",
        "department": "Finance & Operations",
        "category_id": "public_holidays_compassionate",
        "category_title": "Public Holidays & Compassionate Leave",
        "subject": "5-Day Study Leave approval for CPA Section 5 exams in November",
        "details": "Attached is my KASNEB examination timetable for 24–28 November. Requesting 5 paid Study & Exam Leave days per Section 4.4 of the Employee Handbook.",
        "handbook_reference": "Section 4.4 — Public Holidays, Compassionate Leave & Exam Study Leave",
        "status": "Open",
        "hr_owner": "People Services Desk",
        "hr_response": "Awaiting HR verification of attached KASNEB exam timetable.",
    },
    {
        "request_id": "HR-2026-1044",
        "created_at": "2026-10-18 11:30 EAT",
        "employee_name": "Kelvin Mutua",
        "employee_email": "kelvin.mutua@sybyl.com",
        "department": "Enterprise Sales",
        "category_id": "transport_expense_claims",
        "category_title": "Transport & Expense Claims",
        "subject": "Mileage reimbursement for Nakuru client implementation visit (320 km)",
        "details": "Completed two-day client rollout in Nakuru (320 km round trip in personal vehicle @ KES 65/km = KES 20,800). Manager approved on Tuesday; checking Friday payout schedule.",
        "handbook_reference": "Section 6.3 — Staff Transport, Travel Per Diems & Expense Reimbursements",
        "status": "Resolved",
        "hr_owner": "HR & Finance Reimbursements",
        "hr_response": "Verified 320 km x KES 65/km = KES 20,800. Scheduled for this Friday's weekly reimbursement transfer.",
    },
]


def get_handbook_categories() -> List[Dict[str, Any]]:
    return [dict(c) for c in EMPLOYEE_HANDBOOK_CATEGORIES]


def get_handbook_category_by_id(category_id: str) -> Optional[Dict[str, Any]]:
    clean = (category_id or "").strip().lower()
    for cat in EMPLOYEE_HANDBOOK_CATEGORIES:
        if cat["id"].lower() == clean:
            return dict(cat)
    return None


def get_initial_helpdesk_requests() -> List[Dict[str, Any]]:
    return [dict(r) for r in INITIAL_HELPDESK_REQUESTS]


def match_handbook_category(question: str, category_id: Optional[str] = None) -> Dict[str, Any]:
    if category_id:
        found = get_handbook_category_by_id(category_id)
        if found:
            return found

    q_lower = (question or "").strip().lower()
    best_cat = EMPLOYEE_HANDBOOK_CATEGORIES[0]
    best_score = -1

    for cat in EMPLOYEE_HANDBOOK_CATEGORIES:
        score = 0
        for kw in cat["keywords"]:
            if kw in q_lower:
                score += 3 if " " in kw else 2
        if cat["title"].lower() in q_lower:
            score += 5
        if score > best_score:
            best_score = score
            best_cat = cat

    return dict(best_cat)


def answer_hr_question(question: str, category_id: Optional[str] = None) -> Dict[str, Any]:
    clean_q = (question or "").strip()
    cat = match_handbook_category(clean_q, category_id)

    # Check if the question closely matches one of the sample questions in the category
    matched_sample_answer = None
    q_lower = clean_q.lower()
    best_overlap = 0
    q_words = {w.strip("?,!.") for w in q_lower.split() if len(w.strip("?,!.")) > 2}

    for sq in cat.get("sample_questions", []):
        sq_words = {w.strip("?,!.") for w in sq["q"].lower().split() if len(w.strip("?,!.")) > 2}
        overlap = len(q_words & sq_words)
        if overlap > best_overlap:
            best_overlap = overlap
            matched_sample_answer = sq["a"]

    if matched_sample_answer and best_overlap >= 2:
        plain_answer = matched_sample_answer
    else:
        plain_answer = (
            f"According to **{cat['handbook_section']}**, {cat['policy_rule']}"
        )

    return {
        "question": clean_q or f"Tell me about {cat['title']}",
        "category_id": cat["id"],
        "category_title": cat["title"],
        "handbook_section": cat["handbook_section"],
        "plain_english_answer": plain_answer,
        "policy_rule": cat["policy_rule"],
        "entitlements_at_a_glance": cat["entitlements_at_a_glance"],
        "steps_to_follow": cat["steps_to_follow"],
        "when_to_contact_hr": cat["when_to_contact_hr"],
        "suggested_request_subject": cat["suggested_request_subject"],
    }
