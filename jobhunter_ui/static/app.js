"use strict";
// All dynamic text is inserted with textContent (job data comes from the web: never innerHTML).
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else if (k === "style") e.style.cssText = v;
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
  return e;
}
function put(el, ...kids) { el.replaceChildren(...kids.flat(Infinity).filter(c => c != null && c !== false)); }
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-JobHunter": "1" }, body: JSON.stringify(body) };
  let r;
  try { r = await fetch(path, opt); } catch { throw new Error("Cannot reach the app. Is the terminal window still running?"); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error ? d.error.message : "Something went wrong (" + r.status + ").");
  return d;
}
function toast(msg, err) {
  const t = h("div", { class: "toast" + (err ? " err" : "") }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), err ? 9000 : 4000);
}
const fmtDate = s => (s || "").slice(0, 10);
const NAMES = { skills_match: "Skills", education_match: "Education", location: "Location", language: "Language", growth: "Growth" };
const REC = { apply: "Apply", consider: "Consider", skip: "Skip", skip_german: "German needed" };
const STATUS = { new: "New", saved: "Saved", applied: "Applied", interview: "Interview", offer: "Offer", rejected: "Rejected", archived: "Archived" };
const S = { setup: null, tab: "jobs", f: { q: "", min: "0", rec: new Set(), status: "", hideGerman: true, ready: false }, weights: null, open: null, data: null, custom: false };

// ---------- tabs / header ----------
function showTab(t) {
  S.tab = t;
  for (const b of document.querySelectorAll("#tabs button")) b.setAttribute("aria-selected", String(b.dataset.tab === t));
  for (const n of ["jobs", "run", "setup"]) $("#view-" + n).hidden = n !== t;
  if (t === "jobs") loadJobs(); if (t === "run") renderRun(); if (t === "setup") renderSetup();
}
document.querySelectorAll("#tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));

async function refreshSetup() {
  S.setup = await api("/api/setup");
  const s = S.setup, p = $("#pills");
  put(p,
    h("span", { class: "pill " + (s.cv.ok ? "ok" : "warn") }, s.cv.ok ? "CV ready" : "CV needed"),
    h("span", { class: "pill " + (s.ai.configured ? "ok" : "warn") }, s.ai.configured ? "AI ready" : "AI key missing"),
    h("span", { class: "pill" }, s.counts.evaluated + " scored · " + s.counts.pending + " waiting"));
  const steps = [];
  if (!s.cv.exists) steps.push(["Add your CV", "setup"]);
  else if (!s.cv.ok) steps.push(["Fix your CV format (missing: " + s.cv.missing.join(", ") + ")", "setup"]);
  if (!s.ai.configured) steps.push(["Add a free AI key to score jobs and tailor CVs", "setup"]);
  const b = $("#banner");
  b.hidden = !steps.length;
  if (steps.length) put(b, h("strong", {}, "Quick start — finish these to unlock everything:"),
    h("ol", {}, steps.map(([t, tab]) => h("li", {}, h("a", { onclick: () => showTab(tab) }, t)))));
}

// ---------- jobs ----------
function qs() {
  const f = S.f, p = new URLSearchParams();
  if (f.q) p.set("q", f.q); if (+f.min) p.set("min", f.min);
  if (f.rec.size) p.set("rec", [...f.rec].join(",")); if (f.status) p.set("status", f.status);
  p.set("hide_german", f.hideGerman ? "1" : "0"); if (f.ready) p.set("ready", "1");
  if (S.weights && S.custom) p.set("weights", Object.entries(S.weights).map(([k, v]) => k + ":" + v).join(","));
  return p.toString();
}
let jobsTimer;
async function loadJobs(keepScroll) {
  clearTimeout(jobsTimer);
  const root = $("#view-jobs");
  try {
    const d = await api("/api/jobs?" + qs());
    S.data = d;
    if (!S.weights) S.weights = Object.fromEntries(Object.entries(d.weights).map(([k, v]) => [k, Math.round(v * 100)]));
    renderJobs(root);
  } catch (e) { put(root,h("div", { class: "empty" }, e.message)); }
}
function renderJobs(root) {
  const d = S.data, f = S.f;
  const search = h("div", { class: "grow" }, h("label", { for: "q" }, "Search"),
    h("input", { type: "search", id: "q", placeholder: "Company, title or keyword", value: f.q, oninput: e => { f.q = e.target.value; clearTimeout(jobsTimer); jobsTimer = setTimeout(() => loadJobs(), 250); } }));
  const min = h("div", {}, h("label", { for: "min" }, "Best matches"),
    h("select", { id: "min", onchange: e => { f.min = e.target.value; loadJobs(); } },
      [["0", "All scores"], ["3", "3.0 and up"], ["3.5", "3.5 and up"], ["4", "4.0 and up"]].map(([v, t]) => h("option", { value: v, selected: f.min === v }, t))));
  const st = h("div", {}, h("label", { for: "st" }, "My progress"),
    h("select", { id: "st", onchange: e => { f.status = e.target.value; loadJobs(); } },
      [["", "Any"], ...Object.entries(STATUS)].map(([v, t]) => h("option", { value: v, selected: f.status === v }, t))));
  const chips = h("div", { class: "row" }, ["apply", "consider", "skip"].map(r =>
    h("label", { class: "row small" }, h("input", { type: "checkbox", checked: f.rec.has(r), onchange: e => { e.target.checked ? f.rec.add(r) : f.rec.delete(r); loadJobs(); } }), REC[r])),
    h("label", { class: "row small" }, h("input", { type: "checkbox", checked: f.ready, onchange: e => { f.ready = e.target.checked; loadJobs(); } }), "CV ready"),
    h("label", { class: "row small" }, h("input", { type: "checkbox", checked: !f.hideGerman, onchange: e => { f.hideGerman = !e.target.checked; loadJobs(); } }), "Show jobs needing German"));
  const wbtn = h("button", { class: "btn", onclick: () => { S.showW = !S.showW; renderJobs(root); } }, "Ranking: " + (d.custom_weights ? "my priorities" : "AI score") + " ▾");
  const panel = S.showW ? weightsPanel(root) : null;
  const note = h("p", { class: "muted small" }, `Showing ${d.shown} of ${d.total} scored jobs, best first. Scores are 1–5; ${d.threshold}+ is worth applying to.`);
  put(root,h("div", { class: "toolbar" }, search, min, st, wbtn), chips, panel, note,
    d.jobs.length ? d.jobs.map(jobCard) : h("div", { class: "empty card" }, d.total ? "No jobs match these filters." : "No scored jobs yet. Go to “Find & score” to search and score jobs."));
}
function weightsPanel(root) {
  const w = S.weights;
  const sliders = Object.keys(NAMES).map(k => {
    const out = h("span", { class: "small muted" }, w[k] + "%");
    return h("div", {}, h("label", { for: "w" + k }, NAMES[k]),
      h("input", { type: "range", id: "w" + k, min: 0, max: 100, step: 5, value: w[k], oninput: e => { w[k] = +e.target.value; out.textContent = w[k] + "%"; S.custom = true; clearTimeout(jobsTimer); jobsTimer = setTimeout(() => loadJobs(), 200); } }), out);
  });
  return h("div", { class: "card" }, h("strong", {}, "What matters most to you?"),
    h("p", { class: "muted small" }, "Drag to re-rank all jobs instantly using your own priorities. Default is the AI’s mix (30/20/20/20/10)."),
    h("div", { class: "weights" }, sliders),
    h("button", { class: "btn", onclick: () => { S.weights = { skills_match: 30, education_match: 20, location: 20, language: 20, growth: 10 }; S.custom = false; loadJobs(); } }, "Reset to AI score"));
}
function jobCard(j) {
  const open = S.open === j.id;
  const ready = [j.artifacts.cv.pdf && h("span", { class: "chip ready" }, "CV ✓"), j.artifacts.cover.pdf || j.artifacts.cover.md ? h("span", { class: "chip ready" }, "Letter ✓") : null];
  const head = h("button", { class: "head", "aria-expanded": String(open), onclick: () => { S.open = open ? null : j.id; renderJobs($("#view-jobs")); if (!open) loadDetail(j.id); } },
    h("div", { class: "rank" }, "#" + j.rank),
    h("div", { class: "score " + j.tier, title: "Score out of 5" }, j.score.toFixed(1)),
    h("div", {}, h("div", { class: "title" }, j.title), h("div", { class: "sub" }, j.company + (j.date_posted ? " · posted " + fmtDate(j.date_posted) : "")),
      h("div", { class: "chips" }, h("span", { class: "chip " + j.recommendation }, REC[j.recommendation] || j.recommendation || "—"),
        j.german_level && j.german_level !== "none" ? h("span", { class: "chip" }, "German " + j.german_level) : null, ready,
        j.status !== "new" ? h("span", { class: "chip" }, STATUS[j.status]) : null)),
    h("div", { class: "right muted" }, open ? "▲" : "▼"));
  return h("div", { class: "job", id: "job-" + j.id }, head, open ? h("div", { class: "detail", id: "d-" + j.id }, h("p", { class: "muted" }, "Loading…")) : null);
}
async function loadDetail(id) {
  try { fillDetail(await api("/api/jobs/" + id)); } catch (e) { toast(e.message, true); }
}
function fillDetail(j) {
  const box = $("#d-" + j.id); if (!box) return;
  const bars = Object.keys(NAMES).filter(k => k in j.scores).flatMap(k => [h("span", {}, NAMES[k]), h("div", { class: "bar" }, h("i", { style: "width:" + (j.scores[k] / 5 * 100) + "%" })), h("strong", {}, j.scores[k])]);
  const a = j.artifacts, f = p => "/files/" + p.split("/").map(encodeURIComponent).join("/");
  const links = [];
  if (a.cv.pdf) links.push(h("a", { href: f(a.cv.pdf), target: "_blank", rel: "noopener" }, "Open CV (PDF)"));
  if (a.cv.md) links.push(h("a", { href: f(a.cv.md) + "?download=1" }, "CV text"));
  if (a.cover.pdf) links.push(h("a", { href: f(a.cover.pdf), target: "_blank", rel: "noopener" }, "Open cover letter (PDF)"));
  if (a.cover.md) links.push(h("a", { href: f(a.cover.md) + "?download=1" }, "Letter text"));
  const status = h("select", { "aria-label": "My progress", onchange: async e => { try { fillDetail(await api("/api/jobs/" + j.id + "/status", { status: e.target.value })); toast("Saved"); loadJobs(); } catch (x) { toast(x.message, true); } } },
    Object.entries(STATUS).map(([v, t]) => h("option", { value: v, selected: j.status === v }, t)));
  const note = h("input", { type: "text", placeholder: "Private note (saved when you click away)", value: j.note, maxlength: 2000, onchange: async e => { try { await api("/api/jobs/" + j.id + "/status", { note: e.target.value }); toast("Note saved"); } catch (x) { toast(x.message, true); } } });
  const busy = (btn, label, fn) => async () => {
    const all = box.querySelectorAll("button"); all.forEach(b => b.disabled = true);
    const old = btn.textContent; btn.replaceChildren(h("span", { class: "spin" }), label);
    try { const r = await fn(); (r.warnings || []).forEach(w => toast(w, true)); toast("Done"); fillDetail(r.id ? r : await api("/api/jobs/" + j.id)); loadJobsQuiet(); }
    catch (e) { toast(e.message, true); all.forEach(b => b.disabled = false); btn.textContent = old; }
  };
  const bTailor = h("button", { class: "btn primary" }, a.cv.kind === "tailored" ? "Re-create tailored CV" : "Create tailored CV");
  bTailor.onclick = busy(bTailor, "Tailoring… up to a minute", () => api("/api/jobs/" + j.id + "/cv", { mode: "tailored" }));
  const bBase = h("button", { class: "btn" }, "Use my CV as is");
  bBase.onclick = busy(bBase, "Preparing…", () => api("/api/jobs/" + j.id + "/cv", { mode: "base" }));
  const bCover = h("button", { class: "btn primary" }, (a.cover.md || a.cover.pdf) ? "Re-write cover letter" : "Write cover letter");
  bCover.onclick = busy(bCover, "Writing… up to a minute", () => api("/api/jobs/" + j.id + "/cover", {}));
  const bBoth = h("button", { class: "btn" }, "Create both");
  bBoth.onclick = busy(bBoth, "Working… up to two minutes", () => api("/api/jobs/" + j.id + "/both", { mode: "tailored" }));
  const bTg = h("button", { class: "btn" }, "Send to Telegram");
  bTg.onclick = busy(bTg, "Sending…", async () => { const r = await api("/api/jobs/" + j.id + "/telegram", {}); toast("Sent: " + r.sent.join(", ")); return {}; });
  const desc = j.description ? h("details", {}, h("summary", {}, "Job description"), h("p", { class: "small", style: "white-space:pre-wrap" }, j.description.slice(0, 6000))) : null;
  put(box,
    h("p", {}, j.summary), h("div", { class: "bars" }, bars),
    j.highlights.length ? [h("h3", {}, "Why it fits"), h("ul", { class: "tight" }, j.highlights.map(x => h("li", {}, x)))] : null,
    j.gaps.length ? [h("h3", {}, "Gaps to be aware of"), h("ul", { class: "tight" }, j.gaps.map(x => h("li", {}, x)))] : null,
    j.reasoning ? h("p", { class: "small muted" }, j.reasoning) : null, desc,
    h("div", { class: "actions" },
      h("strong", {}, "Prepare your application"),
      h("div", { class: "row" }, bTailor, bBase, bCover, bBoth),
      links.length ? h("div", { class: "row links" }, links) : h("p", { class: "muted small" }, "Nothing created yet. “Tailor” rewrites only wording and keyword order for this job — dates, education and languages are never touched."),
      h("div", { class: "row" }, h("a", { class: "btn", href: j.url, target: "_blank", rel: "noopener noreferrer" }, "Open job posting ↗"), S.setup && S.setup.telegram.configured ? bTg : null)),
    h("div", { class: "row" }, h("label", { class: "row small" }, "My progress", status), h("div", { class: "grow", style: "flex:1;min-width:200px" }, note)));
}
function loadJobsQuiet() { api("/api/jobs?" + qs()).then(d => { S.data = d; refreshSetup(); }).catch(() => { }); }

// ---------- run ----------
let poll, since = 0;
async function renderRun() {
  const root = $("#view-run"), s = S.setup || await api("/api/setup");
  const pending = s.counts.pending;
  const o = S.run = S.run || { batch: 5, threshold: "", german: "", create_cv: false };
  const mk = (task, title, text, primary) => h("div", { class: "card" }, h("h3", {}, title), h("p", { class: "muted small" }, text),
    h("button", { class: "btn" + (primary ? " primary" : ""), onclick: () => start(task) }, title));
  put(root,
    h("h2", {}, "Find and score jobs"),
    h("p", { class: "muted" }, `${pending} job${pending === 1 ? " is" : "s are"} waiting to be scored. Results appear in the Jobs tab, best first.`),
    h("div", { class: "tasks" },
      mk("scan", "Find new jobs", "Searches the boards and companies set in config/portals.yml. No AI needed.", false),
      mk("evaluate", "Score new jobs", "The AI reads each waiting job and scores it for you (uses your AI keys).", true),
      mk("all", "Do everything", "Find, score and notify in one go (the original automatic run).", false),
      mk("export", "Export application queue", "Writes data/application_queue.jsonl for UniversalAutoApplier from jobs that have a CV and letter.", false),
      mk("health", "Check setup", "Tests files, keys and PDF support and tells you what to fix.", false)),
    h("details", { class: "card" }, h("summary", {}, "Options for scoring"),
      h("div", { class: "grid2", style: "margin-top:10px" },
        h("div", {}, h("label", { for: "ob" }, "How many jobs to score now"), h("input", { type: "number", id: "ob", min: 1, max: 100, value: o.batch, onchange: e => o.batch = e.target.value })),
        h("div", {}, h("label", { for: "ot" }, "Minimum score for a letter (blank = from Setup)"), h("input", { type: "number", id: "ot", min: 1, max: 5, step: 0.1, value: o.threshold, onchange: e => o.threshold = e.target.value })),
        h("div", {}, h("label", { for: "og" }, "German filter (blank = from Setup)"), h("select", { id: "og", onchange: e => o.german = e.target.value }, [["", "Use my Setup choice"], ...s.german_policies.map(p => [p, p.replace(/_/g, " ")])].map(([v, t]) => h("option", { value: v, selected: o.german === v }, t)))),
        h("label", { class: "row small" }, h("input", { type: "checkbox", checked: o.create_cv, onchange: e => o.create_cv = e.target.checked }), "Also auto-create a tailored CV for every high-scoring job (otherwise you choose per job)"))),
    h("div", { class: "row" }, h("strong", { id: "runlabel" }, "Output"), h("button", { class: "btn danger", id: "stopbtn", hidden: true, onclick: () => api("/api/run", { stop: true }).then(() => toast("Stopping…")) }, "Stop")),
    h("pre", { class: "log", id: "log", "aria-live": "off" }, "Nothing running."));
  since = 0; $("#log").textContent = ""; pollRun(true);
}
async function start(task) {
  const o = S.run;
  try { await api("/api/run", { task, batch: o.batch, threshold: o.threshold, german_policy: o.german, create_cv: o.create_cv }); since = 0; $("#log").textContent = ""; pollRun(true); }
  catch (e) { toast(e.message, true); }
}
async function pollRun(first) {
  clearTimeout(poll);
  if (S.tab !== "run") return;
  try {
    const r = await api("/api/run?since=" + since), log = $("#log"); if (!log) return;
    if (r.lines.length) { const nearEnd = log.scrollTop + log.clientHeight > log.scrollHeight - 40; log.textContent += (log.textContent ? "\n" : "") + r.lines.join("\n"); if (nearEnd) log.scrollTop = log.scrollHeight; }
    since = r.next;
    $("#stopbtn").hidden = !r.running;
    $("#runlabel").textContent = r.task ? r.label + (r.running ? " — running…" : r.returncode === 0 ? " — finished ✓" : " — stopped or failed (code " + r.returncode + ")") : "Output";
    if (!r.running && r.task && !first && r.finished) { refreshSetup(); }
    if (r.running || first) poll = setTimeout(() => pollRun(false), 1000);
  } catch { poll = setTimeout(() => pollRun(false), 3000); }
}

// ---------- setup ----------
async function renderSetup() {
  await refreshSetup();
  const s = S.setup, root = $("#view-setup"), p = s.profile;
  const cvBox = h("textarea", { id: "cvtext", spellcheck: "false", placeholder: "Paste your CV in the JobHunter format here (see the example)." });
  fetch("/files/cv.md").then(r => r.ok ? r.text() : "").then(t => { if (t && !cvBox.value) cvBox.value = t; });
  const fld = (k, label) => h("div", {}, h("label", { for: "p" + k }, label), h("input", { type: "text", id: "p" + k, value: p[k], style: "width:100%" }));
  const thr = h("input", { type: "number", id: "pthr", min: 1, max: 5, step: 0.1, value: p.auto_cv_threshold });
  const ger = h("select", { id: "pger" }, s.german_policies.map(v => h("option", { value: v, selected: p.german_filter === v }, v.replace(/_/g, " "))));
  const ccv = h("input", { type: "checkbox", id: "pccv", checked: p.create_cv });
  const keyIn = k => h("div", {}, h("label", { for: "k" + k }, k + (s.ai.keys[k] ? " ✓ saved" : "")), h("input", { type: "password", id: "k" + k, autocomplete: "off", placeholder: s.ai.keys[k] ? "Saved — leave empty to keep" : "Paste key", style: "width:100%" }));
  const tg = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"].map(k => h("div", {}, h("label", { for: "k" + k }, k), h("input", { type: "password", id: "k" + k, autocomplete: "off", placeholder: s.telegram.configured ? "Saved — leave empty to keep" : "Optional", style: "width:100%" })));
  put(root,
    h("h2", {}, "Setup"),
    h("div", { class: "card" }, h("h3", {}, "1. Your CV"),
      h("p", { class: "muted small" }, s.cv.exists ? (s.cv.ok ? "Your CV is saved and readable." : "Saved, but these sections are missing: " + s.cv.missing.join(", ") + ".") : "No CV yet. Paste it below. Your original is never changed: a backup is kept as cv.md.bak."),
      cvBox, h("div", { class: "row", style: "margin-top:8px" },
        h("button", { class: "btn primary", onclick: async () => { try { await api("/api/setup/cv", { text: cvBox.value }); toast("CV saved"); renderSetup(); } catch (e) { toast(e.message, true); } } }, "Save CV"),
        h("button", { class: "btn", onclick: async () => { const t = await fetch("/static/cv.example.md").then(r => r.text()); cvBox.value = t; } }, "Load example format"),
        h("button", { class: "btn", title: "Paste any CV text, then click. The AI only reformats; it must not add facts. Check the result.", onclick: async ev => { const b = ev.target; b.disabled = true; try { const r = await api("/api/setup/cv/convert", { text: cvBox.value }); cvBox.value = r.text; toast("Converted. Please review before saving."); } catch (e) { toast(e.message, true); } b.disabled = false; } }, "Convert pasted text with AI"))),
    h("div", { class: "card" }, h("h3", {}, "2. About you and your rules"),
      h("div", { class: "grid2" }, fld("full_name", "Full name"), fld("short_name", "Short name (file names)"), fld("subtitle", "Headline under your name"), fld("email", "Email"), fld("phone", "Phone"), fld("location", "Location"), fld("linkedin", "LinkedIn URL"), fld("github", "GitHub URL"),
        h("div", {}, h("label", { for: "pthr" }, "Worth-applying score (1–5)"), thr),
        h("div", {}, h("label", { for: "pger" }, "Jobs that need German"), ger)),
      h("label", { class: "row small", style: "margin-top:8px" }, ccv, "Automatically create a tailored CV for jobs at or above the score (otherwise you click per job)"),
      h("button", { class: "btn primary", style: "margin-top:8px", onclick: async () => {
        const d = { auto_cv_threshold: thr.value, german_filter: ger.value, create_cv: ccv.checked };
        for (const k of ["full_name", "short_name", "subtitle", "email", "phone", "location", "linkedin", "github"]) d[k] = $("#p" + k).value;
        try { await api("/api/setup/profile", d); toast("Saved (backup: profile.yml.bak)"); renderSetup(); } catch (e) { toast(e.message, true); } } }, "Save")),
    h("div", { class: "card" }, h("h3", {}, "3. AI keys (free to create)"),
      h("p", { class: "muted small" }, "Google AI Studio (aistudio.google.com) and OpenRouter (openrouter.ai) both have free tiers. Keys stay on this computer in the .env file and are never shown again."),
      h("div", { class: "grid2" }, ["GOOGLE_AI_API_KEY", "GOOGLE_AI_API_KEY2", "OpenRouter", "OpenRouter2", "OpenRouter3", "OpenRouter4"].map(keyIn)),
      h("h3", {}, "Telegram (optional)"), h("div", { class: "grid2" }, tg),
      h("button", { class: "btn primary", style: "margin-top:8px", onclick: async () => {
        const v = {}; for (const el of document.querySelectorAll("#view-setup input[type=password]")) if (el.value.trim()) v[el.id.slice(1)] = el.value.trim();
        if (!Object.keys(v).length) return toast("Nothing to save.");
        try { await api("/api/setup/keys", { values: v }); toast("Keys saved"); renderSetup(); } catch (e) { toast(e.message, true); } } }, "Save keys")),
    h("div", { class: "card" }, h("h3", {}, "4. PDF support"),
      h("p", { class: s.pdf.ok ? "" : "muted" }, s.pdf.ok ? "PDF creation is available ✓" : "PDFs cannot be created yet (" + s.pdf.error + "). CV and letter text still work. On Windows install MSYS2 + Pango as described in the README.")));
}

(async () => { try { await refreshSetup(); } catch (e) { $("#banner").hidden = false; $("#banner").textContent = e.message; } showTab("jobs"); })();
