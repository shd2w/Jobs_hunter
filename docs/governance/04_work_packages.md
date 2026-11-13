# 04 — Work Packages

Status: **binding implementation plan**. 73 work packages in 17 phases. Release mapping follows DEC-043 (R1 usable discovery, R2 personal workbench, R3 breadth and operations, R4 hosted platform). Controlling documents: GOV-02 (decisions), GOV-01 (invariants), GOV-05 (evidence).

## 1. Phases

| Phase | Name | Release | Work packages | Goal |
| ----- | ---- | ------- | ------------- | ---- |
| 00 | Foundations and guardrails | R1 | 4 | Reproducible installs, policy and secret gates, CI, baseline live probe |
| 01 | Stabilise existing behaviour | R1 | 7 | Known defects closed; no automatic documents; AI failures explicit |
| 02 | Shared service layer and scheduler | R1 | 5 | One code path for CLI and UI; single scheduler with lease |
| 03 | Canonical data and migration | R1 | 4 | Database authoritative with verified, reversible migration and byte-identical exports |
| 04 | Source infrastructure | R1 | 5 | Honest source states, budgets, guards and run metrics |
| 05 | Ingestion core | R1 | 6 | Canonical jobs from ATS, aggregators, imports; company catalog funnel |
| 06 | Dedup stage 2 and lifecycle | R1 | 2 | Cross-source links and safe closing of jobs |
| 07 | Candidate profile and onboarding | R2 | 4 | Confirmed-profile model with proficiency provenance and eligibility data |
| 08 | Enrichment, matching and evaluation | R1/R2 | 6 | Explainable deterministic matching, eligibility verdict, AI failure semantics |
| 09 | User-initiated documents | R2 | 2 | Per-job draft, review, approval, export with versioning |
| 10 | Tracking, notifications, feedback | R2 | 5 | Application events, queue export from database, Telegram rules, feedback loop |
| 11 | Extended sources and pilots | R3 | 9 | More sources through the controlled expansion process; pilots with kill criteria |
| 12 | Monitoring and operations | R3 | 4 | Drift detection, backups, deletion, Windows packaging |
| 13 | Accounts and tenancy | R4 | 3 | Hosted multi-user mode with proven isolation |
| 14 | Hosted operations | R4 | 3 | Shared ingestion plane and per-user plane running as a service |
| 15 | Privacy, compliance, redistribution | R4 | 2 | Consent, export, deletion, per-source redistribution gating |
| 16 | Capacity and cost controls | R4 | 2 | Scope-driven ingestion limits, per-user budgets, load evidence |

### Release map

| Release | Phases | Work packages |
| ------- | ------ | ------------- |
| R1 | 00 01 02 03 04 05 06 (+ 08 lite: WP-08-01, WP-08-02) | 35: WP-00-01, WP-00-02, WP-00-03, WP-00-04, WP-01-01, WP-01-02, WP-01-03, WP-01-04, WP-01-05, WP-01-06, WP-01-07, WP-02-01, WP-02-02, WP-02-03, WP-02-04, WP-02-05, WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-04-01, WP-04-02, WP-04-03, WP-04-04, WP-04-05, WP-05-01, WP-05-02, WP-05-03, WP-05-04, WP-05-05, WP-05-06, WP-06-01, WP-06-02, WP-08-01, WP-08-02 |
| R2 | 07 08 (rest) 09 10 | 15: WP-07-01, WP-07-02, WP-07-03, WP-07-04, WP-08-03, WP-08-04, WP-08-05, WP-08-06, WP-09-01, WP-09-02, WP-10-01, WP-10-02, WP-10-03, WP-10-04, WP-10-05 |
| R3 | 11 12 | 13: WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-05, WP-11-06, WP-11-07, WP-11-08, WP-11-09, WP-12-01, WP-12-02, WP-12-03, WP-12-04 |
| R4 | 13 14 15 16 | 10: WP-13-01, WP-13-02, WP-13-03, WP-14-01, WP-14-02, WP-14-03, WP-15-01, WP-15-02, WP-16-01, WP-16-02 |

A "session" in the SRC estimates is a unit of effort, not a work package: R1 holds many small packages and is estimated at about 16 sessions.

## 2. Work-package lifecycle

| Status | Meaning | Allowed next |
| ------ | ------- | ------------ |
| `blocked` | a dependency is unmerged, a blocking PCD applies to the whole package, or the implementer found a contradiction | `ready_for_implementation` |
| `ready_for_implementation` | all dependencies merged; no blocking PCD; scope clear | `in_progress` |
| `in_progress` | an implementer owns it on a `wp/` branch | `ready_for_validation`, `blocked` |
| `ready_for_validation` | code complete; validation not yet run | `ready_for_review`, `in_progress` |
| `ready_for_review` | every required gate executed with evidence attached | `ready_for_merge`, `in_progress` |
| `ready_for_merge` | reviewer accepted with no open finding | `merged` |
| `merged` | merged into the phase branch; evidence filed | — |

Transition rules are in GOV-05 §10. A package is never `ready_for_review` while a required gate is skipped, unavailable, partially executed or only mocked where the package requires a real run (DEC-047).

## 3. Package types

| Package type | Meaning | Work packages |
| ------------ | ------- | ------------- |
| Foundation | Build, tooling, CI, packaging | WP-00-01, WP-00-02, WP-00-03, WP-02-05, WP-12-03, WP-12-04, WP-14-01 |
| Behaviour fix | Corrects an existing defect | WP-01-01, WP-01-02, WP-01-03, WP-01-04, WP-01-05, WP-01-07 |
| Refactor | Moves or consolidates existing behaviour without changing it | WP-02-01, WP-02-02, WP-02-03, WP-02-04 |
| Data | Schema, migration, importers, exporters | WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-10-02, WP-13-03 |
| Source infrastructure | Registry, protocol, guards, metrics | WP-04-01, WP-04-02, WP-04-03 |
| Source adapter | Adds or changes a provider adapter | WP-05-01, WP-05-02, WP-05-04, WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-05, WP-11-07, WP-14-03 |
| Domain logic | Pure rules, enrichment, scoring, lifecycle | WP-04-04, WP-05-03, WP-05-05, WP-05-06, WP-06-01, WP-06-02, WP-07-01, WP-07-02, WP-08-01, WP-08-02, WP-08-03, WP-08-04, WP-10-01, WP-10-04, WP-10-05, WP-12-01, WP-12-02, WP-16-01 |
| AI | Touches providers, prompts or generated content | WP-01-06, WP-08-05, WP-09-01 |
| UI | Screens and browser flows | WP-04-05, WP-07-04, WP-09-02 |
| Security | Privacy, isolation, consent, upload handling | WP-07-03, WP-10-03, WP-13-01, WP-13-02, WP-14-02, WP-15-01, WP-15-02 |
| Pilot | Experiment, verification or measurement with a decision outcome | WP-00-04, WP-08-06, WP-11-06, WP-11-08, WP-11-09, WP-16-02 |

Required evidence per type is defined in GOV-05 §2.

## 4. Work packages by phase

Each phase has two tables: the definition (scope, non-scope, dependencies, outputs, tests and evidence, exit criteria, initial status) and the traceability (type, components, controlling DEC, pending decisions, gates). "T:" names required tests, "E:" required evidence. Packages in phases 13–16 stay `blocked` until the PCDs listed in their traceability row are answered.


### Phase 00 — Foundations and guardrails  (release R1)

*Goal:* Reproducible installs, policy and secret gates, CI, baseline live probe.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-00-01 | **Dependency lock** — Reproducible installs | pyproject and hash-locked groups (core, ingestion, docs); pins per DEC-013; certifi floor; Python 3.12-3.14 | No new packages beyond DEC-013 and PCD-018; no behaviour change | - | pyproject.toml, lock files, install notes | T: clean-venv install Linux and Windows. E: install logs, pip check output | G7 green on both OS; lock reproducible | ready_for_implementation |
| WP-00-02 | **Policy, secret and PII gates** — Make forbidden things fail in CI | blocked-dependency test; secret and PII scan; split real config/profile.yml from a tracked profile.example.yml; ignore data, output, .env, cv | No runtime change | WP-00-01 | tests/test_policy_blocked.py, scan script, example profile | T: test fails when selenium is added to a test lock; scan finds nothing. E: CI output | G3 and G12 green; no personal data tracked | blocked (dependencies) |
| WP-00-03 | **CI with Windows and WeasyPrint** — Stop silent skips; prove the platform | CI on Linux and Windows; WeasyPrint present; missing WeasyPrint fails instead of skipping; verify_windows script | No feature change | WP-00-01 | CI config, scripts/verify_windows.ps1 | T: 286 pass, 0 skipped on both OS. E: CI runs | G1 and G7 green on both OS | blocked (dependencies) |
| WP-00-04 | **Baseline live source probe (informational)** — Record what actually works from the owner's network | run run_check_sources on the owner's machine; record dated OK or FAIL per source and which link fields each aggregator provider populates | Must not change scope or policy | WP-00-01 | docs/SOURCE_VERIFICATION.md | E: dated table with machine and network | Every source marked verified, failed or unreachable | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-00-01 | Foundation | C-14 | DEC-013, DEC-041 | PCD-018 | G7, G1 |
| WP-00-02 | Foundation | C-14 | DEC-014, DEC-015, DEC-033, DEC-045 | - | G3, G12 |
| WP-00-03 | Foundation | C-14 | DEC-042, DEC-047 | PCD-011 | G1, G7, G9 |
| WP-00-04 | Pilot | C-15 | DEC-044, DEC-047 | PCD-020 | G20, G9 |

### Phase 01 — Stabilise existing behaviour  (release R1)

*Goal:* Known defects closed; no automatic documents; AI failures explicit.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-01-01 | **Remove automatic CV path** — Satisfy DEC-019 for existing code | delete auto creation in run_evaluate; --create-cv valid only with --url; deprecate create_cv and auto_cv_threshold with a warning | DocumentService itself (WP-09-01) | WP-00-03 | patch and tests | T: evaluation with create_cv true creates no document. E: test output | No code path creates a document without an explicit single-job request | blocked (dependencies) |
| WP-01-02 | **Evaluator reads the profile** — Remove hard-coded candidate facts | build evaluator prompt from profile data; unconfirmed wording for levels | New profile model (WP-07-01) | WP-00-03 | patch and tests | T: no language level literal in the prompt; prompt snapshot test. E: snapshot | No hard-coded candidate fact in evaluator | blocked (dependencies) |
| WP-01-03 | **Deterministic total score** — Stop trusting the model total | single recompute function in domain scoring; ignore model total | New signals or eligibility | WP-00-03 | domain scoring function, tests | T: model total ignored; legacy exports unchanged for default weights. E: golden diff | Total derives from weights in one place | blocked (dependencies) |
| WP-01-04 | **Atomic file writes** — Prevent truncated state files | atomic write for pipeline.md and scan-history; crash-injection test | Database (WP-03-01) | WP-00-03 | patch and tests | T: crash mid-write leaves previous file intact. E: test output | All file exports use atomic replace | blocked (dependencies) |
| WP-01-05 | **Source policy gate and pages cleanup** — Close the SmartRecruiters gate defect and the no-op pages option | disabled_by_policy plus authorized flag for SmartRecruiters; remove or implement the pages option | Registry tables (WP-04-01) | WP-00-03 | patch and tests | T: board without authorized is skipped with a visible reason; pages option absent or functional | No source activates without its policy flag | blocked (dependencies) |
| WP-01-06 | **AI error taxonomy and failure semantics** — Make AI failures explicit | error classes, jitter, per-key cooldown, failed means no score | Provider additions; caching | WP-00-03 | router refactor and tests | T: mocked 429, 5xx, 4xx, timeout, malformed, exhaustion each take the specified path. E: test output | G16 green | blocked (dependencies) |
| WP-01-07 | **Pin the title-filter defect** — Record DEF-13 as a red test before it is fixed | failing or xfail test for substring matching (Lead Generation, Staffing, Architecture) | Changing filters now | WP-00-03 | tests | E: test recorded as expected-fail with reason | Defect pinned and referenced by WP-05-03 | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-01-01 | Behaviour fix | C-12, C-01 | DEC-019 | - | G1, G5, G14 |
| WP-01-02 | Behaviour fix | C-10 | DEC-021 | PCD-006 | G1, G9 |
| WP-01-03 | Behaviour fix | C-03, C-10 | DEC-022 | - | G1, G6 |
| WP-01-04 | Behaviour fix | C-14 | DEC-046 | - | G1 |
| WP-01-05 | Behaviour fix | C-04, C-05 | DEC-032, DEC-033 | - | G1, G17 |
| WP-01-06 | AI | C-11 | DEC-034 | PCD-010 | G1, G16 |
| WP-01-07 | Behaviour fix | C-06 | DEC-024 | - | G1 |

### Phase 02 — Shared service layer and scheduler  (release R1)

*Goal:* One code path for CLI and UI; single scheduler with lease.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-02-01 | **Package skeleton and layer lint** — Create the layered package | jobhunter package with domain, app, adapters, interfaces; layer-lint test | Moving existing modules | WP-01-03 | package skeleton, lint test | T: lint fails on a deliberate violation | G4 green | blocked (dependencies) |
| WP-02-02 | **Result type and services over files** — One implementation of each use case | Result[T]; services for jobs, evaluation, applications, health over existing files | Database | WP-02-01 | services and tests | T: service unit tests; existing tests unchanged | CLI and UI can call each use case through a service | blocked (dependencies) |
| WP-02-03 | **CLI shims** — Keep CLI stable on the new layer | run_scan, run_evaluate, run_all, run_export_queue, run_health call services; flags and exit codes unchanged | New CLI commands beyond jobs, profile, health | WP-02-02 | shims and golden tests | T: golden flags, exit codes, json shapes | G14 green | blocked (dependencies) |
| WP-02-04 | **UI on services and ranking consolidation** — One scoring path for CLI and UI | UI handlers call services; ranking weights move to domain scoring | New screens | WP-02-02 | handlers and parity test | T: parity fixture. E: identical ids and scores | G15 green; no weight constants outside domain scoring | blocked (dependencies) |
| WP-02-05 | **Scheduler worker with lease** — Single scheduler in the first release | jobhunter worker; per-source cadences; single-writer lock-file lease; jitter and per-host budget | Adaptive cadence | WP-02-02 | worker and tests | T: second scheduler cannot acquire the lease; expired lease taken over | One scheduler runs; UI and CLI use the same | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-02-01 | Refactor | C-02, C-03 | DEC-003 | - | G4, G1 |
| WP-02-02 | Refactor | C-02 | DEC-003, DEC-002 | - | G1, G4 |
| WP-02-03 | Refactor | C-01 | DEC-002, DEC-003 | - | G14, G1 |
| WP-02-04 | Refactor | C-01, C-03 | DEC-003, DEC-022, DEC-038 | PCD-004 | G15, G4, G1 |
| WP-02-05 | Foundation | C-04 | DEC-028 | PCD-024 | G1, G17 |

### Phase 03 — Canonical data and migration  (release R1)

*Goal:* Database authoritative with verified, reversible migration and byte-identical exports.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-03-01 | **Schema v1 and migration runner** — Create the authoritative store | tables for R1 per SRC design doc 04 s4, s10, s11 with user_id from the first migration; migration runner with automatic backup | Hosted engine | WP-02-02 | migrations, runner | T: migration idempotence on fixtures. E: backup file created | Schema applies on empty and legacy fixtures | blocked (dependencies) |
| WP-03-02 | **Importers** — Fill the database from existing files | profile.yml, portals.yml, pipeline.md, scan-history, jd_cache, evaluations.json, app_state, applications.md, document paths | Deleting any file | WP-03-01 | importers and tests | T: importer idempotence; levels imported as self_declared. E: counts report | Re-running the importer is a no-op | blocked (dependencies) |
| WP-03-03 | **Compat exporters and queue golden** — Keep every external file contract | regenerate pipeline.md, evaluations.json, Excel, applications.md; queue exporter reads a database view | Changing the queue contract | WP-03-02 | exporters and golden tests | T: byte-identical queue file; evaluations.json exact legacy shape | G6 green | blocked (dependencies) |
| WP-03-04 | **Verifier, authority flags, rollback** — Make cutover reversible | verify counts, URL sets, application_id equality; per-entity authority flags; rollback command | One-time cutover unless PCD-016 says so | WP-03-03 | verifier, flags, docs | T: rollback restores file authority. E: verification report | G13 green on a copy of the owner's real workspace | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-03-01 | Data | C-14 | DEC-004, DEC-036, DEC-046 | PCD-005 | G13, G1 |
| WP-03-02 | Data | C-14, C-09 | DEC-004, DEC-021, DEC-046 | PCD-001 | G13 |
| WP-03-03 | Data | C-14, C-13 | DEC-035, DEC-046 | PCD-007 | G6, G13, G1 |
| WP-03-04 | Data | C-14 | DEC-004, DEC-046 | PCD-016 | G13, G6 |

### Phase 04 — Source infrastructure  (release R1)

*Goal:* Honest source states, budgets, guards and run metrics.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-04-01 | **Source registry and policy gate** — Catalogue with states and permissions | source tables, services, states, access_basis, redistribution, authorized, policy flags | Adapters | WP-03-01 | registry service and tests | T: state transitions; first success does not activate | Consumer providers cannot be enabled without acknowledgement | blocked (dependencies) |
| WP-04-02 | **Adapter protocol and run context** — One contract for all sources | SourceAdapter protocol; RunContext with throttle, stamina retries, breaker, conditional requests, payload hash, budgets | Specific providers | WP-04-01 | protocol and context | T: breaker opens on 401/403/429 and stops requests; budget never exceeded in a 24 h simulation | G17 green | blocked (dependencies) |
| WP-04-03 | **Wrap existing scanners as adapters** — Preserve working sources | JobSpy, legacy Workday, scanners/ats.py fallback, feeds as adapters with parity fixtures | Library adapters (WP-05-02) | WP-04-02 | adapters and fixtures | T: existing 24 extra-source tests ported as parity fixtures | Existing scans produce identical jobs through the contract | blocked (dependencies) |
| WP-04-04 | **Run guards** — Never close jobs on bad data | coverage validation, cap detection, volume guard v2 with re-baselining, global cycle breaker, small-source confirmation | Drift detectors (WP-12-01) | WP-04-02 | domain guard functions and simulation tests | T: simulation regression incl. stable zero outage. E: simulation output | G10 green | blocked (dependencies) |
| WP-04-05 | **Run metrics and honest status** — Show what really happened | per-run metrics, status vocabulary, Sources screen and CLI health, reason for every zero result | Drift alerts | WP-04-02 | metrics, screen, CLI | T: a failed source never shows as done; zero results carry a reason | Status wording per SRC design doc 05 s6 | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-04-01 | Source infrastructure | C-04 | DEC-032, DEC-039, DEC-048, DEC-007 | PCD-002 | G8, G17 |
| WP-04-02 | Source infrastructure | C-04, C-05 | DEC-033, DEC-013, DEC-028 | PCD-028, PCD-024 | G17, G8 |
| WP-04-03 | Source infrastructure | C-05 | DEC-002, DEC-041, DEC-005 | - | G8, G1 |
| WP-04-04 | Domain logic | C-03, C-15 | DEC-010 | PCD-024 | G10, G8 |
| WP-04-05 | UI | C-15, C-01 | DEC-032, DEC-047 | - | G15, G17 |

### Phase 05 — Ingestion core  (release R1)

*Goal:* Canonical jobs from ATS, aggregators, imports; company catalog funnel.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-05-01 | **JobSpy adapter upgrade** — Use JobSpy correctly | provider envelope (job_url_direct, company_url, company_url_direct kept; emails dropped); attrs errors; 34-column mapping to Job; query planner; pinned version | Proxy support | WP-04-03 | adapter and contract tests | T: mocked attrs error yields failed run; 3x2 matrix gives 6 queries; planner makes no network call; column contract test | G11 and G8 green | blocked (dependencies) |
| WP-05-02 | **ATS adapters via library and directory** — Broad employer-board coverage | allow-listed ats-scrapers adapters (Greenhouse, Lever, Ashby, Recruitee, Rippling first); fallback parsers registered; vendored directory snapshot with checksum | Workday, Workable, Personio (Phase 11) | WP-04-03 | adapters, fixtures, snapshot | T: fixtures normalise to valid Job; blocked adapters cannot be enabled. E: snapshot checksum | G8 green; live evidence recorded per board kind | blocked (dependencies) |
| WP-05-03 | **Ingestion pipeline** — Persist canonical jobs safely | normalise, global quality rules with visibility and reason, per-user query-time filters, Stage 1 dedup, raw and canonical persistence | Stage 2 dedup, lifecycle | WP-05-01, WP-05-02, WP-01-07 | pipeline and tests | T: nothing deleted at ingest; substring-filter defect fixed; every hidden job has a reason | Hidden-jobs breakdown available | blocked (dependencies) |
| WP-05-04 | **Imports** — Jobs from anywhere without scraping | paste text and URLs, .eml/.mbox, Telegram forward, CSV; sanitising; undo; private to importer | Following links in emails | WP-05-03 | import service and tests | T: sanitisation, no remote loads, attachments ignored, links not followed, size caps | Imported job enters the canonical model with provenance | blocked (dependencies) |
| WP-05-05 | **Company catalog funnel** — Reach many employers without hand-seeding | candidate pool, URL normaliser, resolver wrapper, policy gate, verification, value tiers, onboarding throttle, weekly funnel table | Careers probe, passive datasets | WP-05-02, WP-04-01 | services and fixture tables | T: recognition fixture table (supported, blocked, unsupported, unknown, tracking host); throttle respected | Candidate becomes validating or dormant with a recorded reason | blocked (dependencies) |
| WP-05-06 | **Company entity resolution** — One company, one record | registrable-domain merge with tldextract offline, aliases with undo, advisory company_type | Using company_type to exclude jobs | WP-05-05 | resolution service and tests | T: merge and undo fixtures; agency flag on a labelled sample | Merges are logged and reversible | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-05-01 | Source adapter | C-05 | DEC-006, DEC-012, DEC-017, DEC-041, DEC-045 | PCD-002 | G8, G11, G17 |
| WP-05-02 | Source adapter | C-05, C-07 | DEC-007, DEC-016, DEC-041, DEC-005 | PCD-019 | G8, G11, G20 |
| WP-05-03 | Domain logic | C-06 | DEC-024, DEC-009, DEC-005, DEC-031 | PCD-021 | G1, G8 |
| WP-05-04 | Source adapter | C-17 | DEC-026, DEC-033, DEC-045 | - | G17, G12 |
| WP-05-05 | Domain logic | C-07 | DEC-029, DEC-033, DEC-016 | PCD-024, PCD-028, PCD-008 | G8, G17 |
| WP-05-06 | Domain logic | C-07 | DEC-029 | PCD-018 | G1 |

### Phase 06 — Dedup stage 2 and lifecycle  (release R1)

*Goal:* Cross-source links and safe closing of jobs.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-06-01 | **Dedup stage 2 and exact-hash links** — Link the same job across sources | company and requisition id, fuzzy title and location, exact description hash, automatic grouping with undo | Stage 3 near-duplicate detection | WP-05-03 | dedup service and golden corpus | T: golden duplicate sets with hard negatives | No automatic merge or deletion occurs | blocked (dependencies) |
| WP-06-02 | **Lifecycle service and versions** — Track new, updated, closed | lifecycle using guards, job_version with content hash, 304 handling, explicit expiry signals | Drift detectors | WP-06-01, WP-04-04 | lifecycle service and fixtures | T: disappear and reappear; URL change keeps the job; zero-result outage closes nothing | G10 green | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-06-01 | Domain logic | C-03, C-06 | DEC-009 | - | G1 |
| WP-06-02 | Domain logic | C-03, C-06 | DEC-010, DEC-005 | - | G10, G1 |

### Phase 07 — Candidate profile and onboarding  (release R2)

*Goal:* Confirmed-profile model with proficiency provenance and eligibility data.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-07-01 | **Profile model and versions** — Truthful candidate data | profile versions, skills and languages with level and provenance, profile.yml import mapping with review | Eligibility tables (WP-07-02) | WP-03-02 | profile service and tests | T: yml import produces no confirmed row; every edit is a version; revert works | Nothing is ever auto-confirmed | blocked (dependencies) |
| WP-07-02 | **Eligibility profile** — Capture where the user can work | work authorisation per country, nationalities, relocation plan, remote constraints; kept off AI payloads | Verdict computation (WP-08-04) | WP-07-01 | tables, service, UI fields | T: payload capture shows no nationality or contact data | Prompt for missing data instead of guessing | blocked (dependencies) |
| WP-07-03 | **CV upload and rule-based extraction** — Safe intake with defaults | extension, magic-byte and size validation; read-only storage by hash; rules-based extraction; auto-accept with undo | AI extraction; new parsing libraries until PCD-009 | WP-07-01 | upload service and tests | T: spoofed extension and oversized files rejected; original hash unchanged; auto-accepted stays unconfirmed | Original CV never modified | blocked (dependencies) |
| WP-07-04 | **Onboarding UI and consent setting** — Two entry paths, minimal questions | manual and CV-assisted paths, three short questions, one AI-consent setting | AI extraction itself | WP-07-03, WP-07-02 | screens | T: browser flow for both paths | User can search after minimum profile | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-07-01 | Domain logic | C-09 | DEC-021, DEC-049 | PCD-006 | G1, G13 |
| WP-07-02 | Domain logic | C-09 | DEC-023, DEC-045 | - | G12, G1 |
| WP-07-03 | Security | C-09 | DEC-020, DEC-027, DEC-045 | PCD-009 | G12, G5 |
| WP-07-04 | UI | C-09, C-01 | DEC-049, DEC-027 | PCD-009 | G15 |

### Phase 08 — Enrichment, matching and evaluation  (release R1/R2)

*Goal:* Explainable deterministic matching, eligibility verdict, AI failure semantics.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-08-01 | **Language detection and lexicons** — EN/DE collection filter | stdlib detector, unknown-language policy, EN and DE lexicon files, sectioning, title normalisation | Other languages | WP-05-03 | enrichment module and tests | T: staged labelled set incl. Dutch, Danish, Swedish, Polish, Italian; every lexicon entry unit-tested. E: baseline report | Policy: unknown over 40 tokens hidden as other | blocked (dependencies) |
| WP-08-02 | **Requirement, seniority, salary, eligibility extraction** — Structured facts with evidence | years regexes, evidence-weighted seniority with override rule, title-only hint, salary parse as stated, eligibility cues with quotes | Scoring | WP-08-01 | extractors and tests | T: seniority regression set (35 prototype cases ported); every item has a quote found in the text | Evidence quote required for every extracted item | blocked (dependencies) |
| WP-08-03 | **Skill normalisation** — Open-vocabulary skills | matching ladder with optional ESCO data file; unmapped skills kept with evidence; mapped share reported | Shipping ESCO data before PCD-014 | WP-08-02 | normaliser and tests | T: ladder fixtures; unmapped retained | Mapped share reported on the labelled set | blocked (dependencies) |
| WP-08-04 | **Scorer, ScoreCard, eligibility verdict** — Explainable per-user result | signals to groups to match score and confidence; veto and cap; eligibility verdict; legacy 1-5 view | LLM rationale | WP-08-03, WP-07-02, WP-06-02 | domain scoring and tests | T: per-signal tests; proficiency-state table; eligibility rule table; parity test | Unknown never scored as failure | blocked (dependencies) |
| WP-08-05 | **EvaluationService** — Optional validated LLM layer | requirement extraction fill-in and rationale with quote validation, caching, ai_call records, skill-gap | LLM setting scores | WP-08-04, WP-01-06 | service and tests | T: invalid output rejected; quote must exist; failed AI yields failed row and still ranks | G16 green | blocked (dependencies) |
| WP-08-06 | **Labelled evaluation sets and report** — Measure real accuracy | staged labelled sets (about 60 postings, 40 language, 50 company names, 50 domains) marked directional | Setting numeric targets before a baseline | WP-08-05 | datasets and report | E: baseline numbers per metric with sample sizes | Baseline recorded; targets proposed for PCD-023 | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-08-01 | Domain logic | C-08 | DEC-030, DEC-031 | PCD-023, PCD-021 | G1, G9 |
| WP-08-02 | Domain logic | C-08 | DEC-025, DEC-023, DEC-031, DEC-030 | PCD-023 | G1, G9 |
| WP-08-03 | Domain logic | C-08 | DEC-030, DEC-031 | PCD-014, PCD-025 | G1, G9 |
| WP-08-04 | Domain logic | C-03, C-10 | DEC-022, DEC-023, DEC-021, DEC-025 | PCD-015 | G1, G15 |
| WP-08-05 | AI | C-10, C-11 | DEC-034, DEC-022, DEC-045 | PCD-013 | G16, G1, G12 |
| WP-08-06 | Pilot | C-08, C-10 | DEC-047, DEC-031 | PCD-023, PCD-027 | G9 |

### Phase 09 — User-initiated documents  (release R2)

*Goal:* Per-job draft, review, approval, export with versioning.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-09-01 | **DocumentService** — Only user-initiated documents | wrap CVTailor, cover letters and PDF; draft, approve, discard; versions; facts check; database constraint | Review UI | WP-08-04, WP-03-01 | service and tests | T: call-graph test; scans, evaluations and imports leave documents empty; protected-field edits rejected; original hash unchanged | G5 green | blocked (dependencies) |
| WP-09-02 | **Review and export UI** — User decides | diff view, accept or revert per line, facts check, approve, export | Automatic export | WP-09-01 | screens | T: browser flow of the document journey | Export happens only on the explicit choice | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-09-01 | AI | C-12 | DEC-019, DEC-020, DEC-045 | PCD-011 | G5, G1, G12 |
| WP-09-02 | UI | C-12, C-01 | DEC-020, DEC-019 | - | G5, G15 |

### Phase 10 — Tracking, notifications, feedback  (release R2)

*Goal:* Application events, queue export from database, Telegram rules, feedback loop.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-10-01 | **Application status machine** — Track applications with history | states, events, undo, reminders | Queue export | WP-08-04 | service and tests | T: invalid transitions rejected; undo restores previous state | Event log reconstructs the state | blocked (dependencies) |
| WP-10-02 | **Queue export from the database** — Keep the hand-off contract | export view of approved documents and ready_to_apply jobs; skip reasons shown | Submission | WP-10-01, WP-09-01, WP-03-03 | exporter | T: byte-identical golden for identical inputs | G6 green | blocked (dependencies) |
| WP-10-03 | **Notification service** — No duplicates, no personal data | rules, dedupe keys, quiet hours, Telegram sender, in-app list | Other channels | WP-10-01 | service and tests | T: dedupe key; payload scan for contact or CV text | No personal data in any message | blocked (dependencies) |
| WP-10-04 | **Feedback loop** — Learn from the user's own choices | events, ignore reasons, suggestions, capped soft adjustment, calibration view | Cross-user learning | WP-10-01 | service and tests | T: cap, off-switch, minimum events, no auto-hide | Adjustment always visible and reversible | blocked (dependencies) |
| WP-10-05 | **Learning suggestions** — Optional skill development hints | rule-based suggestions for recurring gaps | Certification claims | WP-08-05 | service | T: rule fixtures | Deferrable without effect on other packages | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-10-01 | Domain logic | C-13 | DEC-050 | - | G1 |
| WP-10-02 | Data | C-13, C-14 | DEC-035 | PCD-007 | G6 |
| WP-10-03 | Security | C-13 | DEC-045 | - | G12, G1 |
| WP-10-04 | Domain logic | C-13 | DEC-051 | - | G1 |
| WP-10-05 | Domain logic | C-10 | DEC-022 | - | G1 |

### Phase 11 — Extended sources and pilots  (release R3)

*Goal:* More sources through the controlled expansion process; pilots with kill criteria.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-11-01 | **Recruitee fallback ladder** — Meet the 2027-02-10 cutover | JSON then XML then data-props ladder with fixtures | Other providers | WP-05-02 | patch module and fixtures | T: ladder fixtures for each step | Ladder demonstrated before 2027-02-10 | blocked (dependencies) |
| WP-11-02 | **Bundesagentur and EURES adapters** — German and EU coverage | adapters with query partitioning under the 10,000 and page caps; employer name only; placeholder employers hidden | Using them as link channels | WP-05-02 | adapters and fixtures | T: partition fixture; count cross-check; coverage partial unless cover verified | Coverage declared only after a verified cover | blocked (dependencies) |
| WP-11-03 | **Workable, Personio, Teamtailor** — Verify then patch | live verification, shortcode grouping, rate cap, fallbacks, detail incremental via item state | Providers not in scope | WP-05-02 | patches and fixtures | T: fixtures; 429 behaviour; detail-skip test | Each provider has a dated live record | blocked (dependencies) |
| WP-11-04 | **Workday adapter** — Large tenants with state | wrap library adapter with item state, global limiter, tenant and locale validation | Own paginator unless PCD-003 says so | WP-05-02, WP-04-02 | adapter | T: item-state tests. E: live test on a tenant above 2,000 jobs | Incremental run issues detail calls only for new or changed items | blocked (dependencies) |
| WP-11-05 | **Greenhouse pay enrichment** — Salary where the provider has it | bounded per-job pay call | Unbounded detail fetching | WP-05-02 | patch | T: fixture with and without pay | Salary stored as stated | blocked (dependencies) |
| WP-11-06 | **Careers-page probe pilot** — Reach custom-domain employers | 100-domain pilot: robots, five requests per domain per 30 days, ATS embed and JSON-LD detection; adapter only if the kill criterion passes | Running without the owner enabling it | WP-05-05 | pilot report; adapter if passed | T: robots, budget tests. E: recall on 100 domains | Pilot report with decision against PCD-025 | blocked (dependencies) |
| WP-11-07 | **JSON-LD recipe** — Generic career pages | sitemap and JSON-LD extraction with validation, quarantine, explicit closure signals | Job boards | WP-11-06 | adapter | T: validation and quarantine fixtures | Built only if WP-11-06 passes | blocked (dependencies) |
| WP-11-08 | **Common Crawl proof of concept** — Test a passive discovery channel | measure recall and precision against the directory | Enabling the channel | WP-05-05 | report | E: recall and precision numbers | Channel kept or dropped by PCD-017 | blocked (dependencies) |
| WP-11-09 | **Regional JobSpy providers verification** — Local-mode coverage evidence | verify providers one at a time; record results | Hosted availability | WP-05-01 | verification record | E: dated results per provider | Each provider marked usable or not | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-11-01 | Source adapter | C-05 | DEC-011 | - | G8, G20 |
| WP-11-02 | Source adapter | C-05 | DEC-010, DEC-030 | PCD-029, PCD-028 | G8, G20 |
| WP-11-03 | Source adapter | C-05 | DEC-011, DEC-018 | PCD-028 | G8, G20 |
| WP-11-04 | Source adapter | C-05 | DEC-008, DEC-018 | PCD-003, PCD-028 | G8, G20 |
| WP-11-05 | Source adapter | C-05 | DEC-011, DEC-025 | - | G8 |
| WP-11-06 | Pilot | C-07 | DEC-033, DEC-029 | PCD-025 | G17, G20 |
| WP-11-07 | Source adapter | C-05 | DEC-033, DEC-010 | PCD-025 | G8, G17 |
| WP-11-08 | Pilot | C-07 | DEC-029, DEC-016 | PCD-017, PCD-025 | G9 |
| WP-11-09 | Pilot | C-05 | DEC-006, DEC-048 | PCD-002 | G20 |

### Phase 12 — Monitoring and operations  (release R3)

*Goal:* Drift detection, backups, deletion, Windows packaging.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-12-01 | **Drift detectors** — Detect silent breakage | per-board robust z-score only at median 20 or more jobs with floored denominator; cohort detector per provider and tier | Small-board per-board detector | WP-04-05 | detectors and simulations | T: injected-drop tests; false-alarm rate under 1 percent on small-board simulation | G10 green | blocked (dependencies) |
| WP-12-02 | **Adaptive cadence** — Spend requests where jobs change | EWMA change rate and interval formula within provider minimums | Shipping if replay saving is under threshold | WP-12-01 | scheduler extension | E: replay report | Enabled only if saving meets PCD-025 | blocked (dependencies) |
| WP-12-03 | **Backups, restore, deletion, log rotation** — Recoverability and control | backup and verified restore, delete-my-data with confirmation, rotating JSONL logs | Cloud backup | WP-03-04 | commands and tests | T: restore verified by integrity check; deletion lists what it removed | Restore tested on a copy | blocked (dependencies) |
| WP-12-04 | **Windows packaging and benchmarks** — One-page install | install steps tested on a clean machine, verify script, benchmark scripts | Installer builds | WP-00-03, WP-12-03 | docs and scripts | E: clean-machine run log; benchmark results against targets | Install in about 10 documented steps | blocked (dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-12-01 | Domain logic | C-15 | DEC-010 | PCD-024 | G10 |
| WP-12-02 | Domain logic | C-04 | DEC-028 | PCD-025, PCD-024 | G9, G17 |
| WP-12-03 | Foundation | C-14, C-15 | DEC-046, DEC-045 | - | G13, G12 |
| WP-12-04 | Foundation | C-15 | DEC-047 | PCD-011, PCD-024 | G7, G20 |

### Phase 13 — Accounts and tenancy  (release R4)

*Goal:* Hosted multi-user mode with proven isolation.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-13-01 | **Authentication and sessions** — Hosted accounts | email-based login and sessions, CSRF, rate limits | Operator access (PCD-022) | WP-10-01, WP-03-01 | auth module | T: session and CSRF tests | Hosted mode behind a flag | blocked (decisions and dependencies) |
| WP-13-02 | **Tenant-scoped repositories** — Provable isolation | every per-user repository method takes a user context; enumerated isolation tests | Admin data access | WP-13-01 | repositories and tests | T: test enumerates every per-user method | G18 green | blocked (decisions and dependencies) |
| WP-13-03 | **PostgreSQL adapter** — Hosted engine | adapter and migration parity | Local mode change | WP-13-02 | adapter and parity tests | T: migration suite on both engines | Both engines pass the suite | blocked (decisions and dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-13-01 | Security | C-16 | DEC-036 | PCD-012, PCD-022, PCD-026 | G12, G21 |
| WP-13-02 | Security | C-16, C-14 | DEC-036, DEC-037 | PCD-022 | G18, G21 |
| WP-13-03 | Data | C-14, C-16 | DEC-004, DEC-036 | PCD-005 | G13 |

### Phase 14 — Hosted operations  (release R4)

*Goal:* Shared ingestion plane and per-user plane running as a service.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-14-01 | **Workers and deployment recipe** — Run the shared plane | scheduled ingestion workers, lease, deployment recipe | Autoscaling | WP-13-03 | recipe and tests | T: one active scheduler lease; staging run | Staging ingests demand-driven scopes on schedule | blocked (decisions and dependencies) |
| WP-14-02 | **Object storage and encrypted backups** — Per-user file safety | per-user storage namespaces, encrypted backups | Vendor selection unless PCD-013 decides | WP-13-02 | storage layer | T: namespace isolation; restore from encrypted backup | Restore verified | blocked (decisions and dependencies) |
| WP-14-03 | **Inbound e-mail per user** — Alert forwarding | per-user inbound address into the import pipeline | Automatic link following | WP-05-04, WP-13-02 | service | T: mail lands only in the owner's imports | Import path reused unchanged | blocked (decisions and dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-14-01 | Foundation | C-16, C-04 | DEC-028, DEC-037 | PCD-012, PCD-013 | G17, G18 |
| WP-14-02 | Security | C-16 | DEC-036, DEC-020 | PCD-013 | G18, G13 |
| WP-14-03 | Source adapter | C-16, C-17 | DEC-026, DEC-045 | PCD-013 | G18, G17 |

### Phase 15 — Privacy, compliance, redistribution  (release R4)

*Goal:* Consent, export, deletion, per-source redistribution gating.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-15-01 | **Consent, export, deletion** — User control over data | consent records, data export bundle, account deletion | Legal text itself (PCD-026) | WP-13-02 | flows and tests | T: export contains all user data; deletion verified | Deletion removes all rows and files | blocked (decisions and dependencies) |
| WP-15-02 | **Redistribution gating and terms register** — Show only what may be shown | per-source terms review date; hosted view filter | Deciding terms for the owner | WP-13-02 | gating and register | T: personal_only and consumer data never visible | G19 green | blocked (decisions and dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-15-01 | Security | C-16 | DEC-045, DEC-036 | PCD-026 | G18, G12, G21 |
| WP-15-02 | Security | C-16, C-04 | DEC-039, DEC-048 | PCD-014, PCD-029, PCD-002 | G19, G18 |

### Phase 16 — Capacity and cost controls  (release R4)

*Goal:* Scope-driven ingestion limits, per-user budgets, load evidence.

| WP | Name — purpose | Scope | Non-scope | Depends on | Outputs | Tests / evidence | Exit criteria | Initial status |
| -- | -------------- | ----- | --------- | ---------- | ------- | ---------------- | ------------- | -------------- |
| WP-16-01 | **Scope-driven ingestion limits and AI budgets** — Bound cost | union of active user scopes drives ingestion; per-user AI budgets; deterministic matching when over budget | Billing | WP-14-01 | limits and tests | T: inactive scopes paused; over-budget user still gets matching | Ingestion volume tracks active scopes | blocked (decisions and dependencies) |
| WP-16-02 | **Load and capacity tests** — Evidence at target concurrency | load scripts and report | Autoscaling design | WP-16-01 | report | E: measured latency and throughput | Targets set after the first baseline | blocked (decisions and dependencies) |

| WP | Type | Components | DEC | Pending decisions | Gates |
| -- | ---- | ---------- | --- | ----------------- | ----- |
| WP-16-01 | Domain logic | C-16, C-04 | DEC-037, DEC-034 | PCD-013, PCD-024 | G1, G16 |
| WP-16-02 | Pilot | C-16 | DEC-047 | PCD-024 | G9 |

## 5. Components and the packages that implement them

| ID | Component | Responsibility | Implemented by |
| -- | --------- | -------------- | -------------- |
| C-01 | Interfaces (CLI and local web server) | Parse input, call exactly one service method, render Result[T]; no business logic | WP-01-01, WP-02-03, WP-02-04, WP-04-05, WP-07-04, WP-09-02 |
| C-02 | Application services | Use cases for profile, CV ingest, sources, discovery, jobs, match, evaluation, skill-gap, documents, applications, notifications, health | WP-02-01, WP-02-02 |
| C-03 | Domain (pure rules) | Scoring, eligibility, dedup, lifecycle and guards, profile-truth rules, salary and seniority rules; no I/O | WP-01-03, WP-02-01, WP-02-04, WP-04-04, WP-06-01, WP-06-02, WP-08-04 |
| C-04 | Source registry and scheduler | Source catalogue, states, policy gate, budgets, circuit breaker, cadences, single-writer lease | WP-01-05, WP-02-05, WP-04-01, WP-04-02, WP-12-02, WP-14-01, WP-15-02, WP-16-01 |
| C-05 | Source adapters | One class per provider behind the SourceAdapter contract; stateless; fetch and normalise only | WP-01-05, WP-04-02, WP-04-03, WP-05-01, WP-05-02, WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-05, WP-11-07, WP-11-09 |
| C-06 | Ingestion pipeline | Normalise, quality rules, visibility, Stage 1-2 dedup, persist raw and canonical jobs, lifecycle | WP-01-07, WP-05-03, WP-06-01, WP-06-02 |
| C-07 | Company catalog and recognition | Candidate pool, URL normaliser, resolver wrapper, policy gate, verification, tiers, entity resolution | WP-05-02, WP-05-05, WP-05-06, WP-11-06, WP-11-08 |
| C-08 | Enrichment | Language detection, EN/DE lexicons, sectioning, requirements, seniority, salary, eligibility cues, skill normalisation | WP-08-01, WP-08-02, WP-08-03, WP-08-06 |
| C-09 | Profile and CV ingestion | Versioned profile, proficiency provenance, work authorisation, upload validation, extraction, review defaults | WP-03-02, WP-07-01, WP-07-02, WP-07-03, WP-07-04 |
| C-10 | Matching and evaluation | Deterministic ScoreCard, eligibility verdict, optional validated LLM rationale, skill-gap | WP-01-02, WP-01-03, WP-08-04, WP-08-05, WP-08-06, WP-10-05 |
| C-11 | AI routing | Provider interface, model registry, error taxonomy, key pool, cache, cost log | WP-01-06, WP-08-05 |
| C-12 | Documents | Explicit per-job CV and cover-letter drafts, review, versioning, export, PDF | WP-01-01, WP-09-01, WP-09-02 |
| C-13 | Applications, notifications, feedback | Status machine, events, queue export, notification rules, feedback loop | WP-03-03, WP-10-01, WP-10-02, WP-10-03, WP-10-04 |
| C-14 | Store, migrations, exports | SQLite store, migrations, importers, compat exports, backups, verification | WP-00-01, WP-00-02, WP-00-03, WP-01-04, WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-10-02, WP-12-03, WP-13-02, WP-13-03 |
| C-15 | Health and monitoring | Run records, metrics, guards reporting, drift detection, diagnostics | WP-00-04, WP-04-04, WP-04-05, WP-12-01, WP-12-03, WP-12-04 |
| C-16 | Hosted platform layer | Accounts, sessions, tenant isolation, workers, object storage, compliance flows (staged) | WP-13-01, WP-13-02, WP-13-03, WP-14-01, WP-14-02, WP-14-03, WP-15-01, WP-15-02, WP-16-01, WP-16-02 |
| C-17 | Imports | Paste, .eml/.mbox, Telegram forward, CSV into the canonical job model | WP-05-04, WP-14-03 |

## 6. Implementation boundaries

An implementation agent must not:

1. **Expand scope.** Anything in a package's non-scope column, or not listed in its scope, needs a new or amended work package.
2. **Resolve a pending decision.** A PCD default may be used only as stated in GOV-02 §3 and must be recorded in the report.
3. **Change unrelated architecture.** Invariants in GOV-01 §3 are not editable by a work package.
4. **Bypass a security gate.** Gates in GOV-05 §3 are not waived by the package that needs them.
5. **Add an unapproved dependency.** Only DEC-013 packages, `tldextract` under the PCD-018 default, and `pypdf`/`python-docx` after PCD-009 is answered.
6. **Fake an integration.** A mocked provider, fixture or simulation is labelled as such in tests, reports and UI wording (DEC-047); no code path may return a hard-coded "success" for an unavailable source, provider or model.
7. **Mark an unavailable test as passed.** Missing runtimes (for example WeasyPrint) fail the gate; they are not skipped silently (WP-00-03).
8. **Touch MUST-KEEP files beyond the package scope** or shrink one by more than 20 percent without stop-and-ask (DEC-042).
9. **Create documents, call external AI with personal data, or enable a provider** outside the explicit paths defined by DEC-019, DEC-045 and DEC-032.

## 6.1 Dependency rule
A package may start only when every package in its *Depends on* column is `merged`. The phase order in §1 is a recommended sequence; the dependency columns are binding.
