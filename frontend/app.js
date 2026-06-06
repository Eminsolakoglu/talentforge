const API_BASE =
  window.location.protocol === "file:" || window.location.port === "5500"
    ? localStorage.getItem("talentforge_api_base") || "http://127.0.0.1:8010"
    : window.location.origin;

const state = {
  role: localStorage.getItem("talentforge_role") || "hr",
  token: localStorage.getItem("talentforge_token") || "",
  user: JSON.parse(localStorage.getItem("talentforge_user") || "null"),
  jobs: [],
  applications: [],
  dashboardSummary: null,
  recentSearch: JSON.parse(localStorage.getItem("talentforge_recent_search") || "null"),
  savedSearches: JSON.parse(localStorage.getItem("talentforge_saved_searches") || "[]"),
  savedCandidates: JSON.parse(localStorage.getItem("talentforge_saved_candidates") || "[]"),
  jobFilters: { title: "", seniority: "", location: "" },
  lastCandidates: new Map(),
};

const views = {
  landing: document.querySelector("#landing-view"),
  login: document.querySelector("#auth-view"),
  dashboard: document.querySelector("#dashboard-view"),
};

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

function setMessage(text, type = "ok") {
  const message = $(".auth-message");
  if (!message) return;
  message.textContent = text || "";
  message.dataset.type = type;
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error(`API'ye ulaşılamadı: ${API_BASE}`);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(formatApiError(data.detail));
  return data;
}

function formatApiError(detail) {
  if (!detail) return "İşlem tamamlanamadı";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .filter(Boolean)
      .join(" / ") || "İşlem tamamlanamadı";
  }
  if (typeof detail === "object") return detail.msg || detail.message || JSON.stringify(detail);
  return String(detail);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setUploadStatus(text, type = "") {
  const status = $("[data-upload-status]");
  if (!status) return;
  status.textContent = text;
  status.dataset.type = type;
}

function setUploadStep(activeStep = null, doneSteps = []) {
  $all("[data-upload-step]").forEach((step) => {
    step.classList.toggle("active", step.dataset.uploadStep === activeStep);
    step.classList.toggle("done", doneSteps.includes(step.dataset.uploadStep));
  });
}

function renderUploadResult(data) {
  const result = $("[data-upload-result]");
  if (!result) return;
  const candidateName = data.candidate_name || data.name || "Aday";
  const skills = (data.skills || []).map((skill) => skill.name || skill).filter(Boolean);
  const experiences = data.experiences || [];
  const educations = data.educations || [];
  const projects = data.projects || [];
  const certifications = data.certifications || [];
  const languages = data.languages || [];
  const companies = [...new Set(experiences.map((exp) => exp.company_name || exp.company).filter(Boolean))];
  const graphNodes = [
    { label: candidateName, type: "Candidate", x: 49, y: 48 },
    ...skills.slice(0, 12).map((label, index) => ({ label, type: "Skill", ...radialPoint(index, 12, 35, 44, 49, 48) })),
    ...experiences.slice(0, 4).map((exp, index) => ({ label: exp.role_title || exp.role || "Experience", type: "Experience", ...radialPoint(index + 1, 5, 25, 76, 49, 48) })),
    ...projects.slice(0, 4).map((project, index) => ({ label: project.name || "Project", type: "Project", ...radialPoint(index + 3, 8, 43, 30, 49, 48) })),
    ...companies.slice(0, 3).map((label, index) => ({ label, type: "Company", ...radialPoint(index + 2, 4, 31, 19, 49, 48) })),
    ...educations.slice(0, 2).map((edu, index) => ({ label: edu.institution || edu.institution_name || edu.degree || "Education", type: "Education", ...radialPoint(index + 3, 6, 30, 72, 49, 48) })),
    ...certifications.slice(0, 2).map((label, index) => ({ label: label.name || label, type: "Certification", ...radialPoint(index + 2, 7, 40, 64, 49, 48) })),
    ...languages.slice(0, 2).map((label, index) => ({ label: label.name || label, type: "Language", ...radialPoint(index + 4, 7, 26, 22, 49, 48) })),
  ].slice(0, 28);
  const relationshipCount =
    skills.length + experiences.length + projects.length + companies.length + educations.length + certifications.length + languages.length;
  const typeCounts = graphNodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {});
  const edges = graphNodes
    .slice(1)
    .map((node, index) => renderGraphEdge(graphNodes[0], node, index))
    .join("");

  result.innerHTML = `
    <div class="neo4j-preview" aria-label="Neo4j bilgi grafı önizleme">
      <div class="neo4j-toolbar">
        <span class="active">Graph</span>
        <span>Table</span>
        <span>RAW</span>
      </div>
      <div class="neo4j-canvas">
        ${edges}
        ${graphNodes
          .map(
            (node, index) => `
              <span
                class="neo-node ${node.type.toLowerCase()}"
                style="left:${node.x}%; top:${node.y}%; animation-delay:${index * 35}ms"
                title="${escapeHtml(node.type)}: ${escapeHtml(node.label)}"
              >
                ${escapeHtml(shortLabel(node.label))}
              </span>`
          )
          .join("")}
      </div>
    </div>
    <div class="neo4j-overview">
      <h3>Results overview</h3>
      <p>Nodes (${graphNodes.length})</p>
      <div class="overview-tags">
        ${Object.entries(typeCounts)
          .map(([type, count]) => `<span class="${type.toLowerCase()}">${escapeHtml(type)} (${count})</span>`)
          .join("")}
      </div>
      <p>Relationships (${relationshipCount})</p>
      <div class="overview-tags rels">
        <span>HAS_SKILL (${skills.length})</span>
        <span>HAS_EXPERIENCE (${experiences.length})</span>
        <span>HAS_PROJECT (${projects.length})</span>
        <span>AT_COMPANY (${companies.length})</span>
        <span>HAS_EDUCATION (${educations.length})</span>
        <span>HAS_CERTIFICATION (${certifications.length})</span>
      </div>
    </div>
    <div class="upload-summary full">
      <strong>${escapeHtml(candidateName)}</strong>
      <span>${escapeHtml(data.summary || "CV yapısal veriye çevrildi ve bilgi grafına kaydedildi.")}</span>
      <div class="pill-list">
        ${skills.slice(0, 8).map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}
      </div>
      <span>Neo4j kaydı: ${escapeHtml(data.cv_id || "oluşturuldu")}</span>
    </div>
  `;
}

function radialPoint(index, total, radiusX, radiusY, centerX, centerY) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const jitterX = ((index % 3) - 1) * 3;
  const jitterY = ((index % 4) - 1.5) * 2.2;
  return {
    x: Math.max(6, Math.min(88, centerX + Math.cos(angle) * radiusX + jitterX)),
    y: Math.max(8, Math.min(84, centerY + Math.sin(angle) * radiusY + jitterY)),
  };
}

function renderGraphEdge(from, to, index) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  return `
    <span
      class="neo-edge"
      style="left:${from.x}%; top:${from.y}%; width:${length}%; transform:rotate(${angle}deg); animation-delay:${index * 25}ms"
    ></span>
  `;
}

function shortLabel(label) {
  const text = String(label || "");
  return text.length > 13 ? `${text.slice(0, 10)}...` : text;
}

async function uploadLandingCv(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  const done = [];
  const steps = ["parse", "extract", "graph", "embed"];
  let stepIndex = 0;

  $("[data-upload-result]").innerHTML = "";
  setUploadStatus(`${file.name} işleniyor...`, "");
  setUploadStep(steps[0], []);
  const timer = setInterval(() => {
    if (stepIndex < steps.length - 1) {
      done.push(steps[stepIndex]);
      stepIndex += 1;
      setUploadStep(steps[stepIndex], done);
    }
  }, 1400);

  try {
    const response = await fetch(`${API_BASE}/upload-cv`, {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(formatApiError(data.detail));
    clearInterval(timer);
    setUploadStep(null, steps);
    setUploadStatus("Bilgiler çıkarıldı, Neo4j bilgi grafına kaydedildi ve embedding oluşturuldu.", "ok");
    renderUploadResult(data);
  } catch (error) {
    clearInterval(timer);
    setUploadStep(null, done);
    setUploadStatus(error.message, "error");
  }
}

function saveSession(data) {
  state.token = data.access_token;
  state.user = data.user;
  state.role = data.user?.role || state.role;
  localStorage.setItem("talentforge_token", state.token);
  localStorage.setItem("talentforge_user", JSON.stringify(state.user));
  localStorage.setItem("talentforge_role", state.role);
  syncAuthChrome();
}

function clearSession() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("talentforge_token");
  localStorage.removeItem("talentforge_user");
  localStorage.removeItem("talentforge_role");
  syncAuthChrome();
}

function syncAuthChrome() {
  document.body.classList.toggle("is-authenticated", Boolean(state.token));
}

function showView(name) {
  if (name === "dashboard" && !state.token) name = "login";
  syncAuthChrome();
  Object.values(views).forEach((view) => view?.classList.remove("active"));
  views[name]?.classList.add("active");
  if (name === "dashboard") loadDashboard();
  updateLocationHash(name);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateLocationHash(view = "dashboard", tab = null) {
  if (view === "dashboard") {
    const activeTab = tab || $(".dash-link.active")?.dataset.dashTab || "overview";
    history.replaceState(null, "", `#dashboard/${activeTab}`);
    return;
  }
  history.replaceState(null, "", view === "landing" ? "#home" : `#${view}`);
}

function syncRoleUI() {
  const isCandidate = state.role === "candidate";

  $all("[data-register-role]").forEach((group) => {
    const isActive = group.dataset.registerRole === state.role;
    group.classList.toggle("active", isActive);
    $all("input, select, textarea", group).forEach((field) => {
      field.disabled = !isActive;
    });
  });
  $all(".role-option").forEach((button) => {
    button.classList.toggle("active", button.dataset.role === state.role);
  });
  $all("[data-menu-role]").forEach((menu) => {
    menu.classList.toggle("active", menu.dataset.menuRole === state.role);
  });
  $all("[data-role-dashboard]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.roleDashboard === state.role);
  });

  const roleLabel = $("#dashboard-role-label");
  const title = $("#dashboard-title");
  if (roleLabel) roleLabel.textContent = isCandidate ? "Aday anasayfa" : "İK anasayfa";
  if (title) {
    title.textContent = isCandidate
      ? "Profilini ve başvurularini takip et."
      : "";
  }
}

function setDashboardTab(tab) {
  const activeRoot = $(`[data-role-dashboard="${state.role}"]`);
  if (!activeRoot) return;

  $all(`[data-menu-role="${state.role}"] .dash-link`).forEach((link) => {
    link.classList.toggle("active", link.dataset.dashTab === tab);
  });
  $all(".dashboard-panel", activeRoot).forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === tab);
  });

  const dashTop = $(".dash-top");
  const topButton = $("[data-top-action='search']");
  const isHrSecondaryTab = state.role === "hr" && tab !== "overview";
  const hideHeroForJobs = state.role === "hr" && tab === "jobs";
  dashTop?.classList.toggle("is-hidden", hideHeroForJobs);
  dashTop?.classList.toggle("is-compact", isHrSecondaryTab);
  if (topButton) topButton.hidden = state.role !== "hr" || tab !== "overview";
  updateDashboardHeader(tab);
  if (state.role === "hr" && tab === "shortlist") renderSavedCandidatesPanel();
  updateLocationHash("dashboard", tab);
}

function updateDashboardHeader(tab) {
  const roleLabel = $("#dashboard-role-label");
  const title = $("#dashboard-title");
  const hrLabels = {
    overview: "İK anasayfa",
    search: "Aday arama",
    jobs: "İlanlar",
    shortlist: "Kaydedilen adaylar",
  };
  const candidateLabels = {
    overview: "Aday anasayfa",
    profile: "Profilim",
    matches: "Eşleşmeler",
    applications: "Başvurular",
  };
  if (roleLabel) {
    roleLabel.textContent = state.role === "hr"
      ? (hrLabels[tab] || "İK anasayfa")
      : (candidateLabels[tab] || "Aday dashboard");
  }
  if (title) {
    title.textContent = state.role === "candidate" && tab === "overview"
      ? "Profilini ve başvurularını takip et."
      : "";
  }
}

function renderMetricGrid(root, metrics) {
  if (!root) return;
  root.innerHTML = metrics
    .map((item) => `<article><span>${item.label}</span><strong>${item.value}</strong></article>`)
    .join("");
}

function renderCompanyCard(summary) {
  const card = $("#hr-dashboard .company-card");
  if (!card || !state.user) return;
  const org = state.user.organization || {};
  const metrics = summary.metrics || {};
  card.innerHTML = `
    <div>
      <p class="eyebrow">Şirket profili</p>
      <h2>${org.name || "İK ekibi"}</h2>
      <p>${metrics.active_jobs ?? summary.total_jobs ?? 0} aktif ilan.</p>
    </div>
  `;
}

function renderHrOverview(summary) {
  const metrics = summary.metrics || {};
  const status = $("#hr-status-summary");
  if (status) {
    const activeJobs = metrics.active_jobs ?? summary.total_jobs ?? 0;
    const applications = metrics.applications ?? summary.total_applications ?? 0;
    const savedSearches = state.savedSearches.length || summary.saved_searches || 0;
    const savedCandidates = state.savedCandidates.length || metrics.shortlist || summary.shortlist || 0;
    status.innerHTML = `
      <p>${activeJobs ? `${activeJobs} aktif ilan yayında.` : "Aktif ilanınız yok."}</p>
      <p>${applications ? `${applications} başvuru takip ediliyor.` : "Henüz başvuru yok."}</p>
      <p>${savedSearches ? `${savedSearches} kayıtlı arama var.` : "Kayıtlı arama yok."}</p>
      <p>${savedCandidates ? `${savedCandidates} aday kaydedildi.` : "Kaydedilen aday yok."}</p>
    `;
  }
  renderRecentMatches();
}

function refreshHrDashboardSummary() {
  if (state.role !== "hr" || !state.dashboardSummary) return;
  const metrics = state.dashboardSummary.metrics || {};
  renderMetricGrid($("#hr-dashboard .metric-grid"), [
    { label: "Aktif ilan", value: metrics.active_jobs ?? state.dashboardSummary.total_jobs ?? 0 },
    { label: "Başvuru", value: metrics.applications ?? state.dashboardSummary.total_applications ?? 0 },
    { label: "Kayıtlı arama", value: state.savedSearches.length || state.dashboardSummary.saved_searches || 0 },
    { label: "Kaydedilen aday", value: state.savedCandidates.length || metrics.shortlist || state.dashboardSummary.shortlist || 0 },
  ]);
  renderHrOverview(state.dashboardSummary);
}

function persistSavedSearches() {
  localStorage.setItem("talentforge_saved_searches", JSON.stringify(state.savedSearches));
}

function persistSavedCandidates() {
  localStorage.setItem("talentforge_saved_candidates", JSON.stringify(state.savedCandidates));
}

function getSavedCandidateReasons(candidate) {
  if (Array.isArray(candidate.reasons) && candidate.reasons.length) return candidate.reasons;
  if (candidate.notes) {
    return String(candidate.notes)
      .split(" / ")
      .map((item) => item.trim())
      .filter((item) => item && !item.toLowerCase().startsWith("pozisyon:"));
  }
  return [];
}

function getSavedCandidatePosition(candidate) {
  if (candidate.search_title || candidate.position || candidate.title) {
    return candidate.search_title || candidate.position || candidate.title;
  }
  const match = String(candidate.notes || "").match(/Pozisyon:\s*([^/]+)/i);
  return match ? match[1].trim() : "Pozisyon belirtilmedi";
}

async function loadSavedCollections() {
  if (!state.token || state.role !== "hr") return;
  try {
    const [searchData, shortlistData] = await Promise.all([
      api("/saved-searches"),
      api("/shortlists"),
    ]);
    state.savedSearches = searchData.saved_searches || [];
    state.savedCandidates = shortlistData.shortlists || [];
    persistSavedSearches();
    persistSavedCandidates();
    renderSavedSearches();
    renderSavedCandidatesPanel();
  } catch (error) {
    console.warn(error);
  }
}

function renderSavedSearches() {
  const list = $("#saved-search-list");
  if (!list) return;
  if (!state.savedSearches.length) {
    list.innerHTML = `
      <div class="empty-state compact">
        <h3>Kayıtlı arama yok</h3>
        <p>Arama yaptıktan sonra "Aramayı kaydet" ile buraya ekleyebilirsin.</p>
      </div>
    `;
    return;
  }
  list.innerHTML = state.savedSearches.map((search) => `
    <article class="saved-item">
      <button type="button" data-run-saved-search="${escapeHtml(search.id)}">
        <strong>${escapeHtml(getSavedSearchTitle(search))}</strong>
        <span>${escapeHtml(search.mode === "text" ? "Metinle arama" : "Kategorik arama")}</span>
      </button>
      <button class="icon-text-btn" type="button" data-delete-saved-search="${escapeHtml(search.id)}">Sil</button>
    </article>
  `).join("");
}

function getSavedSearchTitle(search) {
  const parsed = search.parsed || {};
  const payload = search.payload || {};
  return (
    parsed.title ||
    payload.title ||
    (parsed.must_have_skills || payload.must_have_skills || []).slice(0, 3).join(", ") ||
    search.title ||
    search.name ||
    "Arama"
  );
}

function applySavedSearch(search) {
  renderSearchPanel();
  setDashboardTab("search");
  const mode = search.mode === "text" ? "text" : "categorical";
  setSearchMode(mode);
  const payload = search.payload || {};
  const parsed = search.parsed || {};
  if (mode === "text") {
    const textForm = $("#candidate-text-search-form");
    if (textForm) textForm.query.value = payload.query || search.title || "";
  } else {
    const form = $("#candidate-search-form");
    if (form) {
      form.title.value = payload.title || parsed.title || "";
      form.seniority.value = payload.seniority || parsed.seniority || "";
      form.must_have_skills.value = (payload.must_have_skills || parsed.must_have_skills || []).join(", ");
      form.nice_to_have_skills.value = (payload.nice_to_have_skills || parsed.nice_to_have_skills || []).join(", ");
      form.min_experience_years.value = payload.min_experience_years ?? parsed.min_experience_years ?? 0;
      form.locations.value = (payload.locations || parsed.locations || []).join(", ");
      form.education_institutions.value = (payload.education_institutions || parsed.education_institutions || []).join(", ");
      form.free_text.value = payload.free_text || parsed.free_text || "";
    }
  }
  state.recentSearch = search;
  renderCandidateResults($("#candidate-search-results"), search.candidates || [], search.parsed || null);
}

async function saveCurrentSearch() {
  const recent = state.recentSearch;
  if (!recent) return;
  const title = recent.title || "Yeni arama";
  const item = {
    ...recent,
    id: recent.id || `search-${Date.now()}`,
    title: title.length > 58 ? `${title.slice(0, 55)}...` : title,
  };
  const previousSearches = [...state.savedSearches];
  state.savedSearches = [item, ...state.savedSearches.filter((search) => search.id !== item.id)].slice(0, 12);
  persistSavedSearches();
  renderSavedSearches();
  refreshHrDashboardSummary();

  if (state.token) {
    try {
      const data = await api("/saved-searches", {
        method: "POST",
        body: JSON.stringify({
          name: item.title,
          query_spec: {
            mode: item.mode,
            parsed: item.parsed,
            payload: item.payload,
            candidates: item.candidates || [],
          },
        }),
      });
      state.savedSearches = [data.saved_search, ...state.savedSearches.filter((search) => search.id !== item.id)].slice(0, 12);
      persistSavedSearches();
      renderSavedSearches();
      refreshHrDashboardSummary();
    } catch (error) {
      state.savedSearches = previousSearches;
      persistSavedSearches();
      renderSavedSearches();
      refreshHrDashboardSummary();
      console.warn(error);
    }
  }
}

async function deleteSavedSearch(id) {
  if (state.token) {
    try {
      await api(`/saved-searches/${id}`, { method: "DELETE" });
    } catch (error) {
      console.warn(error);
    }
  }
  state.savedSearches = state.savedSearches.filter((search) => search.id !== id);
  persistSavedSearches();
  renderSavedSearches();
  refreshHrDashboardSummary();
}

async function saveCandidate(candidateId) {
  const candidate = state.lastCandidates.get(candidateId);
  if (!candidate) return;
  const currentSearchTitle = state.recentSearch ? getSavedSearchTitle(state.recentSearch) : "";
  let item = {
      candidate_id: candidateId,
      name: candidate.name || "Aday",
      score: candidate.total_score ?? "-",
      reasons: candidate.reasons || [],
      score_breakdown: candidate.score_breakdown || {},
      position: currentSearchTitle || candidate.title || "",
      search_title: currentSearchTitle,
      candidate,
      saved_at: new Date().toISOString(),
    };
  const previousCandidates = [...state.savedCandidates];
  state.savedCandidates = [item, ...state.savedCandidates.filter((saved) => saved.candidate_id !== candidateId)].slice(0, 20);
  persistSavedCandidates();
  renderSavedCandidatesPanel();
  refreshHrDashboardSummary();
  const results = $("#candidate-search-results");
  if (results) renderCandidateResults(results, Array.from(state.lastCandidates.values()), state.recentSearch?.parsed || null);

  if (state.token) {
    try {
      const data = await api("/shortlists", {
        method: "POST",
        body: JSON.stringify({
          neo4j_candidate_id: candidateId,
          candidate_name: candidate.name || "Aday",
          score: Number(candidate.total_score || 0),
          notes: [
            currentSearchTitle ? `Pozisyon: ${currentSearchTitle}` : "",
            ...(candidate.reasons || []),
          ].filter(Boolean).join(" / "),
        }),
      });
      item = {
        ...data.shortlist,
        reasons: candidate.reasons || [],
        score_breakdown: candidate.score_breakdown || {},
        position: currentSearchTitle || "",
        search_title: currentSearchTitle || "",
        candidate,
      };
      state.savedCandidates = [item, ...state.savedCandidates.filter((saved) => saved.candidate_id !== candidateId)].slice(0, 20);
      persistSavedCandidates();
      renderSavedCandidatesPanel();
      refreshHrDashboardSummary();
      if (results) renderCandidateResults(results, Array.from(state.lastCandidates.values()), state.recentSearch?.parsed || null);
    } catch (error) {
      state.savedCandidates = previousCandidates;
      persistSavedCandidates();
      renderSavedCandidatesPanel();
      refreshHrDashboardSummary();
      if (results) renderCandidateResults(results, Array.from(state.lastCandidates.values()), state.recentSearch?.parsed || null);
      console.warn(error);
    }
  }
}

async function deleteSavedCandidate(candidateId) {
  const existing = state.savedCandidates.find((item) => item.candidate_id === candidateId);
  if (state.token && existing?.id) {
    try {
      await api(`/shortlists/${existing.id}`, { method: "DELETE" });
    } catch (error) {
      console.warn(error);
    }
  }
  state.savedCandidates = state.savedCandidates.filter((item) => item.candidate_id !== candidateId);
  persistSavedCandidates();
  renderSavedCandidatesPanel();
  refreshHrDashboardSummary();
}

function renderSavedCandidatesPanel() {
  const panel = $('#hr-dashboard [data-panel="shortlist"]');
  if (!panel) return;
  if (!state.savedCandidates.length) {
    panel.innerHTML = `
      <div class="empty-state">
        <h3>Kaydedilen aday yok</h3>
        <p>Aday arama sonuçlarından "Kaydet" butonuyla adayları buraya alabilirsin.</p>
      </div>
    `;
    return;
  }
  panel.innerHTML = `
    <div class="saved-candidate-grid">
      ${state.savedCandidates.map((candidate) => `
        <article class="saved-candidate-card">
          <div>
            <h3>${escapeHtml(candidate.name)}</h3>
            <p>${escapeHtml(candidate.score)} skor</p>
            <small>${escapeHtml(getSavedCandidatePosition(candidate))}</small>
            <span>${escapeHtml(getSavedCandidateReasons(candidate)[0] || "Açıklama yok")}</span>
          </div>
          <div class="job-actions">
            <button class="ghost-btn" type="button" data-candidate-detail="${escapeHtml(candidate.candidate_id)}">İncele</button>
            <button class="ghost-btn" type="button" data-delete-saved-candidate="${escapeHtml(candidate.candidate_id)}">Kaldır</button>
          </div>
        </article>
      `).join("")}
    </div>
  `;
}

function renderRecentMatches() {
  const list = $("#recent-match-list");
  if (!list) return;
  const recent = state.recentSearch;
  const candidates = recent?.candidates || [];
  if (!candidates.length) {
    list.innerHTML = `
      <div class="empty-state compact">
        <h3>Henüz arama yapılmadı</h3>
        <p>Aday arama çalıştırdığında en son sonuçlar burada görünecek.</p>
      </div>
    `;
    return;
  }
  list.innerHTML = candidates.slice(0, 3).map((candidate, index) => `
    <button class="rank-row ${index === 0 ? "hot" : ""}" type="button" data-candidate-detail="${escapeHtml(candidate.candidate_id || "")}">
      <span class="rank">${String(index + 1).padStart(2, "0")}</span>
      <div>
        <strong>${escapeHtml(candidate.name || "Aday")}</strong>
        <p>${escapeHtml(candidate.total_score ?? "-")} skor / ${(candidate.reasons || []).slice(0, 1).map(escapeHtml).join("") || "Açıklama yok"}</p>
      </div>
      <b>${escapeHtml(recent.mode || "KG")}</b>
    </button>
  `).join("");
}

function renderProfileHero(summary) {
  const hero = $("#candidate-dashboard .profile-hero");
  if (!hero || !state.user) return;
  const profile = state.user.profile || {};
  hero.innerHTML = `
    <div>
      <p class="eyebrow">Aday profili</p>
      <h2>${state.user.full_name || "Aday"}</h2>
      <p>${profile.profession || "Rol belirtilmedi"} / ${profile.school || "Okul belirtilmedi"} / ${profile.experience_years || 0} yıl deneyim</p>
    </div>
    <span class="status-pill">${summary.applications || 0} başvuru</span>
  `;
}

async function loadDashboard() {
  syncRoleUI();
  try {
    const summary = await api("/dashboard");
    state.dashboardSummary = summary;
    const metrics = summary.metrics || {};
    if (state.role === "hr") {
      await loadSavedCollections();
      renderCompanyCard(summary);
      renderMetricGrid($("#hr-dashboard .metric-grid"), [
        { label: "Aktif ilan", value: metrics.active_jobs ?? summary.total_jobs ?? 0 },
        { label: "Başvuru", value: metrics.applications ?? summary.total_applications ?? 0 },
        { label: "Kayıtlı arama", value: state.savedSearches.length || summary.saved_searches || 0 },
        { label: "Kaydedilen aday", value: state.savedCandidates.length || metrics.shortlist || summary.shortlist || 0 },
      ]);
      renderHrOverview(summary);
      await loadJobs();
    } else {
      renderProfileHero(summary);
      renderMetricGrid($("#candidate-dashboard .metric-grid"), [
        { label: "Uygun ilan", value: metrics.matching_jobs ?? summary.total_jobs ?? 0 },
        { label: "Başvuru", value: metrics.applications ?? summary.applications ?? 0 },
        { label: "Profil doluluk", value: `${metrics.profile_completion ?? summary.profile_completion ?? 60}%` },
        { label: "Geri bildirim", value: metrics.feedback ?? summary.feedback ?? 0 },
      ]);
      await loadApplications();
    }
  } catch (error) {
    console.warn(error);
  }
}

async function loadJobs() {
  try {
    const data = await api("/jobs");
    state.jobs = data.jobs || [];
    renderJobs();
  } catch (error) {
    console.warn(error);
    state.jobs = [];
    renderJobs();
  }
}

function renderJobs() {
  const panel = $('#hr-dashboard [data-panel="jobs"]');
  if (!panel) return;
  {
  const filters = state.jobFilters;
  const titleOptions = [...new Set(state.jobs.map((job) => job.title).filter(Boolean))];
  const seniorityOptions = [...new Set(state.jobs.map((job) => job.seniority).filter(Boolean))];
  const locationOptions = [...new Set(state.jobs.map((job) => job.location).filter(Boolean))];
  const filteredJobs = state.jobs.filter((job) => {
    const titleOk = !filters.title || job.title === filters.title;
    const seniorityOk = !filters.seniority || job.seniority === filters.seniority;
    const locationOk = !filters.location || job.location === filters.location;
    return titleOk && seniorityOk && locationOk;
  });
  const jobsMarkup = filteredJobs.length
    ? filteredJobs.map((job) => `
      <article class="job-card">
        <button class="job-card-main" type="button" data-job-detail="${escapeHtml(job.id)}">
          <strong>${escapeHtml(job.title)}</strong>
          <span>${escapeHtml(job.location || "-")} / ${escapeHtml(job.seniority || "Kıdem farketmez")} / ${escapeHtml(job.status || "published")}</span>
          <small>${escapeHtml((job.must_have_skills || []).join(", ") || "Zorunlu yetenek girilmedi")}</small>
        </button>
        <div class="job-actions">
          <button class="ghost-btn" type="button" data-job-applications="${escapeHtml(job.id)}">${job.application_count || 0} başvuru</button>
          <button class="ghost-btn" type="button" data-job-detail="${escapeHtml(job.id)}">Detay</button>
        </div>
      </article>
    `).join("")
    : `
      <div class="empty-state">
        <h3>${state.jobs.length ? "Filtreye uygun ilan yok" : "Aktif ilanınız yok"}</h3>
        <p>${state.jobs.length ? "Filtreleri temizleyip tekrar deneyebilirsin." : "İlk ilanı oluşturduğunda aday eşleştirme ve başvuru akışı bu sayfadan takip edilecek."}</p>
        <button class="primary-btn small" type="button" data-job-action="new">Yeni ilan</button>
      </div>
    `;

  panel.innerHTML = `
    <div class="dash-panels ${state.jobs.length ? "" : "jobs-empty"}">
      <section class="dash-panel job-template" id="job-template-panel">
        <div class="panel-heading">
          <h2>Yeni ilan taslağı</h2>
          ${state.jobs.length ? `<button class="ghost-btn" type="button" data-job-action="close">Kapat</button>` : ""}
        </div>
        <form class="stack-form" id="job-form">
          <label>Pozisyon<input name="title" required placeholder="Senior Backend Engineer" /></label>
          <label>Açıklama<textarea name="description" rows="5" required placeholder="Rolün sorumlulukları, ekip yapısı ve aranan temel nitelikler..."></textarea></label>
          <label>Lokasyon<input name="location" placeholder="Istanbul / Remote" /></label>
          <label>Kıdem
            <select name="seniority">
              <option value="">Farketmez</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
            </select>
          </label>
          <label>Min. deneyim<input name="min_experience_years" type="number" min="0" max="50" value="0" /></label>
          <label>Zorunlu yetenekler<input name="must_have_skills" placeholder="Python, FastAPI, AWS" /></label>
          <label>Tercih edilenler<input name="nice_to_have_skills" placeholder="Docker, Kubernetes, Redis" /></label>
          <button class="primary-btn full" type="submit">İlanı yayınla</button>
          <p class="panel-message"></p>
        </form>
      </section>
      <section class="dash-panel">
        <div class="panel-heading">
          <h2>İlanlar</h2>
          <button class="primary-btn small" type="button" data-job-action="new">Yeni ilan</button>
        </div>
        <div class="job-filters">
          <label>Pozisyon
            <select data-job-filter="title">
              <option value="">Tümü</option>
              ${titleOptions.map((title) => `<option value="${escapeHtml(title)}" ${filters.title === title ? "selected" : ""}>${escapeHtml(title)}</option>`).join("")}
            </select>
          </label>
          <label>Kıdem
            <select data-job-filter="seniority">
              <option value="">Tümü</option>
              ${seniorityOptions.map((seniority) => `<option value="${escapeHtml(seniority)}" ${filters.seniority === seniority ? "selected" : ""}>${escapeHtml(seniority)}</option>`).join("")}
            </select>
          </label>
          <label>Konum
            <select data-job-filter="location">
              <option value="">Tümü</option>
              ${locationOptions.map((location) => `<option value="${escapeHtml(location)}" ${filters.location === location ? "selected" : ""}>${escapeHtml(location)}</option>`).join("")}
            </select>
          </label>
        </div>
        <div id="hr-job-list" class="job-grid">${jobsMarkup}</div>
      </section>
    </div>
  `;
  $("#job-form")?.addEventListener("submit", createJob);
  $all("[data-job-filter]", panel).forEach((field) => {
    field.addEventListener("change", () => {
      state.jobFilters[field.dataset.jobFilter] = field.value;
      renderJobs();
    });
  });
  $all("[data-job-action='new']", panel).forEach((button) => {
    button.addEventListener("click", () => $("#job-template-panel")?.classList.add("active"));
  });
  $("[data-job-action='close']", panel)?.addEventListener("click", () => {
    $("#job-template-panel")?.classList.remove("active");
  });
  return;
  }
  const jobsMarkup = state.jobs.length
    ? state.jobs
        .map(
          (job) => `
            <p>
              <strong>${job.title}</strong><br>
              ${job.location || "-"} / ${job.status || "published"}<br>
              <small>${(job.must_have_skills || []).join(", ") || "Zorunlu yetenek girilmedi"}</small>
            </p>`
        )
        .join("")
    : `
        <div class="empty-state">
          <h3>Aktif ilanınız yok</h3>
          <p>İlk ilanı oluşturduğunda aday eşleştirme ve başvuru akışı bu sayfadan takip edilecek.</p>
          <button class="primary-btn small" type="button" data-job-action="new">Yeni ilan</button>
        </div>
      `;

  panel.innerHTML = `
    <div class="dash-panels ${state.jobs.length ? "" : "jobs-empty"}">
      <section class="dash-panel job-template" id="job-template-panel">
        <div class="panel-heading">
          <h2>Yeni ilan taslagi</h2>
          ${state.jobs.length ? `<button class="ghost-btn" type="button" data-job-action="close">Kapat</button>` : ""}
        </div>
        <form class="stack-form" id="job-form">
          <label>Pozisyon<input name="title" required placeholder="Senior Backend Engineer" /></label>
          <label>Açıklama<textarea name="description" rows="5" required placeholder="Rolün sorumlulukları, ekip yapısı ve aranan temel nitelikler..."></textarea></label>
          <label>Lokasyon<input name="location" placeholder="Istanbul / Remote" /></label>
          <label>Kıdem
            <select name="seniority">
              <option value="">Farketmez</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
            </select>
          </label>
          <label>Min. deneyim<input name="min_experience_years" type="number" min="0" max="50" value="0" /></label>
          <label>Zorunlu yetenekler<input name="must_have_skills" placeholder="Python, FastAPI, AWS" /></label>
          <label>Tercih edilenler<input name="nice_to_have_skills" placeholder="Docker, Kubernetes, Redis" /></label>
          <button class="primary-btn full" type="submit">İlani yayınla</button>
          <p class="panel-message"></p>
        </form>
      </section>
      <section class="dash-panel">
        <div class="panel-heading">
          <h2>İlanlar</h2>
          ${state.jobs.length ? `<button class="primary-btn small" type="button" data-job-action="new">Yeni ilan</button>` : ""}
        </div>
        <div id="hr-job-list" class="list-stack">
          ${jobsMarkup}
        </div>
      </section>
    </div>
  `;
  $("#job-form")?.addEventListener("submit", createJob);
  $all("[data-job-action='new']", panel).forEach((button) => {
    button.addEventListener("click", () => $("#job-template-panel")?.classList.add("active"));
  });
  $("[data-job-action='close']", panel)?.addEventListener("click", () => {
    $("#job-template-panel")?.classList.remove("active");
  });
}

async function createJob(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = $(".panel-message", form);
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.must_have_skills = (payload.must_have_skills || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  payload.nice_to_have_skills = (payload.nice_to_have_skills || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  payload.min_experience_years = Number(payload.min_experience_years || 0);
  payload.status = "published";

  try {
    setFormLoading(form, true, "Yayınlanıyor...");
    await api("/jobs", { method: "POST", body: JSON.stringify(payload) });
    if (message) {
      message.textContent = "İlan oluşturuldu.";
      message.dataset.type = "ok";
    }
    form.reset();
    await loadJobs();
    const summary = await api("/dashboard");
    state.dashboardSummary = summary;
    refreshHrDashboardSummary();
    setDashboardTab("jobs");
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
  } finally {
    setFormLoading(form, false);
  }
}

function renderCandidateResults(results, candidates, parsed = null) {
  if (!results) return;
  const list = candidates || [];
  state.lastCandidates = new Map(list.map((candidate) => [candidate.candidate_id, candidate]));
  state.recentSearch = {
    id: `search-${Date.now()}`,
    mode: parsed ? "text" : "categorical",
    parsed,
    payload: parsed,
    title: parsed
      ? parsed.title || (parsed.must_have_skills || []).join(", ") || "Metinle arama"
      : "Kategorik arama",
    candidates: list,
    created_at: new Date().toISOString(),
  };
  localStorage.setItem("talentforge_recent_search", JSON.stringify(state.recentSearch));
  renderRecentMatches();
  const parsedMarkup = parsed
    ? `
      <div class="query-spec">
        <span>Pozisyon: ${escapeHtml(parsed.title || "-")}</span>
        <span>Kıdem: ${escapeHtml(parsed.seniority || "-")}</span>
        <span>Zorunlu: ${escapeHtml((parsed.must_have_skills || []).join(", ") || "-")}</span>
        <span>Tercih: ${escapeHtml((parsed.nice_to_have_skills || []).join(", ") || "-")}</span>
        <span>Eğitim: ${escapeHtml((parsed.education_institutions || []).join(", ") || parsed.education_level || "-")}</span>
      </div>
    `
    : "";

  results.innerHTML = `
    ${parsedMarkup}
    <div class="search-result-actions">
      <button class="ghost-btn" type="button" data-save-current-search>Aramayı kaydet</button>
    </div>
    <div class="table-row head"><span>Aday</span><span>Skor</span><span>Açıklama</span><span>Aksiyon</span></div>
    ${
      list.length
        ? list
            .map((candidate) => {
              const saved = state.savedCandidates.some((item) => item.candidate_id === candidate.candidate_id);
              return `
                <div class="table-row">
                  <span>${escapeHtml(candidate.name || "-")}</span>
                  <span>${escapeHtml(candidate.total_score ?? "-")}</span>
                  <span>${escapeHtml((candidate.reasons || []).join(" / ") || "Açıklama yok")}</span>
                  <span class="row-actions">
                    <button type="button" data-candidate-detail="${escapeHtml(candidate.candidate_id || "")}">İncele</button>
                    <button type="button" data-save-candidate="${escapeHtml(candidate.candidate_id || "")}">${saved ? "Kaydedildi" : "Kaydet"}</button>
                  </span>
                </div>`;
            })
            .join("")
        : `<div class="table-row"><span>Uygun aday bulunamadı</span><span>-</span><span>-</span><span>-</span></div>`
    }
  `;
}
async function searchCandidates(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = $(".panel-message", form);
  const results = $("#candidate-search-results");
  const raw = Object.fromEntries(new FormData(form).entries());
  const payload = {
    title: raw.title || null,
    seniority: raw.seniority || null,
    must_have_skills: splitList(raw.must_have_skills),
    nice_to_have_skills: splitList(raw.nice_to_have_skills),
    min_experience_years: Number(raw.min_experience_years || 0),
    preferred_industries: [],
    locations: splitList(raw.locations),
    languages: [],
    education_level: null,
    education_institutions: splitList(raw.education_institutions),
    must_have_certifications: [],
    free_text: raw.free_text || null,
  };

  try {
    setFormLoading(form, true);
    const data = await api("/search-candidates", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (message) message.textContent = `${data.length} aday bulundu.`;
    renderCandidateResults(results, data);
    if (state.recentSearch) {
      state.recentSearch.payload = payload;
      localStorage.setItem("talentforge_recent_search", JSON.stringify(state.recentSearch));
    }
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
  } finally {
    setFormLoading(form, false);
  }
}

async function searchCandidatesText(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = $(".panel-message", form);
  const results = $("#candidate-search-results");
  const query = new FormData(form).get("query")?.toString().trim();
  if (!query) {
    if (message) {
      message.textContent = "Arama metni bos olamaz.";
      message.dataset.type = "error";
    }
    return;
  }

  try {
    setFormLoading(form, true);
    const data = await api("/nl-search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    const candidates = data.results || [];
    const parsed = data.parsed_query || {};
    if (message) {
      message.textContent = `${candidates.length} aday bulundu. Sistem sorguyu yapısal kriterlere çevirdi.`;
      message.dataset.type = "ok";
    }
    if (results) {
      renderCandidateResults(results, candidates, parsed);
      if (state.recentSearch) {
        state.recentSearch.payload = { query };
        localStorage.setItem("talentforge_recent_search", JSON.stringify(state.recentSearch));
      }
    }
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
  } finally {
    setFormLoading(form, false);
  }
}

function renderSearchPanel() {
  const panel = $('#hr-dashboard [data-panel="search"]');
  if (!panel) return;
  panel.innerHTML = `
    <div class="dash-panels wide-left">
      <section class="dash-panel">
        <div class="panel-heading">
          <h2>Aday arama</h2>
        </div>
        <div class="segmented-control" role="tablist" aria-label="Arama modu">
          <button class="active" type="button" data-search-mode-button="categorical">Kategorik arama</button>
          <button type="button" data-search-mode-button="text">Metinle arama</button>
        </div>
        <div class="search-mode active" data-search-mode="categorical">
          <form class="stack-form" id="candidate-search-form">
            <label>Pozisyon<input name="title" placeholder="Backend Developer" /></label>
            <label>Kıdem
              <select name="seniority">
                <option value="">Farketmez</option>
                <option value="junior">Junior</option>
                <option value="mid">Mid</option>
                <option value="senior">Senior</option>
                <option value="lead">Lead</option>
              </select>
            </label>
            <label>Zorunlu yetenekler<input name="must_have_skills" placeholder="Python, FastAPI, AWS" /></label>
            <label>Tercih edilenler<input name="nice_to_have_skills" placeholder="Docker, Kubernetes" /></label>
            <label>Min. deneyim<input name="min_experience_years" type="number" min="0" value="0" /></label>
            <label>Lokasyon<input name="locations" placeholder="Istanbul, Remote" /></label>
            <label>Eğitim kurumu<input name="education_institutions" placeholder="ODTÜ, Marmara Üniversitesi" /></label>
            <label>Serbest metin<textarea name="free_text" rows="4" placeholder="Fintech deneyimi olan..."></textarea></label>
            <button class="primary-btn full" type="submit">Aday ara</button>
            <p class="panel-message"></p>
          </form>
        </div>
        <div class="search-mode" data-search-mode="text">
          <form class="stack-form" id="candidate-text-search-form">
            <label>Arama metni
              <textarea name="query" rows="8" placeholder="Fintech alanında çalışmış senior backend geliştirici arıyoruz. Python, FastAPI, PostgreSQL ve Redis zorunlu olsun. AWS ve Kubernetes bilmesi iyi olur."></textarea>
            </label>
            <button class="primary-btn full" type="submit">Metinle aday ara</button>
            <p class="panel-message"></p>
          </form>
        </div>
      </section>
      <section class="dash-panel">
        <h2>Kayıtlı aramalar</h2>
        <div id="saved-search-list" class="saved-list"></div>
      </section>
    </div>
    <div class="candidate-table" id="candidate-search-results">
      <div class="table-row head"><span>Aday</span><span>Skor</span><span>Açıklama</span><span>Aksiyon</span></div>
    </div>
  `;
  $("#candidate-search-form")?.addEventListener("submit", searchCandidates);
  $("#candidate-text-search-form")?.addEventListener("submit", searchCandidatesText);
  renderSavedSearches();
  setSearchMode("categorical");
}

async function loadApplications() {
  try {
    const data = await api("/applications");
    state.applications = data.applications || [];
  } catch (error) {
    console.warn(error);
  }
}

function splitList(value) {
  return (value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setFormLoading(form, isLoading, label = "Aranıyor...") {
  const button = $("button[type='submit']", form);
  if (!button) return;
  if (isLoading) {
    button.dataset.originalText = button.textContent;
    button.textContent = label;
    button.disabled = true;
    form.classList.add("is-loading");
    return;
  }
  button.textContent = button.dataset.originalText || button.textContent;
  button.disabled = false;
  form.classList.remove("is-loading");
}

function formatBreakdown(breakdown = {}) {
  const entries = Object.entries(breakdown);
  if (!entries.length) return `<p class="muted-line">Skor kırılımı yok.</p>`;
  return entries
    .map(([name, value]) => `<article><span>${name.replaceAll("_", " ")}</span><strong>${value}</strong></article>`)
    .join("");
}

function renderPills(items = [], key = null) {
  const values = items
    .map((item) => (key && item ? item[key] : item))
    .filter(Boolean)
    .slice(0, 18);
  if (!values.length) return `<p class="muted-line">Kayıt yok.</p>`;
  return `<div class="pill-list">${values.map((value) => `<span>${value}</span>`).join("")}</div>`;
}

function renderTimeline(items = []) {
  if (!items.length) return `<p class="muted-line">Deneyim kaydı yok.</p>`;
  return items
    .slice(0, 4)
    .map(
      (item) => `
        <article class="modal-timeline-item">
          <strong>${item.role || "Rol belirtilmedi"}</strong>
          <span>${item.company || "Şirket belirtilmedi"} / ${item.start_date || "-"} - ${item.end_date || (item.is_current ? "Devam" : "-")}</span>
          <p>${item.description || ""}</p>
        </article>`
    )
    .join("");
}

function renderProjects(items = []) {
  if (!items.length) return `<p class="muted-line">Proje kaydı yok.</p>`;
  return items
    .slice(0, 4)
    .map(
      (item) => `
        <article class="modal-timeline-item">
          <strong>${item.name || "Proje"}</strong>
          <span>${item.role || "Rol belirtilmedi"} ${item.url ? `/ ${item.url}` : ""}</span>
          <p>${item.description || item.evidence_text || ""}</p>
        </article>`
    )
    .join("");
}

async function openCandidateModal(candidateId) {
  if (!candidateId) return;
  const searchResult = state.lastCandidates.get(candidateId) || {};
  const savedResult = state.savedCandidates.find((candidate) => candidate.candidate_id === candidateId) || {};
  const savedCandidatePayload = savedResult.candidate || {};
  let detail = {};
  try {
    detail = await api(`/candidates/${candidateId}`);
  } catch (error) {
    detail = {};
  }
  const savedReasons = getSavedCandidateReasons(savedResult);
  const candidate = {
    ...detail,
    ...savedCandidatePayload,
    ...searchResult,
    total_score: searchResult.total_score ?? savedCandidatePayload.total_score ?? savedResult.score ?? detail.total_score,
    score_breakdown: searchResult.score_breakdown || savedCandidatePayload.score_breakdown || savedResult.score_breakdown || detail.score_breakdown,
    reasons: searchResult.reasons || savedCandidatePayload.reasons || (savedReasons.length ? savedReasons : detail.reasons),
  };
  const modal = ensureCandidateModal();
  const cvButton = candidate.cv_available
    ? `<a class="primary-btn small" href="${API_BASE}/download-cv/${candidateId}" target="_blank" rel="noreferrer">Hashli CV indir</a>`
    : `<button class="ghost-btn" type="button" disabled>CV yok</button>`;

  $(".candidate-modal-body", modal).innerHTML = `
    <div class="modal-head">
      <div>
        <p class="eyebrow">Aday detayı</p>
        <h2>${candidate.name || "Aday"}</h2>
        <p>${candidate.summary || "Ozet bulunamadı."}</p>
      </div>
      <div class="modal-score">
        <span>${candidate.total_score ?? "-"}</span>
        <small>toplam skor</small>
      </div>
    </div>
    <div class="modal-actions">
      ${cvButton}
      <span class="hash-chip">hash: ${candidate.file_hash_short || "yok"}</span>
    </div>
    <div class="modal-grid">
      <section>
        <h3>Skor kırılımı</h3>
        <div class="breakdown-grid">${formatBreakdown(candidate.score_breakdown)}</div>
      </section>
      <section>
        <h3>İletişim</h3>
        <p class="muted-line">${candidate.email || "-"}<br>${candidate.phone || "-"}<br>${candidate.location || "-"}</p>
      </section>
    </div>
    <section>
      <h3>Eşleşme açıklaması</h3>
      <ul class="reason-list">${(candidate.reasons || []).map((reason) => `<li>${reason}</li>`).join("") || "<li>Açıklama yok.</li>"}</ul>
    </section>
    <section>
      <h3>Yetenekler</h3>
      ${renderPills(candidate.skills, typeof candidate.skills?.[0] === "object" ? "name" : null)}
    </section>
    <section>
      <h3>Deneyim</h3>
      ${renderTimeline(candidate.experiences || [])}
    </section>
    <section>
      <h3>Projeler</h3>
      ${renderProjects(candidate.projects || [])}
    </section>
    <div class="modal-grid">
      <section>
        <h3>Eğitim</h3>
        ${renderPills((candidate.educations || []).map((edu) => [edu.degree, edu.field, edu.institution].filter(Boolean).join(" / ")))}
      </section>
      <section>
        <h3>Sertifika & dil</h3>
        ${renderPills([...(candidate.certifications || []), ...(candidate.languages || [])])}
      </section>
    </div>
  `;
  modal.classList.add("active");
  document.body.classList.add("modal-open");
}

function closeCandidateModal() {
  $(".candidate-modal:not(.job-modal)")?.classList.remove("active");
  if (!$(".job-modal")?.classList.contains("active")) {
    document.body.classList.remove("modal-open");
  }
}

async function openJobModal(jobId) {
  const modal = ensureJobModal();
  const localJob = state.jobs.find((job) => job.id === jobId) || {};
  let job = localJob;
  renderJobModalBody(modal, job, true);
  modal.classList.add("active");
  document.body.classList.add("modal-open");
  try {
    const data = await api(`/jobs/${jobId}`);
    job = data.job || localJob;
  } catch (error) {
    console.warn(error);
  }
  renderJobModalBody(modal, job, false);
}

function renderJobModalBody(modal, job, isLoading = false) {
  $(".job-modal-body", modal).innerHTML = `
    <div class="modal-head">
      <div>
        <p class="eyebrow">İlan detayı</p>
        <h2>${escapeHtml(job.title || "İlan")}</h2>
        <p>${escapeHtml(job.description || "Açıklama yok.")}</p>
        ${isLoading ? `<p class="muted-line">Detaylar yükleniyor...</p>` : ""}
      </div>
      <div class="modal-score">
        <span>${escapeHtml(job.application_count || 0)}</span>
        <small>başvuru</small>
      </div>
    </div>
    <div class="modal-grid">
      <section>
        <h3>Kriterler</h3>
        <p class="muted-line">
          Kıdem: ${escapeHtml(job.seniority || "Farketmez")}<br>
          Min. deneyim: ${escapeHtml(job.min_experience_years ?? 0)} yıl<br>
          Lokasyon: ${escapeHtml(job.location || "-")}
        </p>
      </section>
      <section>
        <h3>Yetenekler</h3>
        ${renderPills([...(job.must_have_skills || []), ...(job.nice_to_have_skills || [])])}
      </section>
    </div>
    <div class="modal-actions">
      <button class="primary-btn small" type="button" data-job-applications="${escapeHtml(job.id)}">${job.application_count || 0} başvuru</button>
    </div>
  `;
}

async function openJobApplicationsModal(jobId) {
  const modal = ensureJobModal();
  const job = state.jobs.find((item) => item.id === jobId) || {};
  $(".job-modal-body", modal).innerHTML = `<p class="muted-line">Başvurular yükleniyor...</p>`;
  modal.classList.add("active");
  document.body.classList.add("modal-open");
  try {
    const data = await api(`/jobs/${jobId}/applications`);
    const applications = data.applications || [];
    $(".job-modal-body", modal).innerHTML = `
      <div class="modal-head">
        <div>
          <p class="eyebrow">Başvuran adaylar</p>
          <h2>${escapeHtml(job.title || "İlan")}</h2>
          <p>${applications.length} başvuru listeleniyor.</p>
        </div>
      </div>
      <div class="candidate-table in-modal">
        <div class="table-row head"><span>Aday</span><span>Skor</span><span>Profil</span><span>Aksiyon</span></div>
        ${
          applications.length
            ? applications.map((application) => {
                const candidate = application.candidate || {};
                const neo4jId = candidate.neo4j_candidate_id || "";
                return `
                  <div class="table-row">
                    <span>${escapeHtml(candidate.name || "Aday")}</span>
                    <span>${escapeHtml(application.match_score ?? "-")}</span>
                    <span>${escapeHtml([candidate.profession, candidate.school, candidate.location].filter(Boolean).join(" / ") || "-")}</span>
                    <span class="row-actions">
                      <button type="button" data-candidate-detail="${escapeHtml(neo4jId)}" ${neo4jId ? "" : "disabled"}>İncele</button>
                      ${neo4jId ? `<a class="ghost-btn" href="${API_BASE}/download-cv/${escapeHtml(neo4jId)}" target="_blank" rel="noreferrer">CV indir</a>` : `<button type="button" disabled>CV yok</button>`}
                    </span>
                  </div>`;
              }).join("")
            : `<div class="table-row"><span>Henüz başvuru yok</span><span>-</span><span>-</span><span>-</span></div>`
        }
      </div>
    `;
  } catch (error) {
    $(".job-modal-body", modal).innerHTML = `<p class="muted-line">${escapeHtml(error.message)}</p>`;
  }
}

function closeJobModal() {
  $(".job-modal")?.classList.remove("active");
  if (!$(".candidate-modal:not(.job-modal)")?.classList.contains("active")) {
    document.body.classList.remove("modal-open");
  }
}

function ensureJobModal() {
  let modal = $(".job-modal");
  if (modal) return modal;
  modal = document.createElement("div");
  modal.className = "job-modal candidate-modal";
  modal.innerHTML = `
    <div class="candidate-modal-backdrop" data-modal-close></div>
    <article class="candidate-modal-card wide" role="dialog" aria-modal="true" aria-label="İlan detayı">
      <button class="modal-close" type="button" data-modal-close aria-label="Kapat">×</button>
      <div class="job-modal-body candidate-modal-body"></div>
    </article>
  `;
  document.body.appendChild(modal);
  return modal;
}

function ensureCandidateModal() {
  let modal = $(".candidate-modal:not(.job-modal)");
  if (modal) return modal;
  modal = document.createElement("div");
  modal.className = "candidate-modal";
  modal.innerHTML = `
    <div class="candidate-modal-backdrop" data-modal-close></div>
    <article class="candidate-modal-card" role="dialog" aria-modal="true" aria-label="Aday detayı">
      <button class="modal-close" type="button" data-modal-close aria-label="Kapat">×</button>
      <div class="candidate-modal-body"></div>
    </article>
  `;
  document.body.appendChild(modal);
  return modal;
}

function setSearchMode(mode) {
  const panel = $('#hr-dashboard [data-panel="search"]');
  if (!panel) return;
  $all("[data-search-mode-button]", panel).forEach((button) => {
    button.classList.toggle("active", button.dataset.searchModeButton === mode);
  });
  $all("[data-search-mode]", panel).forEach((section) => {
    section.classList.toggle("active", section.dataset.searchMode === mode);
  });
}

function setupRouting() {
  document.addEventListener("click", (event) => {
    const searchModeButton = event.target.closest("[data-search-mode-button]");
    if (searchModeButton) {
      setSearchMode(searchModeButton.dataset.searchModeButton);
    }

    const detailButton = event.target.closest("[data-candidate-detail]");
    if (detailButton) {
      openCandidateModal(detailButton.dataset.candidateDetail);
    }

    const saveSearchButton = event.target.closest("[data-save-current-search]");
    if (saveSearchButton) {
      saveCurrentSearch();
    }

    const deleteSearchButton = event.target.closest("[data-delete-saved-search]");
    if (deleteSearchButton) {
      deleteSavedSearch(deleteSearchButton.dataset.deleteSavedSearch);
    }

    const runSearchButton = event.target.closest("[data-run-saved-search]");
    if (runSearchButton) {
      const saved = state.savedSearches.find((search) => search.id === runSearchButton.dataset.runSavedSearch);
      if (saved) applySavedSearch(saved);
    }

    const jobDetailButton = event.target.closest("[data-job-detail]");
    if (jobDetailButton) {
      openJobModal(jobDetailButton.dataset.jobDetail);
    }

    const jobApplicationsButton = event.target.closest("[data-job-applications]");
    if (jobApplicationsButton) {
      openJobApplicationsModal(jobApplicationsButton.dataset.jobApplications);
    }

    const saveCandidateButton = event.target.closest("[data-save-candidate]");
    if (saveCandidateButton) {
      saveCandidate(saveCandidateButton.dataset.saveCandidate);
    }

    const deleteCandidateButton = event.target.closest("[data-delete-saved-candidate]");
    if (deleteCandidateButton) {
      deleteSavedCandidate(deleteCandidateButton.dataset.deleteSavedCandidate);
    }

    const closeButton = event.target.closest("[data-modal-close]");
    if (closeButton) {
      if (closeButton.closest(".job-modal")) {
        closeJobModal();
      } else {
        closeCandidateModal();
      }
    }
  });

  $all("[data-route]").forEach((element) => {
    element.addEventListener("click", () => {
      if (element.dataset.route === "landing") clearSession();
      showView(element.dataset.route);
    });
  });

  $all(".role-option").forEach((button) => {
    button.addEventListener("click", () => {
      state.role = button.dataset.role;
      localStorage.setItem("talentforge_role", state.role);
      syncRoleUI();
    });
  });

  $all("[data-auth-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      $all("[data-auth-tab]").forEach((item) => item.classList.remove("active"));
      $all("[data-auth-panel]").forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      $(`[data-auth-panel="${button.dataset.authTab}"]`)?.classList.add("active");
      setMessage("");
    });
  });

  $all(".dash-link").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.dashTab === "search") renderSearchPanel();
      setDashboardTab(button.dataset.dashTab);
    });
  });

  $("[data-top-action='search']")?.addEventListener("click", () => {
    renderSearchPanel();
    setDashboardTab(state.role === "hr" ? "search" : "matches");
  });
}

function setupLandingUpload() {
  const trigger = $("[data-demo-upload-trigger]");
  const input = $("#demo-cv-input");
  if (!trigger || !input) return;
  trigger.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    uploadLandingCv(input.files?.[0]);
    input.value = "";
  });
}

function setupAuthForms() {
  $all(".auth-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const panel = form.dataset.authPanel;
      const inputs = [...form.querySelectorAll("input")];
      setMessage("Isleniyor...");

      try {
        if (panel === "forgot") {
          setMessage("Demo modunda sifre sifirlama simule edildi.");
          return;
        }

        if (panel === "login") {
          const [email, password] = inputs;
          const data = await api("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email: email.value, password: password.value }),
          });
          saveSession(data);
          setMessage("Giriş başarılı.");
          showView("dashboard");
          return;
        }

        const activeRoleFields = form.querySelector(`[data-register-role="${state.role}"]`);
        const roleInputs = [...activeRoleFields.querySelectorAll("input")];
        const fullName = inputs[0].value;
        const password = inputs[inputs.length - 1].value;
        const payload =
          state.role === "hr"
            ? {
                role: "hr",
                full_name: fullName,
                company_name: roleInputs[0].value,
                company_email: roleInputs[1].value,
                email: roleInputs[1].value,
                position: roleInputs[2].value,
                password,
              }
            : {
                role: "candidate",
                full_name: fullName,
                email: roleInputs[0].value,
                school: roleInputs[1].value,
                profession: roleInputs[2].value,
                experience_years: Number(roleInputs[3].value || 0),
                password,
              };

        const data = await api("/auth/register", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        saveSession(data);
        setMessage("Hesap oluşturuldu.");
        showView("dashboard");
      } catch (error) {
        setMessage(error.message, "error");
      }
    });
  });
}

function setupReveal() {
  const revealEls = $all("[data-reveal]");
  if (!("IntersectionObserver" in window)) {
    revealEls.forEach((el) => el.classList.add("visible"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add("visible");
      });
    },
    { threshold: 0.14 }
  );
  revealEls.forEach((el) => observer.observe(el));
}

function init() {
  setupRouting();
  setupAuthForms();
  setupLandingUpload();
  setupReveal();
  syncRoleUI();
  renderSearchPanel();

  if (state.token) {
    showView("dashboard");
  } else {
    showView("landing");
  }
}

init();


