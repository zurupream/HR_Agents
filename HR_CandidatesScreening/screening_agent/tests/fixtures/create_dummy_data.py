"""Generate synthetic Sales hiring test fixtures in a temporary directory for automated tests.

All generated candidates and documents use fictional names, fictional companies, and
synthetic contact details for the role "Sales Executive - Retail and Business Clients".
Used strictly inside temporary test folders (`tmp_path`).
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from docx import Document


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(file_path: Path, lines: list[str]) -> None:
    """Write a valid single-page PDF containing the provided text lines."""
    file_path.parent.mkdir(parents=True, exist_ok=True)

    content_ops = ["BT", "/F1 10 Tf", "14 TL", "45 760 Td"]
    for idx, line in enumerate(lines):
        escaped = _escape_pdf_text(line)
        if idx == 0:
            content_ops.append(f"({escaped}) Tj")
        else:
            content_ops.append(f"T* ({escaped}) Tj")
    content_ops.append("ET")
    stream_bytes = "\n".join(content_ops).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    file_path.write_bytes(bytes(out))


def write_docx(file_path: Path, heading: str, paragraphs: list[str]) -> None:
    """Write a Word document (.docx) with a heading and paragraphs."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_heading(heading, level=1)
    for para in paragraphs:
        doc.add_paragraph(para)
    doc.save(str(file_path))


def build_dummy_dataset(base_dir: Path | None = None) -> dict[str, Any]:
    """Create the Sales Executive job advert and 4 synthetic candidate folders in base_dir.

    If base_dir is not provided, creates a temporary directory.
    Returns a dictionary with paths to `job_advert_path` and `applications_dir`.
    """
    if base_dir is None:
        base_dir = Path(tempfile.mkdtemp(prefix="sales_screening_fixture_"))
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    job_advert_path = base_dir / "job_advert.docx"
    applications_dir = base_dir / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    # 1. Job Advert: Sales Executive - Retail and Business Clients
    write_docx(
        job_advert_path,
        "Job Title: Sales Executive - Retail and Business Clients",
        [
            "Job Title: Sales Executive - Retail and Business Clients",
            "Department: Commercial & Retail Sales",
            "Role Summary: Drive revenue growth across retail and business clients by managing the full sales cycle, closing commercial deals, maintaining accurate CRM pipelines, negotiating contracts, and building lasting client relationships.",
            "Must-Have Requirements (70% total weight):",
            "M1 - B2B & Retail Sales Experience with Targets (Weight 25%): 3+ years of B2B or retail sales experience consistently working against revenue or quota targets.",
            "M2 - Closing Deals & Pipeline Conversion (Weight 25%): Proven track record of prospecting, qualifying leads, and closing deals across retail or business clients.",
            "M3 - CRM Software Proficiency (Weight 20%): Daily hands-on use of Salesforce, HubSpot, or any CRM system for pipeline tracking, forecasting, and account records.",
            "Nice-to-Have Requirements (30% total weight):",
            "N1 - Negotiation & Client Presentations (Weight 15%): Experience in commercial negotiation, pricing proposals, and delivering presentations to stakeholders and decision-makers.",
            "N2 - Client Relationship Management & Bilingual Communication (Weight 15%): Track record in client relationship management, account retention and upselling, and bilingual communication.",
            "Screening Policy: Shortlist Threshold is 70.0 / 100. Career continuity is not required (career breaks are not penalised).",
        ],
    )

    # 2. Candidate A (C001) - Strong Match (Score: 100.0, Shortlisted, AI decided)
    cand_a_dir = applications_dir / "Dummy Candidate A"
    cand_a_dir.mkdir(parents=True, exist_ok=True)
    write_simple_pdf(
        cand_a_dir / "cv.pdf",
        [
            "DUMMY DATA - SYNTHETIC CANDIDATE CV",
            "Name: Dummy Candidate A",
            "Email: candidate.a@example.test | Phone: +44 7700 900111",
            "DOB: 14/05/1988 | Gender: Female | Nationality: British | Marital Status: Married",
            "Address: 10 Example High Street, London",
            "---",
            "PROFESSIONAL SUMMARY",
            "Sales Executive with 6 years of B2B and retail sales experience working against annual revenue targets and quarterly quotas, having consistently exceeded targets by 125%.",
            "CORE EXPERIENCE",
            "Senior Sales Executive - Horizon Retail & Business Group (2020 - Present):",
            "- Full-cycle deal closing: prospecting, qualifying leads, and closing deals across 180+ new business and commercial contracts from discovery to signature.",
            "- Daily CRM user with Salesforce and HubSpot for pipeline tracking, revenue forecasting, activity logging, and maintaining complete account records.",
            "- Led commercial terms negotiation, pricing proposals, and boardroom presentations to senior stakeholders and decision-makers.",
            "- Managed long-term client relationship and account management portfolios with 96% retention, consistent upselling and renewals, and fluent bilingual communication in English and French.",
            "Career Break (Jan 2023 - Sep 2023): Full-time parental leave.",
            "Retail & Business Sales Representative - Metro Commercial Supplies (2017 - 2020):",
            "- Surpassed quarterly quota and annual sales targets selling retail merchandising packages to regional business clients.",
        ],
    )
    write_docx(
        cand_a_dir / "cover_letter.docx",
        "Cover Letter - Dummy Candidate A",
        [
            "Dear Hiring Team,",
            "I am applying for the Sales Executive - Retail and Business Clients position.",
            "Over 6 years in B2B and retail sales, I have consistently exceeded annual revenue targets and quarterly quotas.",
            "My work centres on full-cycle prospecting, qualifying leads, and closing deals from discovery to signature, backed by daily Salesforce and HubSpot CRM discipline for pipeline tracking, forecasting, and account records.",
            "I also bring extensive experience in commercial terms negotiation, pricing proposals, boardroom presentations to decision-makers, long-term client relationship retention, upselling, and fluent bilingual communication in English and French.",
        ],
    )
    (cand_a_dir / "email.eml").write_text(
        "From: Dummy Candidate A <candidate.a@example.test>\n"
        "To: recruitment@example.test\n"
        "Subject: Application for Sales Executive - Retail and Business Clients - Dummy Candidate A\n"
        "Content-Type: text/plain; charset=\"utf-8\"\n\n"
        "Hello Recruiting Team,\n\n"
        "Please find attached my cover letter and CV for the Sales Executive - Retail and Business Clients role.\n"
        "I bring 6 years of B2B and retail sales experience exceeding revenue targets, full-cycle deal closing, daily Salesforce CRM pipeline tracking, commercial negotiation and presentations, and bilingual client relationship management.\n",
        encoding="utf-8",
    )

    # 3. Candidate B (C002) - Partial Match (Score: 53.0, Not Shortlisted, AI decided)
    cand_b_dir = applications_dir / "Dummy Candidate B"
    cand_b_dir.mkdir(parents=True, exist_ok=True)
    write_docx(
        cand_b_dir / "cv.docx",
        "Curriculum Vitae - Dummy Candidate B",
        [
            "Name: Dummy Candidate B | Email: candidate.b@example.test | Phone: +44 7700 900222",
            "Profile: Retail Sales Associate with 2 years of retail sales experience working with monthly store revenue targets.",
            "Experience:",
            "Retail Sales Associate (2 years): Worked against monthly retail sales targets and store revenue goals.",
            "Sales Support: Assisted senior executives with qualifying leads and supporting new business inquiries, though I have not yet independently closed full-cycle commercial contracts.",
            "CRM Administration: Used Salesforce CRM daily to maintain account records and log customer inquiries.",
            "Client Proposals: Prepared pricing proposals and delivered product presentations to store stakeholders.",
            "Additional Note: I do not have long-term account management or bilingual experience yet.",
        ],
    )
    write_simple_pdf(
        cand_b_dir / "cover_letter.pdf",
        [
            "Cover Letter - Dummy Candidate B",
            "Dear Hiring Manager,",
            "I am writing to apply for the Sales Executive role.",
            "I have 2 years of retail sales experience working with monthly revenue targets.",
            "In my current role I assist with qualifying leads for new business, use Salesforce CRM daily to update account records, and prepare pricing proposals and presentations for store stakeholders.",
            "I have not yet managed long-term account retention or bilingual client accounts.",
        ],
    )
    (cand_b_dir / "email.txt").write_text(
        "Subject: Application for Sales Executive - Dummy Candidate B\n\n"
        "Attached are my CV and cover letter highlighting my 2 years of retail sales experience with revenue targets, Salesforce CRM account records, and pricing presentations.\n",
        encoding="utf-8",
    )

    # 4. Candidate C (C003) - Non-Match (Score: 0.0, Not Shortlisted, AI decided)
    cand_c_dir = applications_dir / "Dummy Candidate C"
    cand_c_dir.mkdir(parents=True, exist_ok=True)
    write_simple_pdf(
        cand_c_dir / "cover_letter.pdf",
        [
            "Cover Letter - Dummy Candidate C",
            "Dear Recruitment Team,",
            "I am submitting my application for consideration.",
            "My background over the past 8 years is in greenhouse botanical care, floral arrangement, and nursery plant propagation.",
            "I do not have experience with B2B or retail sales targets, closing deals, CRM software, commercial negotiations, or client presentations.",
            "Thank you for reading my letter.",
        ],
    )
    (cand_c_dir / "email.txt").write_text(
        "Subject: Application - Dummy Candidate C\n\n"
        "Please find my cover letter attached. My background is in greenhouse botanical care and I do not have experience with B2B or retail sales targets, closing deals, CRM software, negotiations, or presentations.\n",
        encoding="utf-8",
    )

    # 5. Candidate D (C004) - Borderline / Missing M3 CRM Evidence (Score: 64.0, Needs HR review)
    cand_d_dir = applications_dir / "Dummy Candidate D"
    cand_d_dir.mkdir(parents=True, exist_ok=True)
    write_simple_pdf(
        cand_d_dir / "cv.pdf",
        [
            "DUMMY DATA - SYNTHETIC CANDIDATE CV",
            "Name: Dummy Candidate D",
            "Email: candidate.d@example.test | Phone: +44 7700 900444",
            "---",
            "PROFESSIONAL SUMMARY",
            "Sales Executive with 5 years of B2B and retail sales experience working against annual revenue targets and quarterly quotas, having consistently exceeded targets across regional territories.",
            "EXPERIENCE",
            "Regional Sales Executive - Summit Commercial Retail (2019 - Present):",
            "- Proven track record in prospecting, closing deals, and winning new business across retail and commercial accounts.",
            "- Skilled in commercial negotiation, preparing pricing proposals, and delivering persuasive presentations to client buyers.",
            "- Experienced in client relationship management, driving high retention and renewals, with bilingual communication skills.",
        ],
    )
    write_docx(
        cand_d_dir / "cover_letter.docx",
        "Cover Letter - Dummy Candidate D",
        [
            "Dear Hiring Manager,",
            "I am excited to apply for the Sales Executive - Retail and Business Clients position.",
            "I bring 5 years of B2B and retail sales experience consistently exceeding annual revenue targets and quarterly quotas.",
            "Throughout my career I have focused on prospecting, closing deals, and winning new business, alongside commercial negotiation, pricing proposals, presentations, and bilingual client relationship retention.",
        ],
    )
    (cand_d_dir / "email.txt").write_text(
        "Subject: Application for Sales Executive - Retail and Business Clients - Dummy Candidate D\n\n"
        "Please find attached my cover letter and CV. I bring 5 years of B2B and retail sales experience exceeding revenue targets and quarterly quotas, prospecting and closing deals for new business, commercial negotiation and pricing presentations, and bilingual client relationship retention.\n",
        encoding="utf-8",
    )

    return {
        "base_dir": base_dir,
        "job_advert_path": job_advert_path,
        "advert_path": job_advert_path,
        "applications_dir": applications_dir,
    }
