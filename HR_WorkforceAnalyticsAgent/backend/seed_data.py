"""seed_data.py - Deterministic Workforce KPI Aggregation & Budget/Attrition What-If Simulator."""

from __future__ import annotations
from copy import deepcopy
from typing import Any, Dict, List


INITIAL_DEPARTMENTS: List[Dict[str, Any]] = [
    {
        "id": "dept-eng",
        "name": "Engineering",
        "head_of_department": "Elena Rostova (VP of Engineering)",
        "headcount": 145,
        "open_roles": 12,
        "annual_departures": 20,
        "turnover_pct": 13.8,
        "regrettable_departures": 9,
        "avg_time_to_hire_days": 42,
        "avg_tenure_years": 2.8,
        "retention_status": "Watch Closely",
        "monthly_cost": 1160000,
        "avg_monthly_salary": 8000,
        "replacement_cost_per_exit": 24000,
        "primary_turnover_driver": "Competitive remote offers for Senior Cloud & AI Engineers",
        "recommended_action": "Target 7% retention adjustment for top-quartile engineers and fast-track 6 critical cloud hires.",
    },
    {
        "id": "dept-sales",
        "name": "Sales & Commercial",
        "head_of_department": "Marcus Vance (Chief Commercial Officer)",
        "headcount": 110,
        "open_roles": 9,
        "annual_departures": 20,
        "turnover_pct": 18.2,
        "regrettable_departures": 8,
        "avg_time_to_hire_days": 31,
        "avg_tenure_years": 2.1,
        "retention_status": "Action Needed",
        "monthly_cost": 715000,
        "avg_monthly_salary": 6500,
        "replacement_cost_per_exit": 18000,
        "primary_turnover_driver": "Mid-tenure Account Executive exits following Q3 commission accelerator adjustments",
        "recommended_action": "Rebalance Q4 sales commission tiers and introduce 6-month onboarding coaching for new AEs.",
    },
    {
        "id": "dept-ops",
        "name": "Customer Operations",
        "head_of_department": "Amina Odhiambo (VP of Customer Operations)",
        "headcount": 130,
        "open_roles": 8,
        "annual_departures": 19,
        "turnover_pct": 14.6,
        "regrettable_departures": 5,
        "avg_time_to_hire_days": 21,
        "avg_tenure_years": 2.4,
        "retention_status": "Watch Closely",
        "monthly_cost": 585000,
        "avg_monthly_salary": 4500,
        "replacement_cost_per_exit": 11000,
        "primary_turnover_driver": "Frontline shift fatigue and limited promotion visibility after 18 months",
        "recommended_action": "Launch structured Tier-1 to Tier-2 internal career ladder and flexible shift rotation.",
    },
    {
        "id": "dept-fin",
        "name": "Finance & Admin",
        "head_of_department": "David Kimani (Chief Financial Officer)",
        "headcount": 55,
        "open_roles": 3,
        "annual_departures": 4,
        "turnover_pct": 7.3,
        "regrettable_departures": 1,
        "avg_time_to_hire_days": 29,
        "avg_tenure_years": 4.2,
        "retention_status": "Healthy",
        "monthly_cost": 357500,
        "avg_monthly_salary": 6500,
        "replacement_cost_per_exit": 16000,
        "primary_turnover_driver": "Low natural attrition; strong internal succession bench",
        "recommended_action": "Maintain annual inflation review and cross-train controllers across regional entities.",
    },
    {
        "id": "dept-people",
        "name": "People & Culture",
        "head_of_department": "Grace Njeri (Chief Human Resources Officer)",
        "headcount": 40,
        "open_roles": 2,
        "annual_departures": 3,
        "turnover_pct": 7.5,
        "regrettable_departures": 1,
        "avg_time_to_hire_days": 26,
        "avg_tenure_years": 3.9,
        "retention_status": "Healthy",
        "monthly_cost": 222500,
        "avg_monthly_salary": 5562.5,
        "replacement_cost_per_exit": 14000,
        "primary_turnover_driver": "High stability across Talent Acquisition and HR Operations",
        "recommended_action": "Reallocate recruiter capacity to support Engineering and Sales open roles.",
    },
]

QUARTERLY_TRENDS: List[Dict[str, Any]] = [
    {"quarter": "Q1 2026", "headcount": 452, "attrition_pct": 12.4, "time_to_hire_days": 35, "monthly_payroll": 2840000},
    {"quarter": "Q2 2026", "headcount": 464, "attrition_pct": 13.1, "time_to_hire_days": 34, "monthly_payroll": 2930000},
    {"quarter": "Q3 2026", "headcount": 472, "attrition_pct": 14.2, "time_to_hire_days": 33, "monthly_payroll": 2990000},
    {"quarter": "Q4 2026 (Current)", "headcount": 480, "attrition_pct": 13.8, "time_to_hire_days": 32, "monthly_payroll": 3040000},
]

BOARD_HIGHLIGHTS: List[Dict[str, str]] = [
    {
        "title": "Sales & Commercial Turnover Requires Q4 Intervention (18.2%)",
        "category": "Retention Priority",
        "impact": "$360,000 annual replacement cost across 20 exits (8 regrettable)",
        "summary": "Sales turnover is running 4.4 percentage points above the 13.8% company average. Adjusting Q4 commission accelerators and pairing new hires with senior mentors is projected to cut Sales turnover to 12.0%, saving $108,000 in replacement fees.",
    },
    {
        "title": "Engineering Hiring Speed Needs Fast-Track Panel (42 Days to Hire)",
        "category": "Hiring Velocity",
        "impact": "12 open roles delaying Q1 product roadmap milestones",
        "summary": "Engineering takes 42 days on average to fill a role compared to 32 days company-wide. Consolidating technical interviews from 4 rounds to 2 structured sessions will shorten hiring time by 11 days.",
    },
    {
        "title": "Regrettable Departures Concentrated in 2-to-3 Year Tenure Band",
        "category": "Talent Bench Strength",
        "impact": "17 of 24 regrettable departures occurred in Engineering & Sales",
        "summary": "71% of regrettable departures come from high performers hitting their 24-month mark without an internal grade progression. Introducing a clear mid-year promotion and salary review window protects critical talent.",
    },
]


def aggregate_workforce_kpis(departments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministically aggregates executive workforce KPIs from the department table."""
    total_headcount = sum(int(d["headcount"]) for d in departments)
    total_open_roles = sum(int(d["open_roles"]) for d in departments)
    total_departures = sum(int(d["annual_departures"]) for d in departments)
    regrettable_departures = sum(int(d["regrettable_departures"]) for d in departments)
    monthly_payroll_cost = sum(float(d["monthly_cost"]) for d in departments)
    annual_payroll_cost = monthly_payroll_cost * 12.0

    annual_attrition_rate_pct = (
        round((total_departures / total_headcount) * 100.0, 1) if total_headcount > 0 else 0.0
    )

    if total_open_roles > 0:
        weighted_tth = sum(int(d["open_roles"]) * float(d["avg_time_to_hire_days"]) for d in departments) / total_open_roles
    else:
        weighted_tth = sum(float(d["avg_time_to_hire_days"]) for d in departments) / max(len(departments), 1)
    avg_time_to_hire_days = int(round(weighted_tth))

    if total_headcount > 0:
        weighted_tenure = sum(int(d["headcount"]) * float(d["avg_tenure_years"]) for d in departments) / total_headcount
    else:
        weighted_tenure = 0.0
    avg_tenure_years = round(weighted_tenure, 1)

    regrettable_share_pct = (
        round((regrettable_departures / total_departures) * 100.0, 1) if total_departures > 0 else 0.0
    )

    return {
        "total_active_headcount": total_headcount,
        "total_open_roles": total_open_roles,
        "total_annual_departures": total_departures,
        "annual_attrition_rate_pct": annual_attrition_rate_pct,
        "regrettable_departures": regrettable_departures,
        "regrettable_share_pct": regrettable_share_pct,
        "avg_time_to_hire_days": avg_time_to_hire_days,
        "avg_tenure_years": avg_tenure_years,
        "monthly_payroll_cost": round(monthly_payroll_cost, 2),
        "annual_payroll_cost": round(annual_payroll_cost, 2),
        "avg_monthly_cost_per_employee": round(monthly_payroll_cost / max(total_headcount, 1), 2),
        "avg_annual_cost_per_employee": round(annual_payroll_cost / max(total_headcount, 1), 2),
    }


def run_workforce_stress_test(
    state: Dict[str, Any],
    annual_salary_increment_pct: float = 5.0,
    projected_turnover_pct: float = 13.8,
    planned_new_hires: int = 25,
) -> Dict[str, Any]:
    """
    Deterministically computes the annual payroll and replacement cost impact
    of adjusting Annual Salary Increment %, Projected Turnover %, and Planned New Hires.
    """
    departments = state["departments"]
    kpis = aggregate_workforce_kpis(departments)

    baseline_headcount = kpis["total_active_headcount"]  # 480
    baseline_monthly_payroll = kpis["monthly_payroll_cost"]  # 3,040,000.0
    baseline_annual_payroll = kpis["annual_payroll_cost"]  # 36,480,000.0
    baseline_departures = kpis["total_annual_departures"]  # 66
    baseline_turnover_pct = kpis["annual_attrition_rate_pct"]  # 13.8%
    avg_annual_salary = kpis["avg_annual_cost_per_employee"]  # 76,000.0

    # Deterministic HR cost parameters:
    # - Replacing an existing employee departure costs 25% of average annual salary ($19,000)
    #   covering agency/sourcing fees, background checks, onboarding, and ramp-up productivity gap.
    # - Recruiting a planned expansion hire costs 15% of average annual salary ($11,400).
    replacement_cost_per_exit = round(avg_annual_salary * 0.25, 2)  # 19,000.0
    recruitment_cost_per_new_hire = round(avg_annual_salary * 0.15, 2)  # 11,400.0

    # 1. Salary Increment Impact on Existing Workforce
    annual_salary_increment_cost = round(
        baseline_annual_payroll * (float(annual_salary_increment_pct) / 100.0), 2
    )
    monthly_salary_increment_cost = round(annual_salary_increment_cost / 12.0, 2)

    # 2. Planned New Hires Payroll Impact (at post-increment average salary)
    adjusted_annual_salary_per_hire = avg_annual_salary * (1.0 + float(annual_salary_increment_pct) / 100.0)
    new_hires_annual_payroll_cost = round(int(planned_new_hires) * adjusted_annual_salary_per_hire, 2)
    new_hires_monthly_payroll_cost = round(new_hires_annual_payroll_cost / 12.0, 2)
    new_hires_recruitment_cost = round(int(planned_new_hires) * recruitment_cost_per_new_hire, 2)

    # 3. Turnover & Replacement Cost Impact
    projected_departures = int(round(baseline_headcount * (float(projected_turnover_pct) / 100.0)))
    baseline_replacement_cost = round(baseline_departures * replacement_cost_per_exit, 2)
    projected_replacement_cost = round(projected_departures * replacement_cost_per_exit, 2)
    replacement_cost_variance = round(projected_replacement_cost - baseline_replacement_cost, 2)

    # Total Recruitment & Replacement Budget (backfilling departures + hiring net new roles)
    total_recruitment_and_replacement_cost = round(
        projected_replacement_cost + new_hires_recruitment_cost, 2
    )

    # 4. Consolidated Projected Totals
    projected_headcount = baseline_headcount + int(planned_new_hires)
    projected_annual_payroll = round(
        baseline_annual_payroll + annual_salary_increment_cost + new_hires_annual_payroll_cost, 2
    )
    projected_monthly_payroll = round(projected_annual_payroll / 12.0, 2)

    net_annual_budget_impact = round(
        annual_salary_increment_cost
        + new_hires_annual_payroll_cost
        + replacement_cost_variance
        + new_hires_recruitment_cost,
        2,
    )

    total_projected_people_budget = round(
        projected_annual_payroll + total_recruitment_and_replacement_cost, 2
    )
    baseline_total_people_budget = round(baseline_annual_payroll + baseline_replacement_cost, 2)

    # Department-by-department simulated breakdown
    department_projections: List[Dict[str, Any]] = []
    for dept in departments:
        dept_share = dept["headcount"] / max(baseline_headcount, 1)
        dept_new_hires = int(round(int(planned_new_hires) * dept_share))
        dept_base_annual = float(dept["monthly_cost"]) * 12.0
        dept_merit_cost = round(dept_base_annual * (float(annual_salary_increment_pct) / 100.0), 2)
        dept_hire_payroll = round(
            dept_new_hires * float(dept["avg_monthly_salary"]) * 12.0 * (1.0 + float(annual_salary_increment_pct) / 100.0),
            2,
        )
        # Scale department turnover proportionally to company turnover slider
        turnover_ratio = float(projected_turnover_pct) / max(baseline_turnover_pct, 0.1)
        dept_proj_turnover_pct = round(float(dept["turnover_pct"]) * turnover_ratio, 1)
        dept_proj_exits = int(round(dept["headcount"] * (dept_proj_turnover_pct / 100.0)))
        dept_replacement_cost = round(dept_proj_exits * float(dept["replacement_cost_per_exit"]), 2)

        department_projections.append(
            {
                "name": dept["name"],
                "baseline_headcount": dept["headcount"],
                "projected_headcount": dept["headcount"] + dept_new_hires,
                "projected_turnover_pct": dept_proj_turnover_pct,
                "projected_departures": dept_proj_exits,
                "annual_salary_review_cost": dept_merit_cost,
                "new_hire_payroll_cost": dept_hire_payroll,
                "replacement_cost": dept_replacement_cost,
                "projected_annual_cost": round(dept_base_annual + dept_merit_cost + dept_hire_payroll, 2),
            }
        )

    # Plain-English Executive Verdict
    if projected_turnover_pct > 16.0:
        risk_status = "High Turnover Cost Alert"
        board_guidance = (
            f"At {projected_turnover_pct:.1f}% turnover ({projected_departures} departures), replacement hiring alone consumes "
            f"${projected_replacement_cost:,.0f}—an extra ${replacement_cost_variance:,.0f} above current levels. "
            "Redirecting 1.5% into targeted retention reviews in Sales and Engineering is more cost-effective than backfilling exits."
        )
    elif projected_turnover_pct < 11.0:
        risk_status = "Strong Retention Savings"
        board_guidance = (
            f"Lowering turnover to {projected_turnover_pct:.1f}% ({projected_departures} departures) saves "
            f"${abs(replacement_cost_variance):,.0f} in avoidable recruitment and ramp-up costs, helping self-fund the "
            f"{annual_salary_increment_pct:.1f}% annual salary review."
        )
    else:
        risk_status = "Balanced Workforce Plan"
        board_guidance = (
            f"A {annual_salary_increment_pct:.1f}% salary increment with {planned_new_hires} planned hires and "
            f"{projected_turnover_pct:.1f}% turnover adds ${net_annual_budget_impact:,.0f} in net annual people investment, "
            f"bringing monthly payroll to ${projected_monthly_payroll:,.0f}."
        )

    return {
        "inputs": {
            "annual_salary_increment_pct": round(float(annual_salary_increment_pct), 1),
            "projected_turnover_pct": round(float(projected_turnover_pct), 1),
            "planned_new_hires": int(planned_new_hires),
        },
        "baseline": {
            "headcount": baseline_headcount,
            "monthly_payroll_cost": baseline_monthly_payroll,
            "annual_payroll_cost": baseline_annual_payroll,
            "annual_turnover_pct": baseline_turnover_pct,
            "annual_departures": baseline_departures,
            "annual_replacement_cost": baseline_replacement_cost,
            "total_people_budget": baseline_total_people_budget,
        },
        "projected": {
            "headcount": projected_headcount,
            "monthly_payroll_cost": projected_monthly_payroll,
            "annual_payroll_cost": projected_annual_payroll,
            "annual_turnover_pct": round(float(projected_turnover_pct), 1),
            "annual_departures": projected_departures,
            "annual_salary_increment_cost": annual_salary_increment_cost,
            "monthly_salary_increment_cost": monthly_salary_increment_cost,
            "new_hires_annual_payroll_cost": new_hires_annual_payroll_cost,
            "new_hires_monthly_payroll_cost": new_hires_monthly_payroll_cost,
            "new_hires_recruitment_cost": new_hires_recruitment_cost,
            "annual_replacement_cost": projected_replacement_cost,
            "replacement_cost_variance": replacement_cost_variance,
            "total_recruitment_and_replacement_cost": total_recruitment_and_replacement_cost,
            "net_annual_budget_impact": net_annual_budget_impact,
            "total_projected_people_budget": total_projected_people_budget,
        },
        "unit_assumptions": {
            "avg_annual_salary": avg_annual_salary,
            "replacement_cost_per_exit": replacement_cost_per_exit,
            "recruitment_cost_per_new_hire": recruitment_cost_per_new_hire,
        },
        "department_projections": department_projections,
        "risk_status": risk_status,
        "board_guidance": board_guidance,
    }


def get_initial_state() -> Dict[str, Any]:
    departments = deepcopy(INITIAL_DEPARTMENTS)
    kpis = aggregate_workforce_kpis(departments)
    return {
        "company_profile": {
            "name": "Apex Global Enterprises",
            "reporting_period": "Q4 2026 Executive Board Cycle",
            "currency": "USD",
            "chro_lead": "Grace Njeri, Chief Human Resources Officer",
            "ceo_sponsor": "Jonathan Sterling, Chief Executive Officer",
            "cfo_sponsor": "David Kimani, Chief Financial Officer",
        },
        "executive_kpis": kpis,
        "departments": departments,
        "quarterly_trends": deepcopy(QUARTERLY_TRENDS),
        "board_highlights": deepcopy(BOARD_HIGHLIGHTS),
        "sample_questions": [
            "Which departments have the highest turnover and regrettable departures right now?",
            "What is the total budget impact of a 6% salary review and 20 new hires if we cut turnover to 10%?",
            "Why is Engineering taking 42 days to hire and how do we speed up recruitment?",
            "Give me a 1-page CHRO & CEO summary of our workforce health and Q1 priorities.",
        ],
    }
