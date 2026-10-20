# Admin Access Portal Report (`T018`)

## 1. Overview (Plain Language)

Who can sign in to the Candidate Screening Web Application is now managed inside the application database (`allowed_users` and `allowed_domains` tables in SQLite) through the **4. Access** tab in the web app.

- **Only Admins can see the `4. Access` tab** and change who has access.
- **Changes take effect immediately** on the very next request — no server restart is needed.
- **Every change is recorded** in the `audit_log` table with the admin's email, timestamp (UTC), and action details.
- **Unauthorised Google accounts** receive a clear `403 Forbidden` message that does not reveal any other users or domains:
  > *"Your Google account signed in, but it is not authorised to use this app. Ask an admin to add your email."*

---

## 2. Root Admin Bootstrap

- The bootstrap root admin is defined in `screening_webapp/config/root_admins.json`:
  ```json
  [
    "guruprem.saginadham@sybyl.com"
  ]
  ```
- **Root Admin privileges and guards**:
  - Can always sign in with Google (`role = admin`).
  - Cannot be deactivated, demoted to `hr`, or removed through the UI or API (`409 Conflict`).
  - Can add, deactivate, remove, or change the role (`admin` / `hr`) of other users, and can add or deactivate allowed domains.
  - Additionally, the system prevents removing or deactivating the **last active admin** (`409 Conflict`).
- **No secrets stored**: Only the public Google OAuth Client ID and root admin email address are stored in configuration files. No client secret or API key is stored anywhere in the repository.

---

## 3. How to Add, Change, or Deactivate a User

1. Sign in to the web app at `http://127.0.0.1:8080` using an **Admin** account (such as `guruprem.saginadham@sybyl.com`).
2. Click the **4. Access** tab in the top navigation bar.
3. Under **Authorised Users (`allowed_users`)**:
   - Enter the person's Google email address (for example, `colleague@company.com`) in the **New user email** box.
   - Select their role:
     - **`hr`** — Can view candidate folders, run AI screening, record HR decisions, and export the Excel workbook.
     - **`admin`** — Full HR access plus access to the **4. Access** tab to manage users and domains.
   - Click **Add / Enable User**.
4. **Changing a user's role or status**:
   - To promote an `hr` user to `admin` (or demote an `admin` to `hr`), use the role dropdown on their row.
   - To temporarily block a user from signing in while keeping their record, click **Deactivate**.
   - To re-enable a deactivated user, click **Activate**.
   - To permanently delete a non-root user row, click **Remove**.

---

## 4. How to Add or Deactivate a Domain Rule

Domain rules allow every Google-authenticated user from a specific email domain (for example, `example.gov`) to use the app with role `hr`, without having to add each employee's email individually.

1. Sign in with an **Admin** account and open the **4. Access** tab.
2. Under **Authorised Domains (`allowed_domains` — Role: HR)**:
   - Enter the domain name (for example, `example.gov`) in the **Organisation domain** box.
   - Click **Add / Enable Domain (HR)**.
3. **Deactivating or removing a domain**:
   - Click **Deactivate** next to a domain to immediately stop domain-wide sign-ins for that domain (users who are individually listed as active in `allowed_users` will still be able to sign in).
   - Click **Activate** to re-enable a deactivated domain, or **Remove** to delete the domain rule.

---

## 5. Open Decision Note — Civil Employees / GC Domains

> **Important Open Decision (Not Configured by Default):**
> Domain rules for **"civil employees, GC"** have **not** been configured, and `allowed_domains` is intentionally left **empty (`[]`)** by default.
> The project owner must decide and confirm the exact email domain(s) (for example, the specific government or department domain names) before an admin adds them in the **4. Access** tab.

---

## 6. One-Time Migration & Demo User

- **One-Time Migration**: On first start, the application reads `screening_webapp/config/demo_allowed_emails.json`, `screening_webapp/config/allowed_emails.json`, and `screening_webapp/config/root_admins.json` once, imports:
  - `guruprem.saginadham@sybyl.com` (`role = admin`, `active = true`)
  - `hr.demo@example.com` (`role = hr`, `active = true`)
  and writes a `migrate_allowlist` entry to `audit_log`. Subsequent starts do not re-import or duplicate these rows. The JSON files are kept only as a documented fallback for automated tests that explicitly set `ALLOWED_EMAILS_FILE`.
- **Demo User (`hr.demo@example.com`)**: Kept for local demo testing (`Sign in as Demo HR (hr.demo@example.com)`) with role `hr` and clearly marked with a **`[DEMO USER]`** badge in the top bar and in the Access table.

---

## 7. Automated Test Summary (`pytest`)

All **25 automated tests** across `screening_agent/tests` and `screening_webapp/tests` pass:

- `test_adk_web_entry.py` (4 passed)
- `test_human_in_loop.py` (7 passed)
- `test_webapp.py` (14 passed, including 5 new `T018` tests):
  - `test_t018_migration_imports_once_and_does_not_duplicate`: Verifies one-time JSON-to-SQLite migration, no duplication on second start, and `allowed_domains` empty by default.
  - `test_t018_root_admin_signin_and_access_tab`: Verifies root admin (`guruprem.saginadham@sybyl.com`) signs in (`200`), has `is_admin=True`, sees the `4. Access` tab, and can query `/api/admin/access`.
  - `test_t018_active_vs_deactivated_user_and_403_message`: Verifies active allowed user gets `200`, deactivated user gets `403` with the exact message `"Your Google account signed in, but it is not authorised to use this app. Ask an admin to add your email."` and no leaked user/domain data.
  - `test_t018_domain_rules_and_non_admin_403`: Verifies unlisted domain gets `403`, listed active domain gets `200` (`role=hr`), non-admin HR calling admin endpoints gets `403`, and deactivated domain returns `403`.
  - `test_t018_last_admin_guard_root_admin_guard_and_audit_log`: Verifies root admin cannot be deactivated/demoted/removed (`409`), last active admin cannot be removed/deactivated (`409`), and every access change writes an `audit_log` row.
