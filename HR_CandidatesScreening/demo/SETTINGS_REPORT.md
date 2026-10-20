# Default Screening Settings Panel Refactor Report

## Summary of What Moved Where

Per owner feedback, the **Default Screening Settings** panel was refactored so it is no longer permanently pinned open beside the Jobs page:

1. **Top Bar (`header.topbar > .topbar-actions` in [`index.html`](file:///home/ubuntu/candidates_screening/screening_webapp/static/index.html))**:
   - Added a **`Default settings`** toggle button (`#btn-default-settings`, `aria-expanded="false"`, `aria-controls="settings-panel"`) directly next to the theme switch (`#theme-select`).
   - Added a live single-line summary pill (`#settings-summary`) shown whenever the panel is folded:
     `Threshold 70 · gemini-4-argon · Redaction on`
   - As settings are loaded or saved via [`loadSettings()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L477-L497) and [`saveSettings()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L499-L525), [`updateSettingsSummary()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L360-L366) updates this summary line automatically.

2. **Foldable Default Settings Panel (`aside#settings-panel` in [`index.html`](file:///home/ubuntu/candidates_screening/screening_webapp/static/index.html) & [`styles.css`](file:///home/ubuntu/candidates_screening/screening_webapp/static/styles.css))**:
   - Moved `#settings-panel` out of the permanent 2-column `.app-layout` sidebar into a collapsible top drawer (`class="settings-panel collapsed hidden"`, `data-folded="true"`, `aria-hidden="true"`), folded away by default.
   - Added a **`Fold panel`** button (`#btn-close-settings`) inside the panel header and wired [`setSettingsPanelFolded()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L381-L399) to toggle the panel open/closed.
   - Kept all default screening controls working (`#setting-threshold`, `#setting-continuity`, `#setting-model`, `#setting-redact`, and `#btn-save-settings`), and synced saved defaults to the Create Job form via [`syncJobFormDefaults()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L368-L379).

3. **Removed from Settings Panel**:
   - **Removed `#btn-run-screening` ("Run screening")** from the settings panel (and removed `#btn-run-selected-job` from the Results toolbar) so screening runs per job from the Jobs page only.
   - **Removed `#setting-app-dir` ("Active Job / Folder")** from the settings panel. Each job row in [`loadJobs()`](file:///home/ubuntu/candidates_screening/screening_webapp/static/app.js#L240-L352) now displays its folder (`📁 <applications_dir>`) directly in the Candidates column.

4. **Jobs Page (`section#tab-jobs` in [`index.html`](file:///home/ubuntu/candidates_screening/screening_webapp/static/index.html))**:
   - Changed `.app-layout` from `grid-template-columns: 260px 1fr` to `grid-template-columns: 1fr` in [`styles.css`](file:///home/ubuntu/candidates_screening/screening_webapp/static/styles.css).
   - The Jobs page now displays only the **Create a New Screening Job** form and the **All Screening Jobs** list (with the active run progress indicator `#run-progress-box` shown only during an active run).

## Test Verification

- Added [`test_settings_panel_folded_by_default_and_new_jobs_use_saved_defaults`](file:///home/ubuntu/candidates_screening/screening_webapp/tests/test_webapp.py#L1050-L1119) in [`test_webapp.py`](file:///home/ubuntu/candidates_screening/screening_webapp/tests/test_webapp.py).
- Executed the full test suite across `screening_agent/tests` and `screening_webapp/tests` (`27 passed`).
