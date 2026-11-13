# 02 — Decision Log and Scope

Status: **binding**. This file is the single authority for what is decided, what is pending, and what is in or out of scope. If any other document, prompt, work package or code comment contradicts it, this file wins; if this file is silent, the matter is **undecided** and must be raised as a pending decision, not resolved by the implementer.

Source basis: the JobHunter design suite (primary document plus design documents 01–10, revision 4), referred to as `SRC`. The file `revised_system_v2.md` was not supplied (ASM-001). Governance documents are referred to as GOV-00 … GOV-07.

## 1. Identifier scheme

| Prefix | Meaning | Defined in |
| ------ | ------- | ---------- |
| DEC-nnn | final decision | §2 |
| PCD-nnn | pending decision or blocker | §3 |
| WP-pp-nn | work package (pp = phase) | GOV-04 |
| INV-nn | architectural invariant | GOV-01 §3 |
| C-nn | component | GOV-01 §5 |
| G-n | validation gate | GOV-05 §3 |
| SC-nn | contradiction or gap in the source | §7 |
| ASM-nnn | assumption | §8 |

Status values for decisions: **Final-Owner** (stated by the owner in the Decision Log or in an owner instruction), **Final-Constraint** (a binding constraint of the original brief or non-goal), **Final-Baseline** (decided by the source design suite and binding for implementation, but not individually ratified by the owner; the owner may change it through §9).

## 2. Final decisions

This table contains 51 decisions. Assumptions are never listed here (see §8).

| ID | Decision | Source basis | Status |
| -- | -------- | ------------ | ------ |
| DEC-001 | Authority order: repository state, then Decision Log, then research, then older documents; a later numbered revision wins over an earlier one | SRC FINAL s2; docs/README authority rule | Final-Constraint |
| DEC-002 | Evolve by strangler migration, never a rewrite; existing CLI flags, exit codes, exports and tests are preserved | SRC FINAL AD-1; doc 03 s1 | Final-Baseline |
| DEC-003 | CLI and dashboard call one application service layer; no business logic or scoring constants in interfaces; layer rules enforced by a test | SRC FINAL AD-2; doc 03 s3, s8 | Final-Baseline |
| DEC-004 | The database is the authority per entity after cutover; flat files become derived exports; cutover is per entity and reversible; files are never deleted | SRC FINAL AD-3; doc 04 s1.1, s9 | Final-Baseline |
| DEC-005 | Canonical ingest model is the 30-field ats-scrapers Job; JobHunter extras live beside it; legacy JobPosting is mapped at the edge; global_id is deterministic | SRC Decision Log D2 and Conflict 1; doc 04 s2 | Final-Owner |
| DEC-006 | python-jobspy is the only consumer-board engine; wrapped as adapters; every provider off by default; exact version pinned | SRC Decision Log D1; doc 02 D1 | Final-Owner |
| DEC-007 | ats-scrapers is used as a pinned library: no fork, no [all] extra, adapter allow-list; adapters using a stealth engine or browser are blocked by policy | SRC Decision Log D2 (scope-adjusted); doc 02 D2 | Final-Owner |
| DEC-008 | Workday goal: tenants above 2,000 jobs collected completely, detail fetched only for new or changed items, global rate about 90 requests per minute | SRC Decision Log D3 (goal); doc 02 D3 | Final-Owner |
| DEC-009 | Dedup is Stage 1 (global_id and canonical URL) plus Stage 2 (company and requisition id, fuzzy match) plus exact description hash; Stage 3 MinHash is deferred by the owner; possible duplicates are grouped automatically with undo and never auto-merged or deleted | SRC Decision Log D4; owner instruction doc 08 A9 | Final-Owner |
| DEC-010 | Lifecycle: new, updated and closed change only after complete successful syncs; closing needs two consecutive complete non-empty misses; volume guard with re-baselining; global cycle breaker; small-source confirmation | SRC D4; FINAL AD-9, AD-22; doc 10 F1 | Final-Baseline |
| DEC-011 | ATS protocol traps: Greenhouse pay enrichment and Recruitee fallback ladder are built (Recruitee before 2027-02-10); Personio, Workable, Rippling are verified then patched | SRC Decision Log D5 and Conflict 4 | Final-Owner |
| DEC-012 | LinkedIn handling is limited to a query planner (filter to keyword, partition by city and date, matched_search_term, 3-7 s jitter) with a circuit breaker on the first 429; no proxies; provider state experimental and default off | SRC Decision Log D6 (scope-adjusted); doc 02 D6 | Final-Owner |
| DEC-013 | Dependency stack and pins follow Decision Log D7; hash-locked; installed by group; stamina is the single retry layer | SRC Decision Log D7; doc 06 s6 | Final-Owner |
| DEC-014 | No paid scraping or anti-bot services | SRC Decision Log D8 | Final-Owner |
| DEC-015 | No login-based scrapers and no archived tools; selenium, undetected-chromedriver, jobfunnel, python-jobscrape, jobspy2, jobsparser are blocked by a test | SRC Decision Log D9; doc 06 G3 | Final-Owner |
| DEC-016 | The CC0 ats-directory snapshot is vendored with provenance and used as a suggestion list only; never auto-enabled; the owner watch-list is the primary input | SRC Decision Log D10; doc 09 B1 | Final-Owner |
| DEC-017 | No proxy infrastructure is built | SRC Decision Log Conflict 3 | Final-Owner |
| DEC-018 | Workday detail fetching is incremental through persisted per-item state; at most 50 workers across distinct tenants | SRC Decision Log Conflict 2 | Final-Owner |
| DEC-019 | CVs and cover letters are created only by DocumentService on an explicit per-job user action; a database constraint requires the action reference; automatic creation and the create_cv and auto_cv_threshold settings are removed | SRC brief s5.3; doc 02 RC-1; FINAL AD-7 | Final-Constraint |
| DEC-020 | Original uploaded CV files are immutable and stored by hash; generated documents are versioned; export is an explicit user choice | SRC brief s5.3; doc 04 s3.5-3.7; doc 05 s5 | Final-Constraint |
| DEC-021 | Skills and languages carry a level and a provenance (confirmed, self_declared, extracted_unconfirmed, unknown); only an explicit user action sets confirmed; no import, migration or AI call may | SRC FINAL AD-6, AD-18; doc 04 s3.2 | Final-Baseline |
| DEC-022 | Matching is a deterministic ScoreCard from signals; the LLM never sets a score; the legacy 1-5 score and five dimensions are a view; weights live in one place | SRC FINAL AD-5; doc 03 s6; doc 04 s3.6 | Final-Baseline |
| DEC-023 | Eligibility is a separate per-user verdict (eligible, blocked, unknown_check) and never part of the 0-100 match; unknown is never scored as failure | SRC owner instruction doc 08 A6; FINAL AD-14 | Final-Owner |
| DEC-024 | Ingestion never deletes: global quality rules hide with a reason; user filters are per-user, query-time and token or phrase based; seniority exclusions use the derived level | SRC FINAL AD-15; doc 01 DEF-13; doc 08 s4.10 | Final-Baseline |
| DEC-025 | Salary is stored as stated (amount, currency, period, basis, tax note), displayed, and never scored, converted or compared | SRC owner instruction doc 08 A8; FINAL AD-16 | Final-Owner |
| DEC-026 | Imports (paste, .eml/.mbox, Telegram forward, CSV) are a first-class source type; tracking and redirect links are never followed; imports are private to the importer in hosted mode | SRC owner instruction doc 08 A7, A12; FINAL AD-17 | Final-Owner |
| DEC-027 | Review is optional with working defaults: high-confidence extraction is auto-accepted with undo and stays unconfirmed; at most three onboarding questions; one AI-consent setting | SRC owner instruction doc 08 A4; FINAL AD-18 | Final-Owner |
| DEC-028 | One scheduler with a single-writer lease and per-source cadences ships in the first useful release; adaptive cadence is deferred until a replay shows at least 20 percent request saving | SRC owner instruction doc 08 A15; doc 09 B11; doc 10 s5 | Final-Owner |
| DEC-029 | The company catalog grows through a multi-channel funnel; recognition reuses the library resolver; a policy gate, verification, value tiers and an onboarding throttle precede any polling; no endpoint is ever guessed | SRC FINAL AD-20; doc 09 B1-B5 | Final-Baseline |
| DEC-030 | Job languages collected are English and German only; Arabic is removed; language detection is stdlib; EN/DE lexicons; ESCO normalisation with an open vocabulary | SRC owner instruction doc 08 A1, A2, A14; FINAL AD-21 | Final-Owner |
| DEC-031 | The model is profession-agnostic: no tech-only filters, vocabularies or taxonomies | SRC owner instruction doc 08 s2.3 C-3 | Final-Owner |
| DEC-032 | Source registry with states, policy gate and circuit breaker; a first successful request does not make a source reliable; validating becomes active on green fixtures plus one canary run; SmartRecruiters and Google Jobs are disabled by policy until authorised | SRC FINAL AD-8; doc 04 s5.3; owner removal of promotion rules | Final-Owner |
| DEC-033 | No bypass: no CAPTCHA, login or paywall handling, no stealth or TLS-impersonation adapters, no retry-through-block, no following of redirect or tracking links, robots.txt honoured for non-API pages | SRC brief s7.4; doc 09 B14 | Final-Constraint |
| DEC-034 | A failed AI step is an explicit failed or partial state; error taxonomy with retries only for transient classes; per-key cooldown; no fabricated or default result | SRC brief s10; FINAL AD-12; doc 03 s7 | Final-Constraint |
| DEC-035 | JobHunter never submits applications; the UniversalAutoApplier queue export contract and identity hashes stay byte-identical; a job enters the queue only after the user marks it ready_to_apply with approved documents | SRC brief s5.1; doc 02 RC-3 | Final-Constraint |
| DEC-036 | Scope is a platform for any user and any country: one codebase runs as a local single-user app and, staged after the core, as a hosted multi-user service; user_id is present on every per-user table from the first migration | SRC owner instruction doc 08 A1, C-4; FINAL AD-13 | Final-Owner |
| DEC-037 | Two planes: shared user-independent ingestion and enrichment (once per job); per-user matching, eligibility, feedback and documents | SRC FINAL AD-13; doc 08 s4.1 | Final-Baseline |
| DEC-038 | Keep the stdlib HTTP server and vanilla JavaScript with a versioned /api/v1; no new heavy frontend dependency | SRC FINAL AD-11; doc 03 s11 | Final-Baseline |
| DEC-039 | Every source records access_basis and redistribution (allowed, link_only, personal_only); hosted mode shows only allowed or link_only data | SRC doc 08 NR-10, s6; doc 04 s10 | Final-Baseline |
| DEC-040 | Non-goals: recruiter discovery or outreach, automatic application submission, proxy rotation, paid scraping services, employer-side features, payments, scraping competitors' company lists | SRC brief s5.1; D8; doc 09 B1 | Final-Constraint |
| DEC-041 | scanners/ats.py is kept as the tested fallback until the library adapters pass at least 4 weeks of live verification; only the resolver is adopted immediately; exact versions pinned with hashes; used modules vendored into third_party if upstream stalls | SRC FINAL AD-23; doc 10 F5, F6 | Final-Baseline |
| DEC-042 | All existing tests pass unchanged; a MUST-KEEP file shrinking by more than 20 percent requires stop-and-ask | SRC docs/PROMPT.md s2, s8; doc 06 G1, G2 | Final-Constraint |
| DEC-043 | Release plan: R1 usable discovery for one user, R2 personal workbench, R3 breadth and operations, R4 hosted platform; V1 means R1 to R3 in local mode; R1 contents per doc 07 s7 including the database phase | SRC doc 07 s7-s8 | Final-Baseline |
| DEC-044 | Review points ignored by the owner (sources reachable, reliable sources contain target jobs, free AI stability, Windows differences) drive no design change; the live probe is informational only | SRC doc 08 s2.2, C-1 | Final-Owner |
| DEC-045 | Contact data and nationality never enter AI payloads; CV text goes to an external AI only under the consent setting; recruiter e-mails are never stored; Telegram messages carry no personal data | SRC doc 06 s5; doc 08 s4.3, s4.5; brief s12 | Final-Constraint |
| DEC-046 | Migrations are additive; an automatic backup precedes each; verification covers counts, URL sets, application_id equality and byte-identical queue export; atomic writes for all file exports | SRC brief s13; doc 04 s9; doc 06 s4 | Final-Constraint |
| DEC-047 | Validation honesty: tests with fakes are labelled mocked; verified means a dated run against the real thing; unavailable or skipped gates are reported as skipped, never passed | SRC doc 06 G9; docs/PROMPT.md s5 | Final-Constraint |
| DEC-048 | No core capability depends on a restricted consumer-board source: discovery, matching, tracking and documents work with every consumer provider disabled | SRC doc 03 s1 principle 4; brief s7.4 | Final-Baseline |
| DEC-049 | Onboarding has two entry paths, manual and CV-assisted, that lead to the same profile structure; extracted data is reviewable and correctable before it counts as verified | SRC brief s5.2; doc 05 s2 | Final-Constraint |
| DEC-050 | Application states and events: saved, preparing, ready_to_apply, applied, interview, offer, accepted or declined, rejected, withdrawn, archived; ready_to_apply is the only state eligible for queue export; every change is an event with undo | SRC doc 03 s10 | Final-Baseline |
| DEC-051 | Feedback loop is per user only: events and ignore reasons; suggestions never auto-hide; soft ranking adjustment capped at plus or minus 10, inactive below 10 events, switchable off | SRC owner instruction doc 08 A13, s4.7 | Final-Baseline |

## 3. Pending choices and blockers

This table contains 29 pending decisions. An implementer must not resolve a pending decision. Handling rules:

* **Blocking for the guarded behaviour (B):** the behaviour the PCD guards is outside the work package's scope until the owner answers; work packages whose whole purpose depends on the answer (phases 13–16) stay `blocked`.
* **Non-blocking, default applies (D):** the work package proceeds using the stated interim default, **records that it did so** in its report (GOV-06 §7, field `PCD impact`), and the default is replaced when the owner answers.
* A default is never a decision. It is the safest practical behaviour that lets work continue.

| ID | Pending Choice / Blocker | Why It Matters | Minimal Input Needed |
| -- | ------------------------ | -------------- | -------------------- |
| PCD-001 | Which repository line is the repository (clean line versus GitHub rewrite) [OT-0] | Importers, migration source and assessment depend on it | Owner confirms the clean line |
| PCD-002 | Consumer-board posture and hosted-mode availability [OT-1, C-5] | Coverage versus compliance and ban risk | Owner confirms: restricted local-mode tier only, or other |
| PCD-003 | Workday method: verify-and-extend the library adapter versus build an own paginator [OT-2] | Effort and duplication | Owner acknowledges the method change; live >2,000-job tenant result |
| PCD-004 | Server technology: keep stdlib or move to a framework [OT-3] | Dependency weight versus API ergonomics | Owner decision only if a concrete need appears |
| PCD-005 | Database engine for hosted mode [OT-4] | Hosted scale and migration parity | Owner decision before Phase 13 |
| PCD-006 | True language levels and which are certified [OT-5] | Evaluator and document claims must not overstate | Owner states levels and certificates |
| PCD-007 | Is the hand-off file to the separate auto-applier in scope [OT-6] | Existing contract tests and workflow | Owner confirms keep or drop |
| PCD-008 | Use the hosted dataset snapshot for bootstrap [OT-7] | External dependency and cold start | Owner opt-in |
| PCD-009 | CV parsing libraries (pypdf, python-docx) and the default for AI-assisted extraction [OT-8] | New dependencies need a decision; privacy default | Owner approves the two libraries and the consent default |
| PCD-010 | Provider terms for multi-key quota rotation [OT-9] | Account risk versus free-first capacity | Terms check result |
| PCD-011 | PDF engine on Windows (WeasyPrint needs a GTK runtime) [OT-10] | CV and PDF feature on the primary platform | Result of the Windows verification |
| PCD-012 | Hosted platform versus each user running an own instance [OT-11, OT-12] | Scope of Phases 13-14 | Owner decision |
| PCD-013 | Hosting budget, provider terms for processing other users' CVs, per-user AI budget [OT-13] | Cost and lawful processing | Budget figure; terms check |
| PCD-014 | Source redistribution and licensing review: feeds, ESCO terms [OT-14] | Whether a source or dataset may be shown to other users | Terms review per source |
| PCD-015 | What salary should do (filter, minimum per currency, conversion) [OT-15] | Ranking quality versus false precision | Owner defines |
| PCD-016 | Cutover style: per-entity reversible versus one-time [OT-16, C-2] | Migration risk profile; the owner instruction was duplicated | Owner says apply or ignore |
| PCD-017 | Passive discovery datasets (Common Crawl; Certificate Transparency judged likely infeasible) [OT-17] | Only compliant route to thousands of tenants | Proof-of-concept result against the directory |
| PCD-018 | Public Suffix List dependency tldextract (offline mode) [OT-18] | New dependency for company-domain merging | Owner confirms |
| PCD-019 | Mitigation set for the young ats-scrapers and fast-moving python-jobspy [OT-19] | ATS backbone stability | Owner confirms |
| PCD-020 | Live source probe included although review point 1.2 was ignored [C-1] | Informational only; scope must not depend on it | Owner confirms or removes WP-00-04 |
| PCD-021 | Meaning of 'ignore the Tech-only filter part' [C-3] | Defines the filter and taxonomy scope | Owner clarifies |
| PCD-022 | Operator access policy in hosted mode: who may access user data and how | Privacy and tenant isolation design | Owner policy |
| PCD-023 | Numeric quality targets: language accuracy, seniority and skill recall, eligibility cue recall | Exit criteria of WP-08-06 cannot be numeric without them | Targets set after the first measured baseline |
| PCD-024 | Numeric operating constants: value-score weights, tier cut-offs, guard thresholds, cadence constants, request budgets | Tuning of scheduler and guards | Values tuned after the baseline |
| PCD-025 | Pilot kill-criteria thresholds: careers probe recall, Common Crawl recall, ESCO mapped share, adaptive-cadence saving | Decides whether deferred methods are built | Thresholds set after the first baseline |
| PCD-026 | Applicable data-protection obligations and lawful basis for hosted mode | Phase 15 design | Legal review |
| PCD-027 | Which occupation families the evaluation sets cover (at least 10, not only IT) | Representativeness of WP-08-06 | Owner picks families |
| PCD-028 | Per-provider request limits and terms (documented values are partly unverified) | Budgets and per-host token buckets | Verified limits per provider |
| PCD-029 | Terms and permitted use of the Bundesagentur and EURES endpoints (the adapter uses a public header key) | Whether they may be used and shown to others | Terms review |

### PCD handling (interim defaults)

| ID | Mode | Work packages that reference it | Interim default in force |
| -- | ---- | ------------------------------- | ------------------------ |
| PCD-001 | non-blocking, default applies | WP-03-02 | Clean line (feature/extra-sources lineage) |
| PCD-002 | non-blocking, default applies | WP-04-01, WP-05-01, WP-11-09, WP-15-02 | Restricted, off per provider, local mode only, no proxies |
| PCD-003 | non-blocking, default applies | WP-11-04 | Verify and extend |
| PCD-004 | non-blocking, default applies | WP-02-04 | Keep stdlib server |
| PCD-005 | blocking for the guarded behaviour | WP-03-01, WP-13-03 | SQLite local; PostgreSQL hosted |
| PCD-006 | non-blocking, default applies | WP-01-02, WP-07-01 | Stored self_declared; evaluator says unconfirmed |
| PCD-007 | non-blocking, default applies | WP-03-03, WP-10-02 | Keep explicit export; never submit |
| PCD-008 | non-blocking, default applies | WP-05-05 | Off |
| PCD-009 | blocking for the guarded behaviour | WP-07-03, WP-07-04 | Rules-based and paste-text only; AI extraction off |
| PCD-010 | non-blocking, default applies | WP-01-06 | Keep, configurable, logged |
| PCD-011 | non-blocking, default applies | WP-00-03, WP-09-01, WP-12-04 | Keep WeasyPrint; verify in WP-00-03 |
| PCD-012 | blocking for the guarded behaviour | WP-13-01, WP-14-01 | Build the core to serve both |
| PCD-013 | blocking for the guarded behaviour | WP-08-05, WP-14-01, WP-14-02, WP-14-03, WP-16-01 | Deterministic matching free; LLM on demand with budgets |
| PCD-014 | non-blocking, default applies | WP-08-03, WP-15-02 | redistribution flag per source; ship without ESCO data until checked |
| PCD-015 | non-blocking, default applies | WP-08-04 | Display only |
| PCD-016 | non-blocking, default applies | WP-03-04 | Per-entity, reversible |
| PCD-017 | blocking for the guarded behaviour | WP-11-08 | Not enabled |
| PCD-018 | non-blocking, default applies | WP-00-01, WP-05-06 | Assumed accepted |
| PCD-019 | non-blocking, default applies | WP-05-02 | Assumed accepted: pin, hash, contract tests, vendor if stalled, keep fallback parsers |
| PCD-020 | non-blocking, default applies | WP-00-04 | Included, informational |
| PCD-021 | non-blocking, default applies | WP-05-03, WP-08-01 | No tech-only filtering or taxonomy |
| PCD-022 | blocking for the guarded behaviour | WP-13-01, WP-13-02 | None defined; no operator access assumed |
| PCD-023 | non-blocking, default applies | WP-08-01, WP-08-02, WP-08-06 | Record a baseline first; targets afterwards |
| PCD-024 | non-blocking, default applies | WP-02-05, WP-04-02, WP-04-04, WP-05-05, WP-12-01, WP-12-02, WP-12-04, WP-16-01, WP-16-02 | Defaults in SRC design doc 09 B5, B6, B11 marked target |
| PCD-025 | non-blocking, default applies | WP-08-03, WP-11-06, WP-11-07, WP-11-08, WP-12-02 | Defer the methods until set |
| PCD-026 | blocking for the guarded behaviour | WP-13-01, WP-15-01 | None assumed |
| PCD-027 | blocking for the guarded behaviour | WP-08-06 | None |
| PCD-028 | non-blocking, default applies | WP-04-02, WP-05-05, WP-11-02, WP-11-03, WP-11-04 | 1 request per second per host until verified |
| PCD-029 | blocking for the guarded behaviour | WP-11-02, WP-15-02 | Local personal use only until reviewed |

## 4. Scope boundaries

### 4.1 Allowed for V1 (V1 = releases R1–R3, local mode; DEC-043, ASM-004)

* Discovery from employer ATS boards, government portals, public remote feeds, user imports and (restricted, off by default) consumer boards; company catalog funnel; run guards and honest source states (phases 03–06, 11).
* Canonical job model, deduplication stages 1–2 plus exact-hash links, lifecycle with guards and version history (phases 05–06).
* Versioned candidate profile with proficiency provenance, eligibility data, CV upload and rules-based extraction (phase 07).
* Enrichment for English and German postings, deterministic explainable matching, separate eligibility verdict, salary shown as stated, optional validated LLM layer with explicit failure states (phase 08).
* User-initiated per-job CV and cover-letter drafts with review, approval, versioning and export (phase 09).
* Application tracking with events and undo, queue export for the separate auto-applier, notifications, feedback loop (phase 10).
* Scheduler with lease, monitoring, backups, deletion, Windows packaging (phases 02, 12).
* CLI and local dashboard sharing one service layer (phases 02, 04).

### 4.2 Not allowed for V1 without a decision update

* Hosted multi-user mode and anything in phases 13–16 (needs PCD-005, PCD-012, PCD-013, PCD-022, PCD-026).
* Enabling any consumer-board provider by default, or in hosted mode (PCD-002).
* Any document creation not initiated by an explicit per-job user action (DEC-019).
* Adding a dependency outside DEC-013 and the approved PCD defaults (GOV-03 §10).
* Shipping ESCO data or a hosted snapshot (PCD-014, PCD-008).
* Turning a deferred item below into a work package outside its pilot gate.
* Scoring or converting salary (DEC-025, PCD-015).

### 4.3 Deferred

Stage 3 near-duplicate detection (DEC-009); adaptive cadence unless a replay meets the threshold (DEC-028, PCD-025); careers-page probe adapter and JSON-LD recipe (pilot-gated, WP-11-06, WP-11-07); Common Crawl channel (PCD-017); learning suggestions (WP-10-05, deferrable); German user interface; local LLM provider; additional notification channels; cross-user learning; salary behaviour (PCD-015).

### 4.4 Rejected

Proxy rotation and proxy infrastructure (DEC-017); paid scraping or anti-bot services (DEC-014); stealth, TLS-impersonation or browser-automation adapters and archived scraping tools (DEC-015, DEC-033); Certificate-Transparency enumeration of tenants (judged likely infeasible, SRC design doc 10 F7); search-engine scraping; brute-force or dictionary guessing of employer slugs (DEC-029); scraping competitors' company lists (DEC-040); recruiter e-mail harvesting (DEC-045); automatic application submission (DEC-035); automatic CV generation (DEC-019); Arabic-language postings (DEC-030); a rewrite instead of strangler migration (DEC-002).

## 5. Traceability (decision → component → work package → gate)

Generated from the work-package definitions in GOV-04; a decision with no work package is a governance rule enforced by the gates shown.

| Decision | Components | Work packages | Gates |
| -------- | ---------- | ------------- | ----- |
| DEC-001 | - | governance only | review checklist (GOV-05 s9); docs README authority rule |
| DEC-002 | C-01 C-02 | WP-02-02, WP-02-03, WP-04-03 | G1 G4 G8 G14 |
| DEC-003 | C-01 C-02 C-03 | WP-02-01, WP-02-02, WP-02-03, WP-02-04 | G1 G4 G14 G15 |
| DEC-004 | C-14 | WP-03-01, WP-03-02, WP-03-04, WP-13-03 | G1 G6 G13 |
| DEC-005 | C-05 C-06 C-14 | WP-04-03, WP-05-02, WP-05-03, WP-06-02 | G1 G8 G10 G11 G20 |
| DEC-006 | C-05 | WP-05-01, WP-11-09 | G8 G11 G17 G20 |
| DEC-007 | C-05 C-04 | WP-04-01, WP-05-02 | G8 G11 G17 G20 |
| DEC-008 | C-05 | WP-11-04 | G8 G20 |
| DEC-009 | C-03 C-06 | WP-05-03, WP-06-01 | G1 G8 |
| DEC-010 | C-03 C-06 C-15 | WP-04-04, WP-06-02, WP-11-02, WP-11-07, WP-12-01 | G1 G8 G10 G17 G20 |
| DEC-011 | C-05 | WP-11-01, WP-11-03, WP-11-05 | G8 G20 |
| DEC-012 | C-05 C-04 | WP-05-01 | G8 G11 G17 |
| DEC-013 | C-14 | WP-00-01, WP-04-02 | G1 G7 G8 G17 |
| DEC-014 | - | WP-00-02 | G3 G12 |
| DEC-015 | - | WP-00-02 | G3 G12 |
| DEC-016 | C-07 | WP-05-02, WP-05-05, WP-11-08 | G8 G9 G11 G17 G20 |
| DEC-017 | - | WP-05-01 | G8 G11 G17 |
| DEC-018 | C-05 C-14 | WP-11-03, WP-11-04 | G8 G20 |
| DEC-019 | C-12 C-14 | WP-01-01, WP-09-01, WP-09-02 | G1 G5 G12 G14 G15 |
| DEC-020 | C-12 C-09 | WP-07-03, WP-09-01, WP-09-02, WP-14-02 | G1 G5 G12 G13 G15 G18 |
| DEC-021 | C-09 C-03 | WP-01-02, WP-03-02, WP-07-01, WP-08-04 | G1 G9 G13 G15 |
| DEC-022 | C-03 C-10 | WP-01-03, WP-02-04, WP-08-04, WP-08-05, WP-10-05 | G1 G4 G6 G12 G15 G16 |
| DEC-023 | C-03 C-10 C-09 | WP-07-02, WP-08-02, WP-08-04 | G1 G9 G12 G15 |
| DEC-024 | C-06 C-02 | WP-01-07, WP-05-03 | G1 G8 |
| DEC-025 | C-08 C-10 | WP-08-02, WP-08-04, WP-11-05 | G1 G8 G9 G15 |
| DEC-026 | C-17 | WP-05-04, WP-14-03 | G12 G17 G18 |
| DEC-027 | C-09 | WP-07-03, WP-07-04 | G5 G12 G15 |
| DEC-028 | C-04 | WP-02-05, WP-04-02, WP-12-02, WP-14-01 | G1 G8 G9 G17 G18 |
| DEC-029 | C-07 C-04 | WP-05-05, WP-05-06, WP-11-06, WP-11-08 | G1 G8 G9 G17 G20 |
| DEC-030 | C-08 C-06 | WP-08-01, WP-08-02, WP-08-03, WP-11-02 | G1 G8 G9 G20 |
| DEC-031 | C-08 C-06 C-10 | WP-05-03, WP-08-01, WP-08-02, WP-08-03, WP-08-06 | G1 G8 G9 |
| DEC-032 | C-04 | WP-01-05, WP-04-01, WP-04-05 | G1 G8 G15 G17 |
| DEC-033 | C-04 C-05 C-07 | WP-00-02, WP-01-05, WP-04-02, WP-05-04, WP-05-05, WP-11-06, WP-11-07 | G1 G3 G8 G12 G17 G20 |
| DEC-034 | C-11 C-10 | WP-01-06, WP-08-05, WP-16-01 | G1 G12 G16 |
| DEC-035 | C-13 C-14 | WP-03-03, WP-10-02 | G1 G6 G13 |
| DEC-036 | C-14 C-16 | WP-03-01, WP-13-01, WP-13-02, WP-13-03, WP-14-02, WP-15-01 | G1 G12 G13 G18 G21 |
| DEC-037 | C-06 C-08 C-10 | WP-13-02, WP-14-01, WP-16-01 | G1 G16 G17 G18 G21 |
| DEC-038 | C-01 | WP-02-04 | G1 G4 G15 |
| DEC-039 | C-04 C-16 | WP-04-01, WP-15-02 | G8 G17 G18 G19 |
| DEC-040 | - | governance only | G3 and reviewer checklist |
| DEC-041 | C-05 C-14 | WP-00-01, WP-04-03, WP-05-01, WP-05-02 | G1 G7 G8 G11 G17 G20 |
| DEC-042 | - | WP-00-03 | G1 G7 G9 |
| DEC-043 | - | governance only | phase exit conditions (GOV-06 s10) |
| DEC-044 | - | WP-00-04 | G9 G20 |
| DEC-045 | C-09 C-11 C-13 C-17 | WP-00-02, WP-05-01, WP-05-04, WP-07-02, WP-07-03, WP-08-05, WP-09-01, WP-10-03, WP-12-03, WP-14-03, WP-15-01 | G1 G3 G5 G8 G11 G12 G13 G16 G17 G18 G21 |
| DEC-046 | C-14 | WP-01-04, WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-12-03 | G1 G6 G12 G13 |
| DEC-047 | - | WP-00-03, WP-00-04, WP-04-05, WP-08-06, WP-12-04, WP-16-02 | G1 G7 G9 G15 G17 G20 |
| DEC-048 | C-04 C-05 | WP-04-01, WP-11-09, WP-15-02 | G8 G17 G18 G19 G20 |
| DEC-049 | C-09 C-01 | WP-07-01, WP-07-04 | G1 G13 G15 |
| DEC-050 | C-13 | WP-10-01 | G1 |
| DEC-051 | C-13 | WP-10-04 | G1 |

## 6. Requirement-to-decision chain

For every major requirement the chain is: **source requirement** (SRC section) → **DEC/PCD** (this file) → **architecture contract** (GOV-01 invariant or workflow) → **work package** (GOV-04) → **validation gate** (GOV-05). Rows of the traceability table above give the DEC → WP → gate link; GOV-01 §3 gives INV → DEC; GOV-05 §3 gives gate → WP.

## 7. Contradictions and gaps found in the source

None of these was silently resolved. "Resolved" means a decision already in the source or a binding constraint settles it.

| ID | Contradiction or gap in the source | Handling |
| -- | ---------------------------------- | -------- |
| SC-01 | Decision Log D3 says build a Workday paginator; the pinned library already subdivides by facet | PCD-003; goal kept in DEC-008 |
| SC-02 | Decision Log D2 installs ats-scrapers with the [all] extra; that pulls stealth tooling forbidden by the no-bypass rule | Resolved: DEC-007 and DEC-033; owner acknowledgement via PCD-002 |
| SC-03 | D1 and D6 wording about bypassing result caps and rotating proxies versus the no-bypass rule | Resolved by query partitioning and no proxies: DEC-012, DEC-017, DEC-033 |
| SC-04 | The original brief said local-first and not a mandatory service; the owner later asked for a platform for any user | Resolved: newest instruction wins, staged: DEC-036 |
| SC-05 | The working contract allowed automatic CV creation as an opt-in setting; the brief says never automatic | Resolved: DEC-019 |
| SC-06 | Review point 1.2 was ignored, yet a live source probe was requested | PCD-020; DEC-044 |
| SC-07 | The one-time cutover fix was given twice, once as apply and once as ignore | PCD-016 |
| SC-08 | Research says postpone SmartRecruiters unless authorised; an earlier-built scanner activates it on configuration | Resolved: DEC-032; defect fixed in WP-01-05 |
| SC-09 | Research lists adapters as missing that the library already contains | Resolved: DEC-007, DEC-011 (verify then patch) |
| SC-10 | Language levels differ between profile.yml, the evaluator prompt, the sample CV and the owner's statement | PCD-006; DEC-021 |
| SC-11 | The plan said retire scanners/ats.py after parity while the library backbone is 14 weeks old and single-author | Resolved: DEC-041 |
| SC-12 | Automatic submission is a non-goal, but an auto-applier queue export exists | DEC-035 and PCD-007 |
| SC-13 | Some Decision Log and research claims are unverified (popularity figures, coverage percentage, some rate limits) | PCD-028; treated as information only |

## 8. Assumptions

Assumptions are not decisions. Each lists what changes if it is wrong.

| ID | Assumption | If wrong |
| -- | ---------- | -------- |
| ASM-001 | The authoritative source is the JobHunter design suite (primary document plus docs 01-10, revision 4) because revised_system_v2.md was not supplied | If the real file differs, regenerate; DEC and PCD sets may change |
| ASM-002 | The reference documents 00-07 were not supplied; structure and rigor are derived from the task description only | File layout may differ in detail from the intended reference |
| ASM-003 | The implementation repository is the clean line (feature/extra-sources lineage), PCD-001 | Importers and assessments change if the GitHub rewrite is meant |
| ASM-004 | V1 means R1 to R3 in local mode (DEC-043); the hosted platform is a later scope | Scope tables change if V1 is meant to include hosting |
| ASM-005 | The project has one maintainer; reviewer independence means a separate session or person, not a separate team | Reviewer prompt assumes a fresh context |
| ASM-006 | Local mode targets Windows with Python 3.12 to 3.14; wheels for compiled dependencies were verified for cp312 and cp314 only | Other versions are unverified |
| ASM-007 | Live network access to providers exists only on the owner's machine; CI has no live access | Live verification gates are manual and dated |
| ASM-008 | No hosted deployment target is specified; hosted work packages are written technology-neutral where the source is silent | Phase 13-14 outputs need PCD-005, PCD-012, PCD-013 |

## 9. Changing this log

1. A change starts as a proposal that names the DEC or PCD, the reason and the evidence.
2. Only the owner may move a PCD to a DEC or change a Final-Owner decision; Final-Baseline decisions may be changed by the owner after a review that lists affected work packages (from §5).
3. Decisions are superseded, never deleted: the old row gets status `Superseded by DEC-nnn` and stays.
4. Every change updates the affected work packages (GOV-04), gates (GOV-05) and invariants (GOV-01) in the same change set.
5. An implementer who finds that a work package cannot be completed as specified stops, files the finding as a proposed PCD, and sets the package to `blocked` (GOV-04 §2).
