"""test_app.py - Automated pytest suite for Agent #09: Workforce Analytics Agent."""

from __future__ import annotations
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from auth_service import GOOGLE_CLIENT_ID, _OTP_STORE
from seed_data import aggregate_workforce_kpis, get_initial_state, run_workforce_stress_test

client = TestClient(app)


def test_health_and_google_client_id():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["agent_number"] == 9
    assert data["agent_name"] == "Workforce Analytics Agent"
    assert data["google_client_id"] == "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"
    assert GOOGLE_CLIENT_ID == "259388273008-n8vg3ae8be86e56svvg09rbdciah17u1.apps.googleusercontent.com"


def test_workforce_kpi_aggregation_and_departments():
    res = client.get("/api/workforce/overview")
    assert res.status_code == 200
    data = res.json()

    kpis = data["executive_kpis"]
    assert kpis["total_active_headcount"] == 480
    assert kpis["total_open_roles"] == 34
    assert kpis["total_annual_departures"] == 66
    assert kpis["annual_attrition_rate_pct"] == 13.8
    assert kpis["regrettable_departures"] == 24
    assert kpis["avg_time_to_hire_days"] == 32
    assert kpis["monthly_payroll_cost"] == 3040000.0
    assert kpis["annual_payroll_cost"] == 36480000.0

    departments = data["departments"]
    dept_names = [d["name"] for d in departments]
    assert dept_names == [
        "Engineering",
        "Sales & Commercial",
        "Customer Operations",
        "Finance & Admin",
        "People & Culture",
    ]
    for d in departments:
        assert "headcount" in d
        assert "open_roles" in d
        assert "turnover_pct" in d
        assert "retention_status" in d
        assert "monthly_cost" in d


def test_deterministic_what_if_simulator_math():
    state = get_initial_state()
    # Test 1: 0% salary increment, baseline turnover (13.8% -> 66 exits), 0 new hires
    zero_change = run_workforce_stress_test(
        state,
        annual_salary_increment_pct=0.0,
        projected_turnover_pct=13.8,
        planned_new_hires=0,
    )
    assert zero_change["projected"]["headcount"] == 480
    assert zero_change["projected"]["annual_salary_increment_cost"] == 0.0
    assert zero_change["projected"]["new_hires_annual_payroll_cost"] == 0.0
    assert zero_change["projected"]["new_hires_recruitment_cost"] == 0.0
    assert zero_change["projected"]["annual_departures"] == 66
    assert zero_change["projected"]["annual_replacement_cost"] == 1254000.0
    assert zero_change["projected"]["replacement_cost_variance"] == 0.0
    assert zero_change["projected"]["net_annual_budget_impact"] == 0.0
    assert zero_change["projected"]["annual_payroll_cost"] == 36480000.0

    # Test 2: API endpoint with 6% salary increment, 10% turnover (48 exits), 20 new hires
    res = client.post(
        "/api/workforce/simulate",
        json={
            "annual_salary_increment_pct": 6.0,
            "projected_turnover_pct": 10.0,
            "planned_new_hires": 20,
        },
    )
    assert res.status_code == 200
    sim = res.json()
    proj = sim["projected"]

    # 6% of $36,480,000 = $2,188,800
    assert proj["annual_salary_increment_cost"] == 2188800.0
    # 20 new hires * $76,000 * 1.06 = $1,611,200
    assert proj["new_hires_annual_payroll_cost"] == 1611200.0
    # 20 new hires * $11,400 recruitment fee = $228,000
    assert proj["new_hires_recruitment_cost"] == 228000.0
    # 10% of 480 = 48 exits * $19,000 = $912,000 (saves $342,000 vs $1,254,000 baseline)
    assert proj["annual_departures"] == 48
    assert proj["annual_replacement_cost"] == 912000.0
    assert proj["replacement_cost_variance"] == -342000.0
    # Projected annual payroll = 36,480,000 + 2,188,800 + 1,611,200 = 40,280,000
    assert proj["annual_payroll_cost"] == 40280000.0
    assert proj["headcount"] == 500
    assert sim["risk_status"] == "Strong Retention Savings"


def test_ask_workforce_agent_endpoint():
    # Turnover question
    res1 = client.post(
        "/api/agent/ask",
        json={"question": "Which departments have the highest turnover and regrettable departures?"},
    )
    assert res1.status_code == 200
    ans1 = res1.json()
    assert "Sales & Commercial" in ans1["headline"]
    assert len(ans1["key_points"]) >= 3
    assert "Workforce Analytics Agent" in ans1["agent_badge"]

    # Hiring speed question
    res2 = client.post(
        "/api/agent/ask",
        json={"question": "Why is Engineering taking 42 days to hire?"},
    )
    assert res2.status_code == 200
    ans2 = res2.json()
    assert "32 Days" in ans2["headline"]

    # Budget simulation question
    res3 = client.post(
        "/api/agent/ask",
        json={
            "question": "What is the budget impact of our salary increment and planned hires?",
            "annual_salary_increment_pct": 5.0,
            "projected_turnover_pct": 13.8,
            "planned_new_hires": 25,
        },
    )
    assert res3.status_code == 200
    ans3 = res3.json()
    assert "Projected Annual Payroll" in ans3["headline"]
    assert ans3["engine"] == "Enterprise People & Analytics Engine"
    assert "gemini" not in ans3["engine"].lower()
    assert "vertex" not in ans3["engine"].lower()


def test_sso_and_otp_endpoints():
    # 1. Consumer email rejected for OTP
    bad_res = client.post("/api/auth/otp/request", json={"email": "random.person@gmail.com"})
    assert bad_res.status_code == 403

    # 2. Corporate work email accepted for OTP & verified
    corp_email = "chro.exec@sybyl.com"
    with patch("main.send_otp_email") as mock_send:
        req_res = client.post("/api/auth/otp/request", json={"email": corp_email})
        assert req_res.status_code == 200
        assert req_res.json()["status"] == "sent"
        assert mock_send.called
        sent_code = mock_send.call_args[0][1]

    ver_res = client.post("/api/auth/otp/verify", json={"email": corp_email, "code": sent_code})
    assert ver_res.status_code == 200
    assert ver_res.json()["status"] == "authenticated"
    assert ver_res.json()["user"]["email"] == corp_email

    # 3. Instant Demo Sign-In endpoint
    demo_res = client.post("/api/auth/demo", json={"role": "CHRO / Executive View"})
    assert demo_res.status_code == 200
    assert demo_res.json()["status"] == "authenticated"
    assert demo_res.json()["user"]["role"] == "CHRO / Executive View"

    # 4. Google SSO endpoint with mocked token verifier
    with patch("main.verify_google_id_token") as mock_google:
        mock_google.return_value = (
            True,
            {"email": "grace.njeri@sybyl.com", "name": "Grace Njeri", "picture": ""},
            "",
        )
        g_res = client.post("/api/auth/google", json={"credential": "mock-valid-google-jwt"})
        assert g_res.status_code == 200
        assert g_res.json()["status"] == "authenticated"
        assert g_res.json()["user"]["auth_method"] == "google_sso"


def test_spa_index_served():
    res = client.get("/")
    assert res.status_code == 200
    assert "Workforce Analytics Agent" in res.text


def test_zero_banned_word_occurrences():
    banned_word = "".join(chr(c) for c in [99, 111, 112, 105, 108, 111, 116])
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    checked_files = 0
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".pytest_cache", "dist")]
        for fname in files:
            if fname.endswith((".py", ".jsx", ".js", ".ts", ".tsx", ".html", ".css", ".md", ".json")):
                fpath = os.path.join(root, fname)
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                assert banned_word not in content, f"Banned term found in {fpath}"
                checked_files += 1
    assert checked_files >= 8
