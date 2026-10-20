# T018 - Admin portal to manage who can use the app (allow-list in the database)

## Goal
Replace the allow-list JSON files with an admin page inside the web app. Only admins can change who has access.
Every change is logged. The first admin is a root admin defined in config.

## Root admin (bootstrap)
- Root admin email: guruprem.saginadham@sybyl.com
- Defined in screening_webapp/config/root_admins.json (a list, currently one email). Root admins can always sign in,
  cannot be removed from the admin list through the UI, and can add or remove other admins.
- No other secrets. Never store a client secret.

## Data model (SQLite via SQLAlchemy, same DATABASE_URL approach as before)
- allowed_users: id, email (lowercase, unique), role (admin | hr), added_by, added_at_utc, active (bool)
- allowed_domains: id, domain (e.g. "example.gov"), role (hr), added_by, added_at_utc, active (bool)
  Domain rules let a whole organisation in, but only if the domain is listed by an admin. Empty by default.
- audit_log already exists: record every grant, revoke, and role change with actor and time.

## Access rule (applies to every API call and the page)
Signed in with a valid Google ID token (already implemented) AND one of:
- email is a root admin, or
- email is in allowed_users with active = true, or
- email's domain is in allowed_domains with active = true (role hr).
Otherwise: 403 with a clear message: "Your Google account signed in, but it is not authorised to use this app. Ask an admin to add your email."
The message must not reveal the list of other users or domains.

## Admin page (new tab "Access", visible to admins only)
- Table of users and domains with role, status, who added them, when.
- Add user (email + role), remove or deactivate, change role.
- Add domain (domain + role), deactivate.
- Changes take effect on the next request (no restart).
- Show the audit trail for access changes.
- Guard: the last active admin cannot be removed. Root admins cannot be deactivated from the UI.

## Migration
- Read the current demo_allowed_emails.json and allowed_emails.json. Import their emails as allowed_users (role hr) on first start, once, and log it.
  Then stop reading those JSON files. Keep them only as a documented fallback for tests.
- Import guruprem.saginadham@sybyl.com as hr and as admin via root_admins.json.

## Demo mode
- Keep the demo sign-in button for local tests, but it must use the demo user hr.demo@example.com, which is seeded as hr for demo only.
  Mark the demo user clearly in the UI.

## Tests (pytest)
- Root admin signs in -> allowed and sees the Access tab.
- Active allowed user -> allowed; deactivated user -> 403 with the new message.
- Domain rule: user with a listed domain -> allowed; unlisted domain -> 403.
- Non-admin HR calls an admin endpoint -> 403.
- Cannot remove the last active admin -> 409. Root admin cannot be deactivated -> 409.
- Every change writes an audit_log row.
- Migration imports the JSON emails once and does not duplicate them on second start.
- All existing agent and web app tests still pass.

## Rules
- Work only inside ~/candidates_screening. No keys, client secrets or personal data in files, logs or messages.
- Do not publish or deploy. Localhost only.

## Open decision (do NOT guess)
- Domain rules for "civil employees, GC" are NOT configured. Leave allowed_domains empty. Add a note in the report that the owner must
  decide the exact domain(s) before they are added.

## Done means
- The Access tab works for the root admin, with add, deactivate, and audit.
- Tests pass (show summary).
- demo/ADMIN_REPORT.md explains in plain language how to add a user and how to add a domain.
