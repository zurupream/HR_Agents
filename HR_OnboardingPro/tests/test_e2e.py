"""Comprehensive End-to-End Verification Suite for Sybyl People HR Onboarding."""

from fastapi.testclient import TestClient
from app.database import get_conn, init_db
from app.main import app
from app.seed import seed_demo_data


def test_full_application_links_and_workflows():
    init_db()
    seed_demo_data(force_reset=True)

    # Pause live SMTP during automated test assertions so we don't spam external SMTP
    conn = get_conn()
    conn.execute("UPDATE smtp_settings SET live_mode_enabled = 0 WHERE id = 1")
    conn.commit()
    conn.close()

    client = TestClient(app)

    # 1. Verify Main UI HTML
    res_index = client.get("/")
    assert res_index.status_code == 200
    html = res_index.text
    assert "Fill Sample Candidates" not in html
    assert "Reset Sample Data" not in html
    assert 'id="batchCcEmails"' in html
    assert "separate multiple emails with ;" in html.lower() or "separated by ;" in html.lower()
    assert 'id="tab-history"' in html
    assert 'id="tab-settings"' in html
    assert "Offer Letter Templates" in html
    assert "handleTopOfferButtonClick()" in html

    # 2. Verify Overview & Non-IT Positions
    res_ov = client.get("/api/overview")
    assert res_ov.status_code == 200
    ov = res_ov.json()
    pos_titles = {p["title"] for p in ov["positions"]}
    assert "Sales Manager" in pos_titles
    assert "Merchandiser" in pos_titles
    assert "Procurement Officer" in pos_titles
    assert "Finance Officer" in pos_titles

    # 3. Verify EVERY existing candidate's signing link, signing API, and PDF download link
    assert len(ov["candidates"]) >= 7
    for cand in ov["candidates"]:
        assert ";" in cand["cc_emails_display"] or "@" in cand["cc_emails_display"]
        signing_url = cand["signing_url"]
        assert signing_url and signing_url.startswith("/sign/")

        # Test HTML signing page
        r_sign_html = client.get(signing_url)
        assert r_sign_html.status_code == 200

        # Test JSON signing portal details
        token = signing_url.split("/sign/")[1]
        r_sign_api = client.get(f"/api/sign/{token}")
        assert r_sign_api.status_code == 200
        sign_data = r_sign_api.json()
        assert sign_data["full_name"] == cand["full_name"]
        assert "offer_template" in sign_data
        assert sign_data["offer_template"]["title"]

        # Test Offer PDF download (unsigned & signed)
        offer_id = cand["offer"]["id"]
        r_pdf = client.get(f"/api/offers/{offer_id}/pdf?signed=false")
        assert r_pdf.status_code == 200
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert r_pdf.content.startswith(b"%PDF")

        if cand["offer"]["status"] == "ACCEPTED":
            r_pdf_signed = client.get(f"/api/offers/{offer_id}/pdf?signed=true")
            assert r_pdf_signed.status_code == 200
            assert r_pdf_signed.content.startswith(b"%PDF")

    # 4. Test Offer Launchpad "Send Offer Letter" with semicolon-separated CC emails
    sales_pos_id = next(p["id"] for p in ov["positions"] if p["title"] == "Sales Manager")
    batch_payload = {
        "batch_name": "Commercial Expansion Hiring",
        "cc_emails": "hr@sybyl.com; rachel.adams@sybyl.com; ceo@sybyl.com",
        "offer_expires_in_hours": 72,
        "candidates": [
            {
                "full_name": "Tariq Al-Mansoor",
                "personal_email": "tariq.candidate@example.com",
                "position_id": sales_pos_id,
                "role_category": "EMPLOYEE",
                "compensation": "$92,000/yr + Commission",
                "joining_date": "2026-11-15",
            }
        ],
    }
    res_batch = client.post("/api/offers/batch", json=batch_payload)
    assert res_batch.status_code == 200
    batch_data = res_batch.json()
    assert batch_data["dispatched_count"] == 1
    new_offer = batch_data["created_offers"][0]
    new_offer_id = new_offer["offer_id"]
    new_token = new_offer["signing_token"]

    # Test new candidate's PDF & signing link immediately
    r_new_pdf = client.get(f"/api/offers/{new_offer_id}/pdf?signed=false")
    assert r_new_pdf.status_code == 200
    assert r_new_pdf.content.startswith(b"%PDF")

    r_new_sign = client.get(f"/api/sign/{new_token}")
    assert r_new_sign.status_code == 200
    assert "rachel.adams@sybyl.com" in r_new_sign.json()["cc_emails_display"]

    # Accept the new offer and verify signed PDF & role-based onboarding tasks
    r_accept = client.post(
        f"/api/sign/{new_token}/accept",
        json={
            "signer_name": "Tariq Al-Mansoor",
            "signature_type": "typed",
            "comments": "Excited to join the Sales team!",
        },
    )
    assert r_accept.status_code == 200
    r_signed_pdf = client.get(f"/api/offers/{new_offer_id}/pdf?signed=true")
    assert r_signed_pdf.status_code == 200
    assert r_signed_pdf.content.startswith(b"%PDF")

    # 5. Test Settings: Offer Letter Templates (GET, POST, Reset)
    r_tpl_get = client.get("/api/settings/templates")
    assert r_tpl_get.status_code == 200
    tpl_map = r_tpl_get.json()["templates"]
    assert "EMPLOYEE" in tpl_map and "TRAINEE" in tpl_map and "INTERN" in tpl_map

    r_tpl_save = client.post(
        "/api/settings/templates",
        json={
            "role_category": "EMPLOYEE",
            "title": "Official Appointment Letter — Full-Time",
            "subject_line": "[Offer Letter] {{position_title}} — {{candidate_name}}",
            "intro_text": "Dear {{candidate_name}}, welcome to {{department}} as {{position_title}}!",
            "terms_text": "Your package is {{compensation}} starting {{joining_date}}.",
            "closing_text": "Warm regards, Sybyl People Team",
        },
    )
    assert r_tpl_save.status_code == 200
    assert (
        r_tpl_save.json()["templates"]["EMPLOYEE"]["title"]
        == "Official Appointment Letter — Full-Time"
    )

    r_tpl_reset = client.post("/api/settings/templates/reset")
    assert r_tpl_reset.status_code == 200
    assert "Official Offer of Appointment" in r_tpl_reset.json()["templates"]["EMPLOYEE"]["title"]

    # 6. Test History / Notifications & Sub-Agents Board
    r_notifs = client.get("/api/notifications")
    assert r_notifs.status_code == 200
    notifs = r_notifs.json()
    assert len(notifs) > 0
    for n in notifs[:5]:
        if n.get("offer_id"):
            r_att = client.get(f"/api/offers/{n['offer_id']}/pdf")
            assert r_att.status_code == 200

    r_board = client.get("/api/agents/board")
    assert r_board.status_code == 200
    assert len(r_board.json()["subagents"]) == 4

    # Restore clean demo state with live SMTP re-enabled
    seed_demo_data(force_reset=True)
