# T017 - Explain and fix "Access denied ... is not in the HR allow-list" on local sign-in

## What the user saw
Google sign-in succeeded for guruprem.saginadham@sybyl.com, but the web app returned:
"Access denied: 'guruprem.saginadham@sybyl.com' is not in the HR allow-list."

## Why it happened (explain this in your report)
- Google sign-in verified the user's identity correctly. The denial comes AFTER that, from the app's own allow-list check.
- The local demo run uses screening_webapp/config/demo_allowed_emails.json (set by run_demo.sh and by the start command the user runs).
  That file contains only hr.demo@example.com, so any real Google account is refused. This is the intended behaviour of the allow-list
  (empty or unknown means no access), so the security rule is working. The problem is only that the local demo has no real HR user in it.
- The Google Client ID was also accepted, so the OAuth configuration is correct for http://localhost:8080.

## What to do
1. Add guruprem.saginadham@sybyl.com to screening_webapp/config/demo_allowed_emails.json (local demo list only).
   Keep screening_webapp/config/allowed_emails.json (production list) EMPTY. Do not add any other real person.
2. Make the denial message more helpful: show the email, say that the account signed in fine, and say the admin must add the email to the
   allow-list file named in the settings. Do not show the full allow-list or any internal path.
3. Add a test: a verified token for an email in the demo list -> 200; for an email not in the list -> 403 with the new message.
4. Check the start command works on Windows as well as Linux: the user runs on Windows PowerShell with
   $env:DEMO_TEST_AUTH="1"; $env:ALLOWED_EMAILS_FILE="screening_webapp\config\demo_allowed_emails.json"; python -m screening_webapp
   Make sure the paths in run_demo.sh and the README match this, and say so in the README (Windows section).
5. Keep the Google Client ID as it is. Never store a client secret.

## Rules
- Work only inside ~/candidates_screening. No keys or secrets in files or messages.
- Do not publish or deploy.
- All existing tests (agent and web app) must still pass.

## Done means
- The demo allow-list contains the user's email, the production list is still empty.
- Tests pass (show the summary).
- Final message explains the cause in plain language and lists the files changed.
