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
    throw new Error(`API'ye ulasilamadi: ${API_BASE}`);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Islem tamamlanamadi");
  return data;
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
  const certifications = data.certifications || [];
  const languages = data.languages || [];
  const companies = [...new Set(experiences.map((exp) => exp.company_name || exp.company).filter(Boolean))];
  const graphNodes = [
    { label: candidateName, type: "Candidate", x: 49, y: 48 },
    ...skills.slice(0, 12).map((label, index) => ({ label, type: "Skill", ...radialPoint(index, 12, 35, 44, 49, 48) })),
    ...experiences.slice(0, 4).map((exp, index) => ({ label: exp.role_title || exp.role || "Experience", type: "Experience", ...radialPoint(index + 1, 5, 25, 76, 49, 48) })),
    ...companies.slice(0, 3).map((label, index) => ({ label, type: "Company", ...radialPoint(index + 2, 4, 31, 19, 49, 48) })),
    ...educations.slice(0, 2).map((edu, index) => ({ label: edu.institution || edu.institution_name || edu.degree || "Education", type: "Education", ...radialPoint(index + 3, 6, 30, 72, 49, 48) })),
    ...certifications.slice(0, 2).map((label, index) => ({ label: label.name || label, type: "Certification", ...radialPoint(index + 2, 7, 40, 64, 49, 48) })),
    ...languages.slice(0, 2).map((label, index) => ({ label: label.name || label, type: "Language", ...radialPoint(index + 4, 7, 26, 22, 49, 48) })),
  ].slice(0, 28);
  const relationshipCount =
    skills.length + experiences.length + companies.length + educations.length + certifications.length + languages.length;
  const typeCounts = graphNodes.reduce((acc, node) => {
    acc[node.type] = (acc[node.type] || 0) + 1;
    return acc;
  }, {});
  const edges = graphNodes
    .slice(1)
    .map((node, index) => renderGraphEdge(graphNodes[0], node, index))
    .join("");

  result.innerHTML = `
    <div class="neo4j-preview" aria-label="Neo4j bilgi grafigi onizleme">
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
        <span>AT_COMPANY (${companies.length})</span>
        <span>HAS_EDUCATION (${educations.length})</span>
        <span>HAS_CERTIFICATION (${certifications.length})</span>
      </div>
    </div>
    <div class="upload-summary full">
      <strong>${escapeHtml(candidateName)}</strong>
      <span>${escapeHtml(data.summary || "CV yapisal veriye cevrildi ve bilgi grafigine kaydedildi.")}</span>
      <div class="pill-list">
        ${skills.slice(0, 8).map((skill) => `<span>${escapeHtml(skill)}</span>`).join("")}
      </div>
      <span>Neo4j kaydi: ${escapeHtml(data.cv_id || "olusturuldu")}</span>
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
  setUploadStatus(`${file.name} isleniyor...`, "");
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
    if (!response.ok) throw new Error(data.detail || "CV islenemedi");
    clearInterval(timer);
    setUploadStep(null, steps);
    setUploadStatus("Bilgiler cikarildi, Neo4j bilgi grafigine kaydedildi ve embedding olusturuldu.", "ok");
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
  window.scrollTo({ top: 0, behavior: "smooth" });
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
  if (roleLabel) roleLabel.textContent = isCandidate ? "Aday dashboard" : "IK dashboard";
  if (title) {
    title.textContent = isCandidate
      ? "Profilini ve basvurularini takip et."
      : "Aday havuzunu yonet.";
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
  const hideHeroForJobs = state.role === "hr" && tab === "jobs";
  dashTop?.classList.toggle("is-hidden", hideHeroForJobs);
  if (topButton) topButton.hidden = state.role !== "hr" || tab === "jobs";
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
      <p class="eyebrow">Sirket profili</p>
      <h2>${org.name || "IK ekibi"}</h2>
      <p>${org.domain || state.user.email} domaini ile kayitli. ${metrics.active_jobs ?? summary.total_jobs ?? 0} aktif ilan.</p>
    </div>
    <span class="status-pill">Verified company mail</span>
  `;
}

function renderProfileHero(summary) {
  const hero = $("#candidate-dashboard .profile-hero");
  if (!hero || !state.user) return;
  const profile = state.user.profile || {};
  hero.innerHTML = `
    <div>
      <p class="eyebrow">Aday profili</p>
      <h2>${state.user.full_name || "Aday"}</h2>
      <p>${profile.profession || "Rol belirtilmedi"} / ${profile.school || "Okul belirtilmedi"} / ${profile.experience_years || 0} yil deneyim</p>
    </div>
    <span class="status-pill">${summary.applications || 0} basvuru</span>
  `;
}

async function loadDashboard() {
  syncRoleUI();
  try {
    const summary = await api("/dashboard");
    const metrics = summary.metrics || {};
    if (state.role === "hr") {
      renderCompanyCard(summary);
      renderMetricGrid($("#hr-dashboard .metric-grid"), [
        { label: "Aktif ilan", value: metrics.active_jobs ?? summary.total_jobs ?? 0 },
        { label: "Basvuru", value: metrics.applications ?? summary.total_applications ?? 0 },
        { label: "Kayitli arama", value: summary.saved_searches ?? 0 },
        { label: "Shortlist", value: metrics.shortlist ?? summary.shortlist ?? 0 },
      ]);
      await loadJobs();
    } else {
      renderProfileHero(summary);
      renderMetricGrid($("#candidate-dashboard .metric-grid"), [
        { label: "Uygun ilan", value: metrics.matching_jobs ?? summary.total_jobs ?? 0 },
        { label: "Basvuru", value: metrics.applications ?? summary.applications ?? 0 },
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
          <h3>Aktif ilaniniz yok</h3>
          <p>Ilk ilani olusturdugunda aday eslestirme ve basvuru akisi bu sayfadan takip edilecek.</p>
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
          <label>Aciklama<textarea name="description" rows="5" required placeholder="Rolun sorumluluklari, ekip yapisi ve aranan temel nitelikler..."></textarea></label>
          <label>Lokasyon<input name="location" placeholder="Istanbul / Remote" /></label>
          <label>Kidem
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
          <button class="primary-btn full" type="submit">Ilani yayinla</button>
          <p class="panel-message"></p>
        </form>
      </section>
      <section class="dash-panel">
        <div class="panel-heading">
          <h2>Ilanlar</h2>
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
    await api("/jobs", { method: "POST", body: JSON.stringify(payload) });
    if (message) {
      message.textContent = "Ilan olusturuldu.";
      message.dataset.type = "ok";
    }
    form.reset();
    await loadJobs();
    await loadDashboard();
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
  }
}

function renderCandidateResults(results, candidates, parsed = null) {
  if (!results) return;
  state.lastCandidates = new Map((candidates || []).map((candidate) => [candidate.candidate_id, candidate]));
  const parsedMarkup = parsed
    ? `
      <div class="query-spec">
        <span>Pozisyon: ${parsed.title || "-"}</span>
        <span>Kidem: ${parsed.seniority || "-"}</span>
        <span>Zorunlu: ${(parsed.must_have_skills || []).join(", ") || "-"}</span>
        <span>Tercih: ${(parsed.nice_to_have_skills || []).join(", ") || "-"}</span>
      </div>
    `
    : "";

  results.innerHTML = `
    ${parsedMarkup}
    <div class="table-row head"><span>Aday</span><span>Skor</span><span>Aciklama</span><span>Aksiyon</span></div>
    ${
      candidates.length
        ? candidates
            .map(
              (candidate) => `
              <div class="table-row">
                <span>${candidate.name || "-"}</span>
                <span>${candidate.total_score ?? "-"}</span>
                <span>${(candidate.reasons || []).join(" / ") || "Aciklama yok"}</span>
                <button type="button" data-candidate-detail="${candidate.candidate_id || ""}">Incele</button>
              </div>`
            )
            .join("")
        : `<div class="table-row"><span>Uygun aday bulunamadi</span><span>-</span><span>-</span><span>-</span></div>`
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
    must_have_certifications: [],
    free_text: raw.free_text || null,
  };

  try {
    const data = await api("/search-candidates", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (message) message.textContent = `${data.length} aday bulundu.`;
    renderCandidateResults(results, data);
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
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
    const data = await api("/nl-search", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    const candidates = data.results || [];
    const parsed = data.parsed_query || {};
    if (message) {
      message.textContent = `${candidates.length} aday bulundu. Sistem sorguyu yapisal kriterlere cevirdi.`;
      message.dataset.type = "ok";
    }
    if (results) {
      renderCandidateResults(results, candidates, parsed);
    }
  } catch (error) {
    if (message) {
      message.textContent = error.message;
      message.dataset.type = "error";
    }
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
            <label>Kidem
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
            <label>Serbest metin<textarea name="free_text" rows="4" placeholder="Fintech deneyimi olan..."></textarea></label>
            <button class="primary-btn full" type="submit">Aday ara</button>
            <p class="panel-message"></p>
          </form>
        </div>
        <div class="search-mode" data-search-mode="text">
          <form class="stack-form" id="candidate-text-search-form">
            <label>Arama metni
              <textarea name="query" rows="8" placeholder="Fintech alaninda calismis senior backend gelistirici ariyoruz. Python, FastAPI, PostgreSQL ve Redis zorunlu olsun. AWS ve Kubernetes bilmesi iyi olur."></textarea>
            </label>
            <button class="primary-btn full" type="submit">Metinle aday ara</button>
            <p class="panel-message"></p>
          </form>
        </div>
      </section>
      <section class="dash-panel">
        <h2>Kayitli aramalar</h2>
        <p>Senior Python Istanbul</p>
        <p>Mobile Flutter Remote</p>
        <p>Cybersecurity ISO 27001</p>
      </section>
    </div>
    <div class="candidate-table" id="candidate-search-results">
      <div class="table-row head"><span>Aday</span><span>Skor</span><span>Aciklama</span><span>Aksiyon</span></div>
    </div>
  `;
  $("#candidate-search-form")?.addEventListener("submit", searchCandidates);
  $("#candidate-text-search-form")?.addEventListener("submit", searchCandidatesText);
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

function formatBreakdown(breakdown = {}) {
  const entries = Object.entries(breakdown);
  if (!entries.length) return `<p class="muted-line">Skor kirilimi yok.</p>`;
  return entries
    .map(([name, value]) => `<article><span>${name.replaceAll("_", " ")}</span><strong>${value}</strong></article>`)
    .join("");
}

function renderPills(items = [], key = null) {
  const values = items
    .map((item) => (key && item ? item[key] : item))
    .filter(Boolean)
    .slice(0, 18);
  if (!values.length) return `<p class="muted-line">Kayit yok.</p>`;
  return `<div class="pill-list">${values.map((value) => `<span>${value}</span>`).join("")}</div>`;
}

function renderTimeline(items = []) {
  if (!items.length) return `<p class="muted-line">Deneyim kaydi yok.</p>`;
  return items
    .slice(0, 4)
    .map(
      (item) => `
        <article class="modal-timeline-item">
          <strong>${item.role || "Rol belirtilmedi"}</strong>
          <span>${item.company || "Sirket belirtilmedi"} / ${item.start_date || "-"} - ${item.end_date || (item.is_current ? "Devam" : "-")}</span>
          <p>${item.description || ""}</p>
        </article>`
    )
    .join("");
}

async function openCandidateModal(candidateId) {
  if (!candidateId) return;
  const searchResult = state.lastCandidates.get(candidateId) || {};
  let detail = {};
  try {
    detail = await api(`/candidates/${candidateId}`);
  } catch (error) {
    detail = {};
  }
  const candidate = { ...detail, ...searchResult };
  const modal = ensureCandidateModal();
  const cvButton = candidate.cv_available
    ? `<a class="primary-btn small" href="${API_BASE}/download-cv/${candidateId}" target="_blank" rel="noreferrer">Hashli CV indir</a>`
    : `<button class="ghost-btn" type="button" disabled>CV yok</button>`;

  $(".candidate-modal-body", modal).innerHTML = `
    <div class="modal-head">
      <div>
        <p class="eyebrow">Aday detayi</p>
        <h2>${candidate.name || "Aday"}</h2>
        <p>${candidate.summary || "Ozet bulunamadi."}</p>
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
        <h3>Skor kirilimi</h3>
        <div class="breakdown-grid">${formatBreakdown(candidate.score_breakdown)}</div>
      </section>
      <section>
        <h3>Iletisim</h3>
        <p class="muted-line">${candidate.email || "-"}<br>${candidate.phone || "-"}<br>${candidate.location || "-"}</p>
      </section>
    </div>
    <section>
      <h3>Eslesme aciklamasi</h3>
      <ul class="reason-list">${(candidate.reasons || []).map((reason) => `<li>${reason}</li>`).join("") || "<li>Aciklama yok.</li>"}</ul>
    </section>
    <section>
      <h3>Yetenekler</h3>
      ${renderPills(candidate.skills, typeof candidate.skills?.[0] === "object" ? "name" : null)}
    </section>
    <section>
      <h3>Deneyim</h3>
      ${renderTimeline(candidate.experiences || [])}
    </section>
    <div class="modal-grid">
      <section>
        <h3>Egitim</h3>
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
  $(".candidate-modal")?.classList.remove("active");
  document.body.classList.remove("modal-open");
}

function ensureCandidateModal() {
  let modal = $(".candidate-modal");
  if (modal) return modal;
  modal = document.createElement("div");
  modal.className = "candidate-modal";
  modal.innerHTML = `
    <div class="candidate-modal-backdrop" data-modal-close></div>
    <article class="candidate-modal-card" role="dialog" aria-modal="true" aria-label="Aday detayi">
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

    if (event.target.closest("[data-modal-close]")) {
      closeCandidateModal();
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
          setMessage("Giris basarili.");
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
        setMessage("Hesap olusturuldu.");
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
