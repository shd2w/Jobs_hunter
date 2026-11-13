# 05 — User Experience and Workflows

Status: design document, 2026-11-01. Part of [FINAL_SYSTEM_STRATEGY_AND_DESIGN.md](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md).
Today's UI (verified by reading `jobhunter_ui/static/index.html`): three tabs — **Jobs**, **Find & score**, **Setup**. The target grows it to six areas without adding screens "to look comprehensive".

## 1. Information architecture

| Nav item | Contains | Replaces / extends today |
|---|---|---|
| **Overview** | next actions, new matches since last visit, source problems, application funnel counts, backup/AI-key warnings | new (small) |
| **Jobs** | ranked list, filters, saved searches ("search history" lives here), possible-duplicates queue; **Job detail** drawer/page | extends *Jobs* |
| **Tracker** | applications by status, events, reminders, "ready to apply" hand-off/export | extends status dropdown |
| **Profile** | identity, skills with level+state, languages, experience, education, preferences/exclusions, **CV documents** (originals, extraction review, working base CV) | extends *Setup* |
| **Sources** | registry table, state/health, last run, run history, add watch company, policy badges | replaces *Find & score* run panel (runs start from here and from Overview) |
| **Settings & Diagnostics** | AI providers/keys (never displayed again), thresholds/weights, notifications, data location, backups, health report, logs | extends *Setup* |

Deliberately **not** separate screens: Skill-gap and Learning (sections inside Job detail and Profile → "Skills to develop"), Analytics (cards on Overview; no BI screen), Notifications (a list under Overview plus rules in Settings), Search history (saved searches in Jobs). Rationale: each would otherwise be an almost empty page for a single-user local tool.

Terminology (used identically in UI, CLI and docs): *Job*, *Match* (the 0–100 result), *Score* (legacy 1–5, shown only as a secondary label), *Source*, *Run*, *Draft*, *Approved*, *Ready to apply*. "Evaluated" and "Matched" are not synonyms: a job can be matched (deterministic) without an AI evaluation.

## 2. Onboarding (two entry paths, one profile)

First start shows **Welcome** with two buttons and a "Skip for now — just search" link; the minimum to search is *target roles + at least one location*, nothing else.

**Path A — Manual:** a five-step form (Basics → Roles & locations → Skills → Languages → Experience & education). Every step is skippable; a progress meter shows "profile completeness" (information, not a gate). Skill rows offer an optional level; leaving it blank stores `unknown`, not a guess.

**Path B — CV-assisted:**
1. Upload (`.pdf`, `.docx`, `.md`, `.txt`, ≤ 10 MB). The file is validated (extension + content sniff + size), stored read-only by hash, never altered.
2. Extraction runs **locally by rules first** (headings, dates, language/skill vocabularies). A banner explains: *"Optional: improve extraction with an AI provider. This sends your CV text (without name, email, phone) to <provider>. [Use AI once] [No thanks]"* — consent is per use and logged.
3. **Review screen**: left = original text with highlighted spans; right = extracted fields with a confidence chip. Each field: ✔ accept · ✎ edit · ✖ reject. Anything not accepted stays out of the confirmed profile. Skill levels extracted from prose appear as *unconfirmed*.
4. "Save profile" creates `profile_version 1`; confirmed vs unconfirmed counts are shown ("12 skills confirmed, 8 need a level").

Both paths end in the same `profile_version` structure; the Profile page is the single place to edit later. Existing users: the first run after upgrade offers **"Import from config/profile.yml"** with the mapping review from doc 04 §3.3 (all levels `unknown`/`self_declared`; the language-level conflict is shown as a warning to resolve).

## 3. Screens and component responsibilities

### 3.1 Jobs (list)
Columns: title/company, **Match** with confidence chip, top-3 reasons, location/remote, source badges (ATS / board / feed), posted/first seen, application state. Controls: search box (multilingual, case/diacritic-insensitive), filters (state, source type, location, remote, language requirement, min match, "hide closed", "only possible duplicates"), sort (match, newest, company), re-weight sliders (five legacy dimensions), saved searches, bulk select → "Save", "Mark not interested". Ranking = match descending, ties by skill coverage then newest (existing rule kept). **Works with AI switched off:** matching, ranking, filters and tracking use only deterministic logic; the AI-dependent parts show "Explanation unavailable (AI off)" rather than disappearing.

### 3.2 Job detail
Header (title, company, source links incl. secondary sightings, lifecycle badge `new/updated/closed`). Tabs: **Fit** (match bar + confidence, signal table with ✓/✗/? per requirement and the evidence quote from the posting, "missing critical" list, which profile facts counted and their state), **Skills** (gap list: *missing*, *level too low*, *unconfirmed — confirm to count*; link to learning suggestions), **Description** (plain text), **History** (sightings, changes, application events), **Documents**. Action bar: Save · Track · **Tailor CV for this job** · **Write cover letter** · Mark not interested. Nothing in this screen creates a document except the two explicit buttons.

### 3.3 Documents (inside Job detail)
See section 5.

### 3.4 Tracker
Kanban/table by status (`saved, preparing, ready_to_apply, applied, interview, offer, accepted/declined, rejected, withdrawn, archived`), notes, due reminders, undo of the last status change (from the event log), "Export queue for UniversalAutoApplier" (lists exactly which jobs qualify and why others are skipped, reusing the exporter's skip reasons).

### 3.5 Sources
Table: source, type, **state** (proposed/validating/shadow/active/degraded/blocked/disabled), **policy badge** (allowed / review / disabled by policy), last attempt, last success, last error, yield (7-day median vs last), coverage, next allowed run (cooldown). Row actions: Check now (health probe), Run now, Enable/Disable, "Why is this blocked?" (shows HTTP status class and the stop-on-block rule). **Add watch company**: type a name → suggestions from the ATS directory snapshot or paste a careers URL/slug → probe → saved as `validating`. Consumer boards appear in a separate "Restricted sources" group with the acknowledgement checkbox; SmartRecruiters/Google Jobs show "Disabled by policy" with the reason.

### 3.6 Settings & Diagnostics
AI providers (key present ✔/✖, headroom today, last error class — keys never shown), model lists, privacy switches (allow AI CV extraction, allow AI evaluation), notification rules/quiet hours/Telegram test, weights, thresholds, backup now/restore, data folder, health report (same as `run_health.py`), log viewer (last 200 lines, filtered).

## 4. User journeys

Each journey lists steps and the **states the UI must show**: loading (skeleton + cancel for runs), empty (what to do next), partial (what worked, what failed), success, error (specific code + next step).

1. **First-time onboarding** — Welcome → choose path → minimal profile → "Find jobs" (runs only sources in `allowed` state: remote feeds + any watch companies; if none configured it says so and offers *Add watch company*, *Paste a job link*, *Import CSV*) → Jobs list. Empty state if nothing found: shows which sources ran and their results.
2. **Upload & review CV** — as 2/Path B; errors: unsupported type, too large, unreadable PDF (offer paste text), AI consent declined (continue with rules). Partial: some fields extracted → highlights what's missing.
3. **Complete profile manually** — each save creates a version; "undo" = revert; validation messages inline (CEFR list, date order).
4. **Run a job search** — from Overview/Sources: "Find jobs" runs a *run* with per-source progress rows (queued/running/done/blocked/skipped-cooldown), live counts, cancel. Result summary: new, updated, closed, duplicates linked, per-source errors in plain words. The UI claims "more results available" **only** when the adapter returned continuation proof.
5. **Understand a match** — Job detail → Fit: bar + confidence; each requirement row shows quote, verdict, profile fact used and its state; unknowns are listed as "not enough information" instead of being scored as failures.
6. **Review skill gaps** — Profile → "Skills to develop": gaps aggregated across your top-N jobs ordered by how many jobs need them; each shows *missing / level too low / unconfirmed*; optional suggested resources (rule-based list), no certification promises.
7. **Save a job and track an application** — Save → status `saved`; move to `preparing`; notes; when documents are approved and the user clicks **Ready to apply** the job becomes eligible for export; `applied` records date; reminders optional. Everything without AI.
8. **Tailor a CV for one job** — see section 5.
9. **Manage sources / diagnose failures** — Overview shows a red chip "2 sources need attention" → Sources → row explains (e.g. *Blocked: HTTP 429 at 10:41, cooling down until 11:41; JobHunter does not retry through blocks*), offers Check now / Disable / open docs. Anomaly (volume drop) shows as `degraded` with the numbers compared.

## 5. CV and job-specific document workflow

**Trigger:** only the buttons *Tailor CV for this job* / *Write cover letter* in a job's detail. No scan, evaluation, threshold, import or schedule can call them (tested at call-graph level and by the DB constraint in doc 04 §3.7). CLI equivalent requires `--url` for one job.

| Step | System behaviour |
|---|---|
| 1 Confirm | Dialog: *"Create a tailored CV for <job>? Uses your confirmed profile and base CV. Facts (dates, employers, education, languages) are never changed. If you allow AI, the job text and the CV text (without contact details) are sent to <provider>."* Options: *Use AI* / *Rule-based only (reorder skills, pick projects)* / Cancel. |
| 2 Draft | `DocumentService` builds a patch (subtitle, objective keywords, skills order, bullet rephrasings, project selection — the existing `CVTailor` JSON-patch design) and applies it programmatically to the **working base CV**. A patch that touches a protected field is rejected by validation. Failure → status `failed`, nothing stored as a CV. |
| 3 Review | Side-by-side diff (base vs draft) + rendered PDF preview; every changed line has an *accept/revert* toggle; a **facts check** list shows protected fields unchanged ✔ and any language/skill claim not present in the confirmed profile ⚠. |
| 4 Decide | **Approve** (status `approved`, version frozen) · **Regenerate** (new version n+1; old kept) · **Discard**. |
| 5 Export | Explicit **Export** choice (PDF and/or Markdown) to a folder the user picks (default `output/<job-slug>/v<n>/`); export is logged; the file name contains job and version. |

**Versioning/storage:** `generated_document` rows `(job, kind, version)` + files `output/<job-slug>/v<n>/cv.md|pdf` (same `output/` tree as today); each row stores base CV hash, profile version, patch JSON, model; the **original upload and the working base CV are never overwritten** (edits to the base CV create a new `cv_document` row, as the existing `cv.md.bak` practice already hints). Retention: drafts 90 days unless approved; approved/exported kept.

## 6. Cross-cutting UX rules

- **Language/multilingual:** UI strings are English now with an i18n table (key→text) so German can be added; **job postings are collected in English and German only** (a language filter shows `en`/`de`; other languages are hidden with reason "language"); text, company names and search terms are Unicode-safe (existing UTF-8 logging tests stay).
- **Honest status:** a run is "Running", "Done", "Done with problems", "Blocked", "Cancelled"; never "Done" if a source failed; "0 jobs" is always accompanied by the reason (filters removed N, source errored, cooldown).
- **Data safety:** every destructive action (discard draft, revert profile, restore backup) is undoable or confirmed; secrets are write-only fields.
- **Accessibility:** keyboard operable, ARIA live regions for toasts (existing), contrast per WCAG AA; verified by the browser tests in doc 06.
- **Untrusted text:** job descriptions, company names, error strings from providers are rendered as text only (existing rule, covered by server tests) and are never used as HTML, URLs without scheme checks, or prompt instructions.

## 7. Revision 1 UX additions (amend §2–§6)

Rationale and rules: [08](08_REVISION_1_PLATFORM_SCOPE_AND_REVIEW_RESPONSE.md) §4.

- **Defaults-first review (replaces mandatory review in §2).** CV extraction auto-accepts high-confidence fields into the profile, lists them under "Recently added automatically" with one-click undo, and leaves low-confidence fields empty. Auto-accepted skill/language levels stay *unconfirmed* until the user presses Confirm. Onboarding asks at most three short questions: **languages with levels, where you can work, relocation (yes / no / conditional)**; everything else is optional. Possible duplicates are grouped automatically (collapsed, undoable); there is no review queue. AI use is one setting made at onboarding. A weekly digest offers up to five things worth confirming.
- **Eligibility.** Profile → "Where can you work?" collects work authorisation per country (citizen / resident / work permit / needs sponsorship / not authorised), nationalities (kept off AI payloads), a relocation plan (willing, countries or "any", earliest start, needs sponsorship / relocation support) and remote constraints (home country, time-zone window). Job rows show an **eligibility chip**: *Eligible*, *Check* (unknown) or *Not eligible* (hidden by default, listed under "Not eligible (N)" with reasons and the quote from the posting). Missing profile data produces a prompt, never a guess.
- **Add jobs (imports).** Jobs → "Add jobs": paste text or URLs, upload `.eml`/`.mbox` alert emails, forward a message to the Telegram bot, or import CSV. High-confidence results are saved at once with undo; low-confidence ones open a one-screen preview. Imported jobs are private to the user in hosted mode. Links in emails are shown as written and never followed automatically.
- **Hidden jobs panel.** Every list shows "N hidden — why?" with the breakdown (language, your filters, not eligible, duplicate group). Nothing is deleted by a filter; changing a filter instantly brings jobs back.
- **Feedback.** Each job has Save, Apply, Ignore (reason chips: not interested, wrong seniority, wrong location, salary, company, language, not eligible, other) and, in Tracker, employer outcomes. Suggestions appear as one-click banners ("Hide jobs mentioning X?"); the soft ranking adjustment is capped, labelled ("adjusted by your choices +4") and can be switched off.
- **Salary.** Shown exactly as stated (amount, currency, period, gross/net note, tax note) in list and detail; never converted or scored. A "has stated salary" filter is available.
- **Seniority and skills** shown with their evidence ("10+ years required" → Senior); unmapped skills are listed too, not dropped. Level guesses made from the title alone are labelled **"from title only"** and never hide a job.
- **Scheduler.** Overview shows the next scheduled scan per source group and a "Pause all" switch; "Find jobs now" uses the same single scheduler.

## 8. Revision 2–3 UX additions (amend §3.5 Sources and §7)

Rules and evidence: [09](09_REVIEW_AND_METHODOLOGY_SPECIFICATION.md), [10](10_METHODOLOGY_FEASIBILITY_REVIEW.md).

- **Sources → Discovery tab.** Shows the funnel per channel for the last 7 days (found → recognised → verified → active with in-scope jobs) and the **"Wanted connectors"** list: ATS families recognised often but with no adapter, ranked by count (this is the data-driven order for the next connector). Candidates blocked by policy are listed with the reason; nothing here is polled.
- **Onboarding queue.** Adding many companies at once is allowed; boards are admitted at the daily throttle and the page says "N boards waiting — next batch tomorrow" instead of failing.
- **Guard messages in plain words.** "Job count dropped 60 % (412 → 165). Confirming the new level (2 of 3 checks); nothing was closed." and, for a drop to zero, "Board returned 0 jobs. Waiting for confirmation (3 of 8 checks over 24 h) before closing anything."
- **Chips.** `from title only` (seniority), `language unknown` (short text without a provider language), `staffing agency (advisory)`, `eligibility: check`. Each chip has a one-line explanation and can be dismissed by the user.
- **Monitoring wording.** Small boards show "too few jobs for trend alerts — covered by the provider-level check"; the provider cohort chart is on Diagnostics.
- **Company page.** Name, registrable domain, aliases (merge/undo), recognised ATS, tier and why, last probe, jobs in your scopes.
- **Careers-page probe results** (when that optional adapter exists) appear as "found an embedded Greenhouse board on careers.example.com — add to watch-list?" with Accept / Ignore; the probe never runs without the owner enabling it.

