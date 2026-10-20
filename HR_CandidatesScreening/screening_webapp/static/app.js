/* HR Candidate Screening Web Application Frontend Logic (T016, T017, T018, T019)
   Plain vanilla JS, no build step required.
*/

let idToken = sessionStorage.getItem("hr_google_id_token") || "";
let activePollTimer = null;
let currentUserIsAdmin = false;

let allJobs = [];
let activeJobId = "";
let resultsPage = 1;
const resultsPageSize = 25;
let resultsTotalPages = 1;

function showToast(message, isError = false) {
  const el = document.getElementById("global-toast");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden", "error");
  if (isError) {
    el.classList.add("error");
  }
  setTimeout(() => {
    el.classList.add("hidden");
  }, 4500);
}

function showSignInError(message) {
  const el = document.getElementById("signin-error");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden");
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function fileIcon(type) {
  const t = String(type || "").toLowerCase();
  if (t.includes("cv")) return "📄";
  if (t.includes("cover")) return "✉️";
  if (t.includes("email")) return "📧";
  return "📎";
}

async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (idToken) {
    headers["Authorization"] = `Bearer ${idToken}`;
  }
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body && !isFormData && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(path, Object.assign({}, options, { headers }));
  if (resp.status === 401 || (resp.status === 403 && !options.skipLogoutOn403)) {
    let errText = "Authentication failed.";
    try {
      const errData = await resp.json();
      errText = errData.detail || errText;
    } catch (_) {}
    handleLogout(errText);
    throw new Error(errText);
  }
  return resp;
}

// Google Identity Services callback
window.handleGoogleCredentialResponse = async function (response) {
  if (response && response.credential) {
    await completeSignIn(response.credential);
  }
};

window.signInDemo = async function () {
  try {
    const resp = await fetch("/api/auth/demo", { method: "POST" });
    const data = await resp.json();
    if (!resp.ok || !data.token) {
      throw new Error(data.detail || "Demo SSO sign-in failed.");
    }
    await completeSignIn(data.token);
    if (typeof switchTab === "function") {
      switchTab("results");
    }
  } catch (err) {
    showSignInError(err.message || "Demo SSO sign-in failed.");
  }
};

window.signInWithWorkEmail = async function (ev) {
  if (ev) ev.preventDefault();
  const input = document.getElementById("sso-email-input");
  const email = input ? input.value.trim() : "";
  if (!email) return;
  try {
    const resp = await fetch("/api/auth/sso-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await resp.json();
    if (!resp.ok || !data.token) {
      throw new Error(data.detail || "Work email SSO sign-in failed.");
    }
    await completeSignIn(data.token);
  } catch (err) {
    showSignInError(err.message || "Work email SSO sign-in failed.");
  }
};

async function completeSignIn(token) {
  idToken = token;
  sessionStorage.setItem("hr_google_id_token", token);
  const errEl = document.getElementById("signin-error");
  if (errEl) errEl.classList.add("hidden");

  try {
    const resp = await apiFetch("/api/me");
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Unable to sign in.");
    }
    const profile = await resp.json();
    currentUserIsAdmin = Boolean(profile.is_admin || profile.role === "admin");

    const userPill = document.getElementById("signed-in-user");
    const emailText = profile.email || "HR User";
    if (profile.is_root_admin) {
      userPill.textContent = `${emailText} (Root Admin)`;
    } else if (currentUserIsAdmin) {
      userPill.textContent = `${emailText} (Admin)`;
    } else {
      userPill.textContent = `${emailText} (HR)`;
    }

    const accessTabBtn = document.getElementById("tab-btn-access");
    if (accessTabBtn) {
      if (currentUserIsAdmin) {
        accessTabBtn.classList.remove("hidden");
      } else {
        accessTabBtn.classList.add("hidden");
        const accessPanel = document.getElementById("tab-access");
        if (accessPanel && !accessPanel.classList.contains("hidden")) {
          switchTab("jobs");
        }
      }
    }

    document.getElementById("signin-view").classList.add("hidden");
    document.getElementById("app-view").classList.remove("hidden");

    await loadSettings();
    await loadJobs();
    const tasks = [
      loadCandidates(),
      loadLatestResults(),
      loadHistory(),
    ];
    if (currentUserIsAdmin) {
      tasks.push(loadAccessControl());
    }
    await Promise.all(tasks);
  } catch (err) {
    showSignInError(err.message || "Sign-in failed.");
  }
}

function handleLogout(errorMessage = "") {
  idToken = "";
  currentUserIsAdmin = false;
  sessionStorage.removeItem("hr_google_id_token");
  if (activePollTimer) {
    clearInterval(activePollTimer);
    activePollTimer = null;
  }
  const accessTabBtn = document.getElementById("tab-btn-access");
  if (accessTabBtn) accessTabBtn.classList.add("hidden");
  document.getElementById("app-view").classList.add("hidden");
  document.getElementById("signin-view").classList.remove("hidden");
  if (errorMessage) {
    showSignInError(errorMessage);
  }
}

function updateActiveJobDisplays() {
  const topBadge = document.getElementById("topbar-active-job");
  const resultsBadge = document.getElementById("results-active-job-badge");
  const jobObj = allJobs.find((j) => j.job_id === activeJobId);

  if (jobObj) {
    const label = `${jobObj.job_id} — ${jobObj.title}`;
    if (topBadge) {
      topBadge.textContent = label;
      topBadge.classList.remove("hidden");
    }
    if (resultsBadge) {
      resultsBadge.textContent = label;
    }
  } else {
    if (topBadge) topBadge.classList.add("hidden");
    if (resultsBadge) resultsBadge.textContent = "No Job Selected";
  }

  const candSel = document.getElementById("candidates-job-select");
  if (candSel && candSel.value !== activeJobId) {
    candSel.value = activeJobId;
  }
  const resSel = document.getElementById("results-job-select");
  if (resSel && resSel.value !== activeJobId) {
    resSel.value = activeJobId;
  }
}

async function selectActiveJob(jobId, reloadViews = true) {
  activeJobId = jobId || "";
  resultsPage = 1;
  updateActiveJobDisplays();
  if (reloadViews) {
    await Promise.all([loadCandidates(), loadLatestResults(), loadHistory()]);
  }
}

function populateJobSelectors() {
  const searchInput = document.getElementById("results-job-search");
  const query = (searchInput ? searchInput.value : "").trim().toLowerCase();

  const filteredJobs = allJobs.filter((j) => {
    if (!query) return true;
    return (
      String(j.job_id || "").toLowerCase().includes(query) ||
      String(j.title || "").toLowerCase().includes(query)
    );
  });

  const candSel = document.getElementById("candidates-job-select");
  if (candSel) {
    if (allJobs.length === 0) {
      candSel.innerHTML = `<option value="">No jobs created yet</option>`;
    } else {
      candSel.innerHTML = allJobs
        .map(
          (j) =>
            `<option value="${escapeHtml(j.job_id)}" ${j.job_id === activeJobId ? "selected" : ""}>${escapeHtml(j.job_id)} — ${escapeHtml(j.title)} (${escapeHtml(j.candidate_count)} candidates)</option>`
        )
        .join("");
    }
  }

  const resSel = document.getElementById("results-job-select");
  if (resSel) {
    if (filteredJobs.length === 0) {
      resSel.innerHTML = `<option value="">No matching jobs</option>`;
    } else {
      resSel.innerHTML = filteredJobs
        .map(
          (j) =>
            `<option value="${escapeHtml(j.job_id)}" ${j.job_id === activeJobId ? "selected" : ""}>${escapeHtml(j.job_id)} — ${escapeHtml(j.title)} (${escapeHtml(j.candidate_count)} candidates)</option>`
        )
        .join("");
    }
  }

  updateActiveJobDisplays();
}

async function loadJobs() {
  const resp = await apiFetch("/api/jobs");
  if (!resp.ok) return;
  const data = await resp.json();
  allJobs = data.jobs || [];

  if (allJobs.length > 0 && (!activeJobId || !allJobs.some((j) => j.job_id === activeJobId))) {
    activeJobId = allJobs[0].job_id;
  }

  populateJobSelectors();

  const tbody = document.getElementById("jobs-tbody");
  if (!tbody) return;

  if (allJobs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">
          No jobs created yet. Use the form above to create a job with a Job Description and CV folder.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = allJobs
    .map((j) => {
      const isSelected = j.job_id === activeJobId;
      let lastRunHtml = `<span class="badge badge-ai">Not run yet</span>`;
      if (j.latest_run) {
        const st = j.latest_run.status;
        const cls =
          st === "finished"
            ? "badge-shortlist"
            : st === "running"
            ? "badge-review"
            : "badge-not-shortlist";
        lastRunHtml = `<span class="badge ${cls}">${escapeHtml(st)} (${escapeHtml(j.latest_run.id)})</span>`;
      }

      return `
        <tr class="${isSelected ? "row-needs-review" : ""}">
          <td>
            <span class="badge badge-hr">${escapeHtml(j.job_id)}</span>
          </td>
          <td>
            <strong>${escapeHtml(j.title)}</strong>
            <div class="folder-tag">Created ${escapeHtml(j.created_at_utc)}</div>
          </td>
          <td>
            <span class="doc-badge">📄 ${escapeHtml(j.jd_filename || "job_advert.docx")}</span>
          </td>
          <td>
            <span class="doc-badge">👥 ${escapeHtml(j.candidate_count)} candidates</span>
            <div class="folder-tag" title="${escapeHtml(j.applications_dir || "")}">📁 ${escapeHtml(j.applications_dir || "")}</div>
          </td>
          <td>
            <span class="folder-tag">
              Threshold: <strong>${escapeHtml(j.threshold)}/100</strong> &bull;
              Continuity: <strong>${j.requires_continuity ? "Yes" : "No"}</strong> &bull;
              Model: <strong>${escapeHtml(j.model)}</strong>
            </span>
          </td>
          <td>${lastRunHtml}</td>
          <td>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="btn btn-primary btn-xs btn-job-run" data-jid="${escapeHtml(j.job_id)}">
                Run screening
              </button>
              <button type="button" class="btn btn-outline btn-xs btn-job-results" data-jid="${escapeHtml(j.job_id)}">
                Results
              </button>
              <button type="button" class="btn btn-outline btn-xs btn-job-candidates" data-jid="${escapeHtml(j.job_id)}">
                Candidates
              </button>
              <button type="button" class="btn btn-outline btn-xs btn-job-export" data-jid="${escapeHtml(j.job_id)}">
                Excel
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll(".btn-job-run").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const jid = btn.getAttribute("data-jid");
      await selectActiveJob(jid, false);
      await triggerScreeningRun(jid);
    });
  });

  tbody.querySelectorAll(".btn-job-results").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const jid = btn.getAttribute("data-jid");
      await selectActiveJob(jid, true);
      switchTab("results");
    });
  });

  tbody.querySelectorAll(".btn-job-candidates").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const jid = btn.getAttribute("data-jid");
      await selectActiveJob(jid, true);
      switchTab("candidates");
    });
  });

  tbody.querySelectorAll(".btn-job-export").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const jid = btn.getAttribute("data-jid");
      await downloadExcel(jid);
    });
  });
}

function formatSettingsSummary(threshold, model) {
  const cleanThreshold = Math.round(Number(threshold ?? 70));
  const cleanModel = model || "gemini-4-argon";
  return `Threshold ${cleanThreshold} · ${cleanModel} · Redaction on`;
}

function updateSettingsSummary() {
  const summaryEl = document.getElementById("settings-summary");
  if (!summaryEl) return;
  const threshold = document.getElementById("setting-threshold")?.value ?? 70;
  const model = document.getElementById("setting-model")?.value || "gemini-4-argon";
  summaryEl.textContent = formatSettingsSummary(threshold, model);
}

function syncJobFormDefaults(threshold, requiresContinuity, model) {
  const jobSlider = document.getElementById("new-job-threshold");
  const jobSliderDisp = document.getElementById("new-job-threshold-display");
  if (jobSlider && jobSliderDisp) {
    jobSlider.value = threshold ?? 70;
    jobSliderDisp.textContent = `${jobSlider.value} / 100`;
  }
  const jobCont = document.getElementById("new-job-continuity");
  if (jobCont) jobCont.checked = Boolean(requiresContinuity);
  const jobModel = document.getElementById("new-job-model");
  if (jobModel) jobModel.value = model || "gemini-4-argon";
}

function setSettingsPanelFolded(folded) {
  const panel = document.getElementById("settings-panel");
  const toggleBtn = document.getElementById("btn-default-settings");
  const summaryEl = document.getElementById("settings-summary");
  if (!panel) return;

  const isFolded = Boolean(folded);
  panel.classList.toggle("collapsed", isFolded);
  panel.classList.toggle("hidden", isFolded);
  panel.setAttribute("data-folded", isFolded ? "true" : "false");
  panel.setAttribute("aria-hidden", isFolded ? "true" : "false");

  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", isFolded ? "false" : "true");
  }
  if (summaryEl) {
    summaryEl.classList.toggle("hidden", !isFolded);
  }
}

async function createNewJob(andRun = false) {
  const titleEl = document.getElementById("new-job-title");
  const jdFileEl = document.getElementById("new-job-jd-file");
  const cvFolderEl = document.getElementById("new-job-cv-folder");
  const serverDirEl = document.getElementById("new-job-server-dir");
  const thresholdEl = document.getElementById("new-job-threshold");
  const continuityEl = document.getElementById("new-job-continuity");
  const modelEl = document.getElementById("new-job-model");

  const title = (titleEl ? titleEl.value : "").trim() || "Sales Executive - Retail and Business Clients";
  const threshold = Number(thresholdEl ? thresholdEl.value : 70);
  const requiresContinuity = Boolean(continuityEl && continuityEl.checked);
  const model = modelEl ? modelEl.value : "gemini-4-argon";
  const serverDir = (serverDirEl ? serverDirEl.value : "").trim();

  const formData = new FormData();
  formData.append("title", title);
  formData.append("threshold", String(threshold));
  formData.append("requires_continuity", requiresContinuity ? "true" : "false");
  formData.append("model", model);
  if (serverDir) {
    formData.append("applications_dir", serverDir);
  }

  if (jdFileEl && jdFileEl.files && jdFileEl.files.length > 0) {
    formData.append("jd_file", jdFileEl.files[0]);
  }

  if (cvFolderEl && cvFolderEl.files && cvFolderEl.files.length > 0) {
    for (const file of cvFolderEl.files) {
      formData.append("cv_files", file);
      formData.append("cv_paths", file.webkitRelativePath || file.name);
    }
  }

  const createBtn = document.getElementById("btn-create-job");
  const createRunBtn = document.getElementById("btn-create-and-run-job");
  if (createBtn) createBtn.disabled = true;
  if (createRunBtn) createRunBtn.disabled = true;

  try {
    const resp = await apiFetch("/api/jobs", {
      method: "POST",
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      showToast(err.detail || "Could not create job.", true);
      return;
    }
    const created = await resp.json();
    const job = created.job || created;
    showToast(`Created job ${job.job_id}: ${job.title}`);

    if (titleEl) titleEl.value = "";
    if (jdFileEl) jdFileEl.value = "";
    if (cvFolderEl) cvFolderEl.value = "";
    const countBadge = document.getElementById("new-job-cv-count");
    if (countBadge) countBadge.textContent = "0 files selected";

    // Reset Create Job form settings back to current saved default settings
    syncJobFormDefaults(
      document.getElementById("setting-threshold")?.value ?? 70,
      document.getElementById("setting-continuity")?.checked ?? false,
      document.getElementById("setting-model")?.value || "gemini-4-argon"
    );

    activeJobId = job.job_id;
    await loadJobs();
    await Promise.all([loadCandidates(), loadLatestResults(), loadHistory()]);

    if (andRun) {
      await triggerScreeningRun(job.job_id);
    }
  } finally {
    if (createBtn) createBtn.disabled = false;
    if (createRunBtn) createRunBtn.disabled = false;
  }
}

async function loadSettings() {
  const resp = await apiFetch("/api/settings");
  if (!resp.ok) return;
  const s = await resp.json();

  const slider = document.getElementById("setting-threshold");
  const display = document.getElementById("threshold-display");
  if (slider && display) {
    slider.value = s.threshold ?? 70;
    display.textContent = `${slider.value} / 100`;
  }

  const contEl = document.getElementById("setting-continuity");
  if (contEl) contEl.checked = Boolean(s.requires_continuity);
  const modelEl = document.getElementById("setting-model");
  if (modelEl) modelEl.value = s.model || "gemini-4-argon";

  updateSettingsSummary();
  syncJobFormDefaults(s.threshold ?? 70, s.requires_continuity, s.model || "gemini-4-argon");
}

async function saveSettings(silent = false) {
  const threshold = Number(document.getElementById("setting-threshold").value);
  const requires_continuity = Boolean(document.getElementById("setting-continuity").checked);
  const model = document.getElementById("setting-model").value;

  const resp = await apiFetch("/api/settings", {
    method: "PUT",
    body: JSON.stringify({
      threshold,
      requires_continuity,
      model,
      redact_before_scoring: true,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json();
    showToast(err.detail || "Could not save settings.", true);
    return false;
  }
  updateSettingsSummary();
  syncJobFormDefaults(threshold, requires_continuity, model);
  if (!silent) {
    showToast("Default settings saved.");
    await loadHistory();
  }
  return true;
}

async function openCandidatePreviewModal(candidateId, jobId) {
  const modal = document.getElementById("doc-preview-modal");
  const titleEl = document.getElementById("doc-modal-title");
  const bodyEl = document.getElementById("doc-modal-body");
  if (!modal || !titleEl || !bodyEl) return;

  titleEl.textContent = `Loading documents for ${candidateId}...`;
  bodyEl.innerHTML = `<p style="color: var(--text-muted);">Loading preview...</p>`;
  modal.classList.remove("hidden");

  const url = jobId
    ? `/api/jobs/${encodeURIComponent(jobId)}/folders/${encodeURIComponent(candidateId)}/preview`
    : `/api/folders/${encodeURIComponent(candidateId)}/preview`;
  const pResp = await apiFetch(url);
  if (!pResp.ok) {
    bodyEl.innerHTML = `<p style="color: var(--danger-text);">Failed to load document preview.</p>`;
    return;
  }
  const pData = await pResp.json();
  titleEl.textContent = `${pData.name} (${pData.candidate_id}) — ${pData.folder_name}`;
  const files = pData.files || [];
  if (files.length === 0) {
    bodyEl.innerHTML = `<p style="color: var(--text-muted);">No readable documents found in this folder.</p>`;
    return;
  }
  bodyEl.innerHTML = files
    .map(
      (f) => `
      <div class="cv-preview-file">
        <h4>${fileIcon(f.type)} ${escapeHtml(f.type)} — ${escapeHtml(f.name)}</h4>
        <p class="cv-preview-text">${escapeHtml(f.preview)}${f.truncated ? "\n\n[Preview truncated at 1,500 characters]" : ""}</p>
      </div>
    `
    )
    .join("");
}

async function loadCandidates() {
  const url = activeJobId
    ? `/api/jobs/${encodeURIComponent(activeJobId)}/folders`
    : `/api/folders`;
  const resp = await apiFetch(url);
  if (!resp.ok) return;
  const data = await resp.json();

  const folders = data.folders || [];
  const countBadge = document.getElementById("candidates-count-badge");
  if (countBadge) {
    countBadge.textContent = `${folders.length} ${folders.length === 1 ? "candidate" : "candidates"}`;
  }

  const container = document.getElementById("candidates-list");
  if (!container) return;
  container.innerHTML = "";

  if (folders.length === 0) {
    container.innerHTML = `
      <div class="table-card" style="padding: 24px; text-align: center; color: var(--text-muted); grid-column: 1 / -1;">
        No candidate folders found for this job. Create a job and upload a CV folder on the <strong>1. Jobs</strong> tab.
      </div>
    `;
    return;
  }

  for (const folder of folders) {
    const card = document.createElement("div");
    card.className = "candidate-card";
    const docLabel =
      folder.documents_label ||
      `${folder.document_count ?? (folder.files || []).length} ${(folder.document_count ?? (folder.files || []).length) === 1 ? "document" : "documents"}`;

    card.innerHTML = `
      <div class="candidate-card-header">
        <div>
          <h3>${escapeHtml(folder.name)} <span style="color: var(--text-muted); font-weight: 500;">(${escapeHtml(folder.candidate_id)})</span></h3>
          <div class="folder-tag">Folder: ${escapeHtml(folder.folder_name)}</div>
        </div>
      </div>
      <div class="candidate-card-footer">
        <span class="doc-badge" title="Number of uploaded documents">📎 ${escapeHtml(docLabel)}</span>
        <button type="button" class="btn btn-outline btn-xs btn-view-cv" data-cid="${escapeHtml(folder.candidate_id)}">
          View
        </button>
      </div>
    `;

    container.appendChild(card);
  }

  container.querySelectorAll(".btn-view-cv").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cid = btn.getAttribute("data-cid");
      await openCandidatePreviewModal(cid, activeJobId);
    });
  });
}

function statusBadgeClass(badge) {
  const b = String(badge || "").toLowerCase();
  if (b.includes("needs your review")) return "badge-review";
  if (b.includes("you decided")) return "badge-hr";
  return "badge-ai";
}

async function loadLatestResults() {
  const needsReviewOnly = Boolean(
    document.getElementById("results-needs-review-only")?.checked
  );
  const searchVal = (
    document.getElementById("results-candidate-search")?.value || ""
  ).trim();
  const sortBy = document.getElementById("results-sort-by")?.value || "needs_review";

  const params = new URLSearchParams({
    needs_review_only: needsReviewOnly ? "true" : "false",
    search: searchVal,
    sort_by: sortBy,
    page: String(resultsPage),
    page_size: String(resultsPageSize),
  });

  const url = activeJobId
    ? `/api/jobs/${encodeURIComponent(activeJobId)}/results?${params.toString()}`
    : `/api/runs/latest/results?${params.toString()}`;

  const resp = await apiFetch(url);
  if (!resp.ok) return;
  const data = await resp.json();

  const summary = data.summary || {};
  document.getElementById("sum-total").textContent = summary.total_candidates ?? 0;
  document.getElementById("sum-review").textContent = summary.needs_review ?? 0;
  document.getElementById("sum-ai").textContent = summary.ai_decided ?? 0;
  document.getElementById("sum-hr").textContent = summary.hr_decided ?? 0;

  const pagination = data.pagination || {
    page: 1,
    page_size: resultsPageSize,
    total_items: (data.results || []).length,
    total_pages: 1,
  };
  resultsPage = pagination.page || 1;
  resultsTotalPages = pagination.total_pages || 1;

  const pageInfo = document.getElementById("results-page-info");
  const prevBtn = document.getElementById("btn-page-prev");
  const nextBtn = document.getElementById("btn-page-next");
  if (pageInfo) {
    const totalItems = pagination.total_items ?? 0;
    const startIdx = totalItems === 0 ? 0 : (resultsPage - 1) * resultsPageSize + 1;
    const endIdx = Math.min(totalItems, resultsPage * resultsPageSize);
    pageInfo.textContent = `Showing ${startIdx}–${endIdx} of ${totalItems} candidates (Page ${resultsPage} of ${resultsTotalPages}, ${resultsPageSize} per page)`;
  }
  if (prevBtn) prevBtn.disabled = resultsPage <= 1;
  if (nextBtn) nextBtn.disabled = resultsPage >= resultsTotalPages;

  const tbody = document.getElementById("results-tbody");
  const results = data.results || [];
  if (results.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 28px;">
          No screening results match the current job or filters. Click "Run screening" to evaluate candidates for this job.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = results
    .map((r) => {
      const isReview = r.status_badge === "Needs your review";
      const aiRecBadge =
        r.ai_decision === "Shortlisted" ? "badge-shortlist" : "badge-not-shortlist";
      const reasonsText = (r.review_reasons_plain || []).join(" • ");
      const fullWhy = r.why || r.why_full || r.why_plain || "";
      const shortWhy = r.why_short || fullWhy;
      const showReadMore = Boolean(r.why_truncated || fullWhy.length > 120);
      const docLabel =
        r.documents_label ||
        `${r.document_count ?? 1} ${(r.document_count ?? 1) === 1 ? "document" : "documents"}`;
      const rowJobId = r.job_id || activeJobId || "";

      let hrDecisionHtml = `<div class="current-decision-note">Decision: <strong>${escapeHtml(r.final_decision)}</strong></div>`;
      if (r.hr_decision) {
        hrDecisionHtml = `
          <div class="current-decision-note">
            <strong>${escapeHtml(r.hr_decision.decision)}</strong> by ${escapeHtml(r.hr_decision.decided_by_email)}
            ${r.hr_decision.note ? `<br/><em>Note: ${escapeHtml(r.hr_decision.note)}</em>` : ""}
          </div>
        `;
      }

      return `
        <tr class="${isReview ? "row-needs-review" : ""}">
          <td>
            <strong>${escapeHtml(r.name)}</strong>
            <div class="folder-tag">${escapeHtml(r.candidate_id)} ${rowJobId ? `&bull; ${escapeHtml(rowJobId)}` : ""}</div>
          </td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="doc-badge" title="Documents in candidate folder">📎 ${escapeHtml(docLabel)}</span>
              <button type="button" class="btn btn-outline btn-xs btn-preview-docs"
                      data-cid="${escapeHtml(r.candidate_id)}"
                      data-jid="${escapeHtml(rowJobId)}">
                View
              </button>
            </div>
          </td>
          <td>
            <strong style="font-size: 14px;">${escapeHtml(r.score_display)}</strong>
            <div class="folder-tag">Conf: ${escapeHtml(r.confidence_percent)}%</div>
          </td>
          <td>
            <span class="badge ${aiRecBadge}">
              ${escapeHtml(r.ai_recommendation_plain)}
            </span>
          </td>
          <td class="why-cell">
            ${reasonsText ? `<div class="why-reason-tag">${escapeHtml(reasonsText)}</div>` : ""}
            <div id="why-box-${escapeHtml(r.candidate_id)}"
                 class="why-text-container why-clamped"
                 data-short="${escapeHtml(shortWhy)}"
                 data-full="${escapeHtml(fullWhy)}">${escapeHtml(shortWhy)}</div>
            ${
              showReadMore
                ? `<button type="button" class="btn-link btn-toggle-why" data-cid="${escapeHtml(r.candidate_id)}" data-expanded="false">Read more</button>`
                : ""
            }
          </td>
          <td>
            <span class="badge ${statusBadgeClass(r.status_badge)}">
              ${escapeHtml(r.status_badge)}
            </span>
          </td>
          <td>
            <div class="decision-controls">
              <div class="decision-btn-row">
                <button type="button" class="btn btn-shortlist btn-xs btn-decide"
                        data-cid="${escapeHtml(r.candidate_id)}"
                        data-jid="${escapeHtml(rowJobId)}"
                        data-decision="Shortlisted">
                  Shortlist
                </button>
                <button type="button" class="btn btn-reject btn-xs btn-decide"
                        data-cid="${escapeHtml(r.candidate_id)}"
                        data-jid="${escapeHtml(rowJobId)}"
                        data-decision="Not Shortlisted">
                  Not shortlist
                </button>
              </div>
              <input type="text"
                     id="note-${escapeHtml(r.candidate_id)}"
                     class="text-input"
                     placeholder="Optional note..."
                     value="${escapeHtml(r.hr_decision?.note || "")}" />
              ${hrDecisionHtml}
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll(".btn-preview-docs").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cid = btn.getAttribute("data-cid");
      const jid = btn.getAttribute("data-jid") || activeJobId;
      await openCandidatePreviewModal(cid, jid);
    });
  });

  tbody.querySelectorAll(".btn-toggle-why").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cid = btn.getAttribute("data-cid");
      const whyBox = document.getElementById(`why-box-${cid}`);
      if (!whyBox) return;
      const expanded = btn.getAttribute("data-expanded") === "true";
      if (expanded) {
        whyBox.textContent = whyBox.getAttribute("data-short") || "";
        whyBox.classList.add("why-clamped");
        btn.setAttribute("data-expanded", "false");
        btn.textContent = "Read more";
      } else {
        whyBox.textContent = whyBox.getAttribute("data-full") || "";
        whyBox.classList.remove("why-clamped");
        btn.setAttribute("data-expanded", "true");
        btn.textContent = "Show less";
      }
    });
  });

  tbody.querySelectorAll(".btn-decide").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cid = btn.getAttribute("data-cid");
      const jid = btn.getAttribute("data-jid") || activeJobId;
      const decision = btn.getAttribute("data-decision");
      const noteInput = document.getElementById(`note-${cid}`);
      const note = noteInput ? noteInput.value : "";

      btn.disabled = true;
      try {
        const endpoint = jid
          ? `/api/jobs/${encodeURIComponent(jid)}/candidates/${encodeURIComponent(cid)}/decision`
          : `/api/candidates/${encodeURIComponent(cid)}/decision`;
        const dResp = await apiFetch(endpoint, {
          method: "POST",
          body: JSON.stringify({ decision, note, job_id: jid }),
        });
        if (!dResp.ok) {
          const err = await dResp.json();
          showToast(err.detail || "Could not record decision.", true);
          return;
        }
        showToast(`Recorded decision for ${cid} (${jid || "default"}): ${decision}`);
        await Promise.all([loadLatestResults(), loadHistory()]);
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function formatActionLabel(action) {
  if (action === "create_job") return "Job Created";
  if (action === "hr_decision") return "HR Decision Recorded";
  if (action === "start_run") return "Screening Run Started";
  if (action === "update_settings") return "Settings Updated";
  if (action === "migrate_allowlist") return "Initial Allow-List Migrated";
  if (action === "access_grant_user") return "User Access Granted";
  if (action === "access_revoke_user") return "User Access Deactivated";
  if (action === "access_remove_user") return "User Removed";
  if (action === "access_change_role") return "User Role Changed";
  if (action === "access_grant_domain") return "Domain Access Granted";
  if (action === "access_revoke_domain") return "Domain Access Deactivated";
  if (action === "access_remove_domain") return "Domain Removed";
  return action;
}

async function loadHistory() {
  const url = activeJobId
    ? `/api/history?job_id=${encodeURIComponent(activeJobId)}`
    : `/api/history`;
  const resp = await apiFetch(url);
  if (!resp.ok) return;
  const data = await resp.json();

  const runsTbody = document.getElementById("history-runs-tbody");
  const runs = data.runs || [];
  if (runs.length === 0) {
    runsTbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted);">No runs recorded yet.</td>
      </tr>
    `;
  } else {
    runsTbody.innerHTML = runs
      .map(
        (r) => `
        <tr>
          <td><strong>${escapeHtml(r.id)}</strong></td>
          <td><span class="badge badge-hr">${escapeHtml(r.job_id || "—")}</span></td>
          <td>${escapeHtml(r.started_at)}</td>
          <td>
            Model: <strong>${escapeHtml(r.model)}</strong> &bull;
            Threshold: <strong>${escapeHtml(r.threshold)}/100</strong> &bull;
            Continuity required: <strong>${r.requires_continuity ? "Yes" : "No"}</strong> &bull;
            Redaction: <strong>On</strong>
          </td>
          <td>${escapeHtml(r.candidate_count)}</td>
          <td>
            <span class="badge ${r.status === "finished" ? "badge-shortlist" : r.status === "running" ? "badge-review" : "badge-not-shortlist"}">
              ${escapeHtml(r.status)}
            </span>
          </td>
        </tr>
      `
      )
      .join("");
  }

  const auditTbody = document.getElementById("history-audit-tbody");
  const audits = data.audit_log || [];
  if (audits.length === 0) {
    auditTbody.innerHTML = `
      <tr>
        <td colspan="4" style="text-align: center; color: var(--text-muted);">No audit events recorded yet.</td>
      </tr>
    `;
  } else {
    auditTbody.innerHTML = audits
      .map(
        (a) => `
        <tr>
          <td>${escapeHtml(a.at_utc)}</td>
          <td>${escapeHtml(a.actor_email)}</td>
          <td><strong>${escapeHtml(formatActionLabel(a.action))}</strong></td>
          <td>${escapeHtml(a.detail)}</td>
        </tr>
      `
      )
      .join("");
  }
}

async function loadAccessControl() {
  if (!currentUserIsAdmin) return;
  const resp = await apiFetch("/api/admin/access", { skipLogoutOn403: true });
  if (!resp.ok) return;
  const data = await resp.json();

  const users = data.users || [];
  const domains = data.domains || [];
  const audits = data.audit_log || [];

  const activeAdminCount = users.filter((u) => u.active && u.role === "admin").length;

  const usersTbody = document.getElementById("access-users-tbody");
  if (usersTbody) {
    if (users.length === 0) {
      usersTbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted);">No users configured.</td>
        </tr>
      `;
    } else {
      usersTbody.innerHTML = users
        .map((u) => {
          const isRoot = Boolean(u.is_root_admin);
          const isLastActiveAdmin = Boolean(u.active && u.role === "admin" && activeAdminCount <= 1);
          const lockControls = isRoot || isLastActiveAdmin;

          let badgesHtml = "";
          if (isRoot) {
            badgesHtml += ` <span class="badge badge-hr">Root Admin (Locked)</span>`;
          }

          const roleSelectHtml = `
            <select class="select-input access-role-select"
                    data-uid="${escapeHtml(u.id)}"
                    style="width: auto; min-width: 110px;"
                    ${lockControls ? "disabled" : ""}>
              <option value="hr" ${u.role === "hr" ? "selected" : ""}>hr</option>
              <option value="admin" ${u.role === "admin" ? "selected" : ""}>admin</option>
            </select>
          `;

          const statusHtml = u.active
            ? `<span class="badge badge-shortlist">Active</span>`
            : `<span class="badge badge-not-shortlist">Deactivated</span>`;

          let actionsHtml = "";
          if (isRoot) {
            actionsHtml = `<span style="font-size: 12px; color: var(--text-muted);">Root admin cannot be deactivated</span>`;
          } else {
            const toggleLabel = u.active ? "Deactivate" : "Activate";
            const toggleClass = u.active ? "btn-reject" : "btn-shortlist";
            actionsHtml = `
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                <button type="button"
                        class="btn ${toggleClass} btn-xs btn-toggle-user"
                        data-uid="${escapeHtml(u.id)}"
                        data-next-active="${u.active ? "false" : "true"}"
                        ${isLastActiveAdmin && u.active ? "disabled title='Cannot deactivate the last active admin'" : ""}>
                  ${toggleLabel}
                </button>
                <button type="button"
                        class="btn btn-outline btn-xs btn-remove-user"
                        data-uid="${escapeHtml(u.id)}"
                        ${isLastActiveAdmin && u.active ? "disabled title='Cannot remove the last active admin'" : ""}>
                  Remove
                </button>
              </div>
            `;
          }

          return `
            <tr>
              <td>
                <strong>${escapeHtml(u.email)}</strong>${badgesHtml}
              </td>
              <td>${roleSelectHtml}</td>
              <td>${statusHtml}</td>
              <td>${escapeHtml(u.added_by)}</td>
              <td>${escapeHtml(u.added_at_utc)}</td>
              <td>${actionsHtml}</td>
            </tr>
          `;
        })
        .join("");

      usersTbody.querySelectorAll(".access-role-select").forEach((sel) => {
        sel.addEventListener("change", async () => {
          const uid = sel.getAttribute("data-uid");
          const role = sel.value;
          const r = await apiFetch(`/api/admin/users/${encodeURIComponent(uid)}`, {
            method: "PATCH",
            body: JSON.stringify({ role }),
            skipLogoutOn403: true,
          });
          if (!r.ok) {
            const err = await r.json();
            showToast(err.detail || "Could not change user role.", true);
            await loadAccessControl();
            return;
          }
          showToast(`Updated role to '${role}'.`);
          await Promise.all([loadAccessControl(), loadHistory()]);
        });
      });

      usersTbody.querySelectorAll(".btn-toggle-user").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const uid = btn.getAttribute("data-uid");
          const nextActive = btn.getAttribute("data-next-active") === "true";
          const r = await apiFetch(`/api/admin/users/${encodeURIComponent(uid)}`, {
            method: "PATCH",
            body: JSON.stringify({ active: nextActive }),
            skipLogoutOn403: true,
          });
          if (!r.ok) {
            const err = await r.json();
            showToast(err.detail || "Could not update user status.", true);
            return;
          }
          showToast(nextActive ? "User activated." : "User deactivated.");
          await Promise.all([loadAccessControl(), loadHistory()]);
        });
      });

      usersTbody.querySelectorAll(".btn-remove-user").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const uid = btn.getAttribute("data-uid");
          const r = await apiFetch(`/api/admin/users/${encodeURIComponent(uid)}`, {
            method: "DELETE",
            skipLogoutOn403: true,
          });
          if (!r.ok) {
            const err = await r.json();
            showToast(err.detail || "Could not remove user.", true);
            return;
          }
          showToast("User removed from allow-list.");
          await Promise.all([loadAccessControl(), loadHistory()]);
        });
      });
    }
  }

  const domainsTbody = document.getElementById("access-domains-tbody");
  if (domainsTbody) {
    if (domains.length === 0) {
      domainsTbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--text-muted);">No domain rules configured (empty by default).</td>
        </tr>
      `;
    } else {
      domainsTbody.innerHTML = domains
        .map((d) => {
          const statusHtml = d.active
            ? `<span class="badge badge-shortlist">Active</span>`
            : `<span class="badge badge-not-shortlist">Deactivated</span>`;
          const toggleLabel = d.active ? "Deactivate" : "Activate";
          const toggleClass = d.active ? "btn-reject" : "btn-shortlist";
          return `
            <tr>
              <td><strong>@${escapeHtml(d.domain)}</strong></td>
              <td><span class="badge badge-ai">${escapeHtml(d.role)}</span></td>
              <td>${statusHtml}</td>
              <td>${escapeHtml(d.added_by)}</td>
              <td>${escapeHtml(d.added_at_utc)}</td>
              <td>
                <button type="button"
                        class="btn ${toggleClass} btn-xs btn-toggle-domain"
                        data-did="${escapeHtml(d.id)}"
                        data-next-active="${d.active ? "false" : "true"}">
                  ${toggleLabel}
                </button>
              </td>
            </tr>
          `;
        })
        .join("");

      domainsTbody.querySelectorAll(".btn-toggle-domain").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const did = btn.getAttribute("data-did");
          const nextActive = btn.getAttribute("data-next-active") === "true";
          const r = await apiFetch(`/api/admin/domains/${encodeURIComponent(did)}`, {
            method: "PATCH",
            body: JSON.stringify({ active: nextActive }),
            skipLogoutOn403: true,
          });
          if (!r.ok) {
            const err = await r.json();
            showToast(err.detail || "Could not update domain status.", true);
            return;
          }
          showToast(nextActive ? "Domain rule activated." : "Domain rule deactivated.");
          await Promise.all([loadAccessControl(), loadHistory()]);
        });
      });
    }
  }

  const accessAuditTbody = document.getElementById("access-audit-tbody");
  if (accessAuditTbody) {
    if (audits.length === 0) {
      accessAuditTbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-muted);">No access events recorded yet.</td>
        </tr>
      `;
    } else {
      accessAuditTbody.innerHTML = audits
        .map(
          (a) => `
          <tr>
            <td>${escapeHtml(a.at_utc)}</td>
            <td>${escapeHtml(a.actor_email)}</td>
            <td><strong>${escapeHtml(formatActionLabel(a.action))}</strong></td>
            <td>${escapeHtml(a.detail)}</td>
          </tr>
        `
        )
        .join("");
    }
  }
}

async function addAccessUser() {
  const emailInput = document.getElementById("access-user-email");
  const roleSelect = document.getElementById("access-user-role");
  const email = (emailInput ? emailInput.value : "").trim();
  const role = roleSelect ? roleSelect.value : "hr";

  if (!email) {
    showToast("Please enter an email address.", true);
    return;
  }

  const resp = await apiFetch("/api/admin/users", {
    method: "POST",
    body: JSON.stringify({ email, role }),
    skipLogoutOn403: true,
  });
  if (!resp.ok) {
    const err = await resp.json();
    showToast(err.detail || "Could not add user.", true);
    return;
  }
  if (emailInput) emailInput.value = "";
  showToast(`Granted ${role} access to ${email}.`);
  await Promise.all([loadAccessControl(), loadHistory()]);
}

async function addAccessDomain() {
  const domainInput = document.getElementById("access-domain-name");
  const roleSelect = document.getElementById("access-domain-role");
  const domain = (domainInput ? domainInput.value : "").trim();
  const role = roleSelect ? roleSelect.value : "hr";

  if (!domain) {
    showToast("Please enter a domain name (e.g. example.gov).", true);
    return;
  }

  const resp = await apiFetch("/api/admin/domains", {
    method: "POST",
    body: JSON.stringify({ domain, role }),
    skipLogoutOn403: true,
  });
  if (!resp.ok) {
    const err = await resp.json();
    showToast(err.detail || "Could not add domain.", true);
    return;
  }
  if (domainInput) domainInput.value = "";
  showToast(`Granted ${role} access to domain ${domain}.`);
  await Promise.all([loadAccessControl(), loadHistory()]);
}

async function triggerScreeningRun(jobIdOverride = "") {
  const targetJobId =
    typeof jobIdOverride === "string" && jobIdOverride ? jobIdOverride : activeJobId;
  const progBox = document.getElementById("run-progress-box");
  const progLabel = document.getElementById("run-progress-label");
  const progFill = document.getElementById("run-progress-fill");

  if (progBox) progBox.classList.remove("hidden");
  if (progLabel) {
    progLabel.textContent = targetJobId
      ? `Starting screening for ${targetJobId}...`
      : "Starting screening run...";
  }
  if (progFill) progFill.style.width = "5%";

  const endpoint = targetJobId
    ? `/api/jobs/${encodeURIComponent(targetJobId)}/runs`
    : `/api/runs`;
  const resp = await apiFetch(endpoint, { method: "POST" });
  if (!resp.ok) {
    const err = await resp.json();
    showToast(err.detail || "Could not start screening run.", true);
    if (progBox) progBox.classList.add("hidden");
    return;
  }

  const runData = await resp.json();
  const runId = runData.run_id;
  if (runData.job_id) {
    activeJobId = runData.job_id;
  }

  if (activePollTimer) clearInterval(activePollTimer);
  activePollTimer = setInterval(async () => {
    try {
      const sResp = await apiFetch(`/api/runs/${encodeURIComponent(runId)}`);
      if (!sResp.ok) return;
      const st = await sResp.json();
      const idx = st.current_candidate_index ?? 0;
      const total = st.total_candidates ?? 0;
      const pct = st.progress_percent ?? 0;

      if (progFill) progFill.style.width = `${Math.max(10, pct)}%`;
      if (progLabel) {
        progLabel.textContent =
          st.status === "running"
            ? `Screening ${st.job_id || ""} (${idx} of ${total})...`
            : `Status: ${st.status}`;
      }

      if (st.status === "finished" || st.status === "failed") {
        clearInterval(activePollTimer);
        activePollTimer = null;
        if (progBox) setTimeout(() => progBox.classList.add("hidden"), 1200);

        if (st.status === "finished") {
          showToast(
            `Screening complete${st.job_id ? ` for ${st.job_id}` : ""}. Opening results.`
          );
          await loadJobs();
          await Promise.all([loadCandidates(), loadLatestResults(), loadHistory()]);
          switchTab("results");
        } else {
          showToast(`Screening failed: ${st.error || "Unknown error"}`, true);
          await Promise.all([loadJobs(), loadHistory()]);
        }
      }
    } catch (_) {}
  }, 400);
}

async function downloadExcel(jobIdOverride = "") {
  const targetJobId =
    typeof jobIdOverride === "string" && jobIdOverride ? jobIdOverride : activeJobId;
  const endpoint = targetJobId
    ? `/api/jobs/${encodeURIComponent(targetJobId)}/export.xlsx`
    : `/api/export.xlsx`;
  const resp = await apiFetch(endpoint);
  if (!resp.ok) {
    let msg = "Could not download Excel file.";
    try {
      const err = await resp.json();
      msg = err.detail || msg;
    } catch (_) {}
    showToast(msg, true);
    return;
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = targetJobId
    ? `screening_results_${targetJobId}.xlsx`
    : "screening_results.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `tab-${tabName}`);
  });
  if (tabName === "access" && currentUserIsAdmin) {
    loadAccessControl();
  }
}

function setupTheme() {
  const select = document.getElementById("theme-select");
  const savedTheme = localStorage.getItem("hr_theme_pref") || "system";
  select.value = savedTheme;
  applyTheme(savedTheme);

  select.addEventListener("change", () => {
    const val = select.value;
    localStorage.setItem("hr_theme_pref", val);
    applyTheme(val);
  });
}

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") {
    root.setAttribute("data-theme", theme);
  } else {
    root.removeAttribute("data-theme");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTheme();
  setSettingsPanelFolded(true);
  updateSettingsSummary();

  // Toggle folded Default Screening Settings panel from top bar
  document.getElementById("btn-default-settings")?.addEventListener("click", () => {
    const panel = document.getElementById("settings-panel");
    const currentlyFolded = !panel || panel.getAttribute("data-folded") === "true";
    setSettingsPanelFolded(!currentlyFolded);
  });

  document.getElementById("btn-close-settings")?.addEventListener("click", () => {
    setSettingsPanelFolded(true);
  });

  // Sliders live display
  const slider = document.getElementById("setting-threshold");
  const display = document.getElementById("threshold-display");
  if (slider && display) {
    slider.addEventListener("input", () => {
      display.textContent = `${slider.value} / 100`;
      updateSettingsSummary();
    });
  }

  document.getElementById("setting-model")?.addEventListener("change", () => {
    updateSettingsSummary();
  });

  const jobSlider = document.getElementById("new-job-threshold");
  const jobDisplay = document.getElementById("new-job-threshold-display");
  if (jobSlider && jobDisplay) {
    jobSlider.addEventListener("input", () => {
      jobDisplay.textContent = `${jobSlider.value} / 100`;
    });
  }

  // CV folder file count badge
  const cvFolderInput = document.getElementById("new-job-cv-folder");
  const cvCountBadge = document.getElementById("new-job-cv-count");
  if (cvFolderInput && cvCountBadge) {
    cvFolderInput.addEventListener("change", () => {
      const count = cvFolderInput.files ? cvFolderInput.files.length : 0;
      cvCountBadge.textContent = `${count} ${count === 1 ? "file" : "files"} selected`;
    });
  }

  // Tab buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      switchTab(btn.getAttribute("data-tab"));
    });
  });

  // Job creation & selection controls
  document.getElementById("btn-create-job")?.addEventListener("click", () => createNewJob(false));
  document.getElementById("btn-create-and-run-job")?.addEventListener("click", () => createNewJob(true));

  document.getElementById("candidates-job-select")?.addEventListener("change", async (e) => {
    await selectActiveJob(e.target.value, true);
  });

  document.getElementById("results-job-select")?.addEventListener("change", async (e) => {
    await selectActiveJob(e.target.value, true);
  });

  document.getElementById("results-job-search")?.addEventListener("input", () => {
    populateJobSelectors();
    const resSel = document.getElementById("results-job-select");
    if (resSel && resSel.value && resSel.value !== activeJobId) {
      selectActiveJob(resSel.value, true);
    }
  });

  // Results filter, search, sort & pagination
  document.getElementById("results-needs-review-only")?.addEventListener("change", () => {
    resultsPage = 1;
    loadLatestResults();
  });

  document.getElementById("results-sort-by")?.addEventListener("change", () => {
    resultsPage = 1;
    loadLatestResults();
  });

  document.getElementById("results-candidate-search")?.addEventListener("input", () => {
    resultsPage = 1;
    loadLatestResults();
  });

  document.getElementById("btn-page-prev")?.addEventListener("click", () => {
    if (resultsPage > 1) {
      resultsPage -= 1;
      loadLatestResults();
    }
  });

  document.getElementById("btn-page-next")?.addEventListener("click", () => {
    if (resultsPage < resultsTotalPages) {
      resultsPage += 1;
      loadLatestResults();
    }
  });

  // Document preview modal close
  const modal = document.getElementById("doc-preview-modal");
  document.getElementById("btn-close-doc-modal")?.addEventListener("click", () => {
    modal?.classList.add("hidden");
  });
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
    }
  });

  document.getElementById("btn-save-settings")?.addEventListener("click", () => saveSettings(false));
  document.getElementById("btn-export-excel")?.addEventListener("click", () => downloadExcel(activeJobId));
  document.getElementById("btn-logout")?.addEventListener("click", () => handleLogout());

  const addUserBtn = document.getElementById("btn-add-user");
  if (addUserBtn) {
    addUserBtn.addEventListener("click", addAccessUser);
  }
  const addDomainBtn = document.getElementById("btn-add-domain");
  if (addDomainBtn) {
    addDomainBtn.addEventListener("click", addAccessDomain);
  }

  if (idToken) {
    await completeSignIn(idToken);
  }
});
