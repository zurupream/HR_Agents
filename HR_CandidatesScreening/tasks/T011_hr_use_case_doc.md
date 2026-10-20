# T011 - HR & Recruitment use case Word document

## Goal
Create a Word document (.docx) describing the "AI Agents for HR & Recruitment" use case, in the same structure as the outline below. Do NOT include a "Relevant agents" section or any template links.

## Output
~/candidates_screening/hr_recruitment_doc/output/AgentWorks_HR_Recruitment_Use_Case.docx
Build with python-docx in a venv inside ~/candidates_screening/hr_recruitment_doc/. Use real Word headings and bullet lists.

## Content (reproduce this text, in this order)

Title: AI Agents for HR & Recruitment

Intro: Hiring managers drown in inbound resumes, scheduling ping-pong, and onboarding checklists - while candidates expect fast, fair communication.

Section: The challenge
- Screening against structured criteria takes hours per role, and unconscious bias creeps in when process is informal.
- Interview coordination across time zones creates email chains that delay offers and frustrate top candidates.
- New hires miss critical policy acknowledgements because onboarding tasks scatter across HRIS, email, and shared drives.

Section: The AgentWorks solution
AgentWorks helps HR teams encode rubrics and knockout questions so screening agents summarize fit against explicit criteria - never a black-box hire/no-hire. Humans remain the decision makers for shortlists and offers; agents handle repetitive reading and scheduling logistics.
Interview scheduler agents propose slots that respect panel availability, time zones, and room resources, then sync updates when plans change. Outreach templates stay on-brand and localized while still allowing recruiter edits before send.
Onboarding agents walk new hires through tasks with links to the right policy PDFs and e-sign steps, nudging owners when something stalls. Sensitive topics (compensation, medical, disciplinary) can be excluded from automation by policy.
Activity is centralized for audits and DEI reporting: you can show who saw which candidate summary and when approvals happened. That is increasingly important as regulators scrutinize automated employment tools alongside data protection rules.

Section: Workflow in four steps
1. Define criteria - Upload job scorecards and policy boundaries so screening stays aligned with legal and DEI guidelines.
2. Screen & summarize - Agents cluster applicants, highlight evidence against rubrics, and flag missing information.
3. Schedule & communicate - Coordinators receive proposed slots and candidate comms drafts ready for one-click approval.
4. Onboard with guardrails - Day-one tasks, policy reads, and system access requests flow as tracked checklists with human oversight.

Section: Worked example - Screening 80 applicants against a scorecard
- Agent: Candidate Screening Agent, then Interview Scheduler Agent
- Input: A job scorecard with weighted must-haves and knockout questions, plus the resume and application batch for the requisition.
- Approval gate: The agent clusters candidates and summarizes evidence against each scorecard line - it never issues a hire/no-hire verdict. A recruiter reviews the shortlist and manually approves who advances before the Interview Scheduler Agent proposes panel slots.
- Output: A ranked shortlist with evidence citations per criterion, plus (once approved) proposed interview slots synced to panel calendars and time zones.

Section: Results & benefits
- Faster time-to-interview: Less manual reading and calendar tennis means qualified candidates hear back sooner.
- Consistent process: Every requisition follows the same documented steps - easier for audits and hiring manager training.
- Human-owned decisions: Automation prepares evidence; people retain control on shortlists, messaging, and offers.

## Done means
- The .docx exists at the output path, opens without error, and has the sections above in order.
- No "Relevant agents" section, no template links.
- Final summary gives the output path and a section list.
