# 01 — Existing System Assessment

Status: design document, 2026-11-01. Part of [FINAL_SYSTEM_STRATEGY_AND_DESIGN.md](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md).
No production code was changed to produce this assessment.

## 1. What was assessed (and the one assumption)

"The existing repository" is ambiguous in this project, because two code lines exist. This assessment uses:

| Line | Ref | Role in this design |
|---|---|---|
| **Owner's clean line** (assessed) | branch `feature/extra-sources` @ `3177234` = original zip + local app (`jobhunter_ui/`) + extra sources (`scanners/ats.py`, `feeds.py`, `net.py`) | **Source of truth for "what exists".** The owner chose this line explicitly (clean branch from the original zip, then Tier 1 + Tier 2). |
| **GitHub rewrite** (reference only) | `shd2w/Jobs_hunter` @ `4b0302e` (54 commits, ~22k lines in `jobhunter_app/`, SQLite store, 49 test files) | Donor of ideas and tests. Not assessed for maturity, because it removed CV tailoring/PDF features that the owner wants kept. |

> **Assumption A0.** If the owner meant the GitHub rewrite as "the repository", chapters 1–3 of this assessment change
> (it has a database and migrations; this line has none), but every approved decision and the target design below still apply.
> This is flagged again as Open Technical Decision OT-0 in the primary document.

Evidence conventions: `file:line` = read by inspection. "Run" = executed in this session (2026-11-01, Python 3.12.3, Linux).
Nothing here was run against live job sites, live AI providers, Telegram, or Windows.

## 2. Commands actually run

| Command | Result |
|---|---|
| `python -m pytest -q` on `feature/extra-sources` | first run **283 passed, 1 skipped** (`test_ui_integration.py` skipped: `weasyprint` not installed). After `pip install weasyprint`: **286 passed, 0 skipped** (the integration file has 3 tests) |
| `pytest --collect-only` grouped by file | counts in section 5 |
| `pip index versions <pkg>` for 15 packages in the Decision Log / research | every pinned version exists on PyPI (e.g. python-jobspy 1.4.1, ats-scrapers 0.3.0, curl_cffi 0.17.0, pydantic 2.14.2, certifi 2026.10.23) |
| `pip download --platform win_amd64` for curl_cffi, selectolax, RapidFuzz, lxml, datasketch (cp312) and the first three on cp314 | wheels exist for all |
| `pip install ats-scrapers[all]==0.3.0` in a scratch venv, then inspect | 75 scraper modules; `Job` model has **30 fields**; MIT; `[all]` extra pulls `cloakbrowser`, `httpcloak`, `playwright` (see 4.3) |
| `git clone moonie0201/ats-directory` | 1,804 rows, CC0 licence, providers: ashby 400, greenhouse 400, lever 400, recruitee 400, rippling 204 (**no** Workday/Personio/Workable/SmartRecruiters) |
| Live fetch of Remotive/Jobicy/Arbeitnow/Remote OK from the sandbox | **failed (sandbox has no route to these hosts)** — no live evidence exists for any source |

## 3. Inventory

| Area | Files (lines) |
|---|---|
| Scanners | `scanners/jobspy_scanner.py` (329), `workday.py` (251), `bridge.py` (200), `base.py` (92), **`ats.py` (230), `feeds.py` (255), `net.py` (196), `jobspy_registry.py` (9)** — the bold ones were added in the previous session |
| Filters / dedup / cache | `utils/filters.py` (141), `dedup.py` (136), `jd_cache.py` (62), `jd_fetcher.py` (258) |
| AI | `agents/evaluator.py` (320), `smart_router.py` (309), `openrouter_client.py` (298), `google_client.py` (276), `utils/json_extract.py` (51) |
| Documents | `agents/cv_tailor.py` (491), `agents/cover_letter.py` (133), `utils/pdf_generator.py` (624), `CV_Example.py` (206) |
| Stores / exports | `utils/evaluation_store.py` (136), `excel_export.py` (290), `queue_exporter.py` (930), `telegram.py` (161) |
| Entry points | `run_scan.py`, `run_evaluate.py` (516), `run_all.py`, `run_export_queue.py`, `run_health.py`, `run_app.py`, `run_check_sources.py` |
| Local app | `jobhunter_ui/service.py` (541), `server.py` (186), `runner.py` (107), `ranking.py` (110), `static/` (3 tabs: Jobs, Find & score, Setup) |
| Config | `config/portals.yml`, `config/profile.yml` (85 lines) |
| Storage | **No database.** Flat files: `data/pipeline.md`, `scan-history.tsv`, `jd_cache.json`, `evaluations.json`, `app_state.json`, Excel DB, `reports/*.md`, `output/*.pdf`, `below_threshold.md`, `applications.md` (read by dedup) |

Call paths verified by reading: `run_scan.py → scanners → PipelineBridge.process → filters → DeduplicatorStore → pipeline.md/scan-history.tsv/jd_cache.json`;
`run_evaluate.py → Evaluator → (optional CVTailor/CoverLetterWriter → pdf_generator) → evaluation_store → evaluations.json + Excel + Telegram`;
`run_export_queue.py → queue_exporter → application_queue.jsonl`;
`jobhunter_ui/service.py` reads/writes `evaluations.json` + `app_state.json` and launches the CLI scripts as subprocesses (`runner.py`).

## 4. Findings that shape the design

### 4.1 Defects and risks (code inspection unless marked)

| ID | Finding | Evidence | Effect |
|---|---|---|---|
| DEF-01 | **Automatic CV creation exists.** When `create_cv` is true, every job scoring ≥ `auto_cv_threshold` gets a tailored CV + PDF without any per-job user action. | `run_evaluate.py:298-343`, `:407-412`; `config/profile.yml` keys `evaluation.create_cv`, `auto_cv_threshold`; CLI flag `--create-cv` | Contradicts the final requirement (CV work only on explicit per-job request). Currently dormant because `create_cv: False`, but one flag enables it. |
| DEF-02 | **Candidate facts are hard-coded in the evaluator prompt**, including language levels and "never reject for German". | `agents/evaluator.py:34-39` | Evaluation does not follow the profile; three files disagree about the same person's languages (see 4.4). |
| DEF-03 | **Total score is taken from the model**, not recomputed. The UI recomputes only when custom weights are chosen. | `agents/evaluator.py` JSON field `global_score`; `jobhunter_ui/ranking.py` `score_of` | Same job can show different totals on CLI/Excel/Telegram vs UI; arithmetic errors by the model pass through. Not reproduced with live AI. |
| DEF-04 | **Non-atomic writes** of `pipeline.md` and `scan-history.tsv` header. | `scanners/bridge.py:50,57,180` (`write_text`) | A crash mid-write can truncate the pending list. (`evaluation_store` and UI writes *are* atomic.) |
| DEF-05 | **SmartRecruiters adapter has no authorisation gate.** Research says "postpone unless authorised" (robots.txt/ToS); the adapter added last session activates as soon as a board is listed. | `scanners/ats.py` (`COOLDOWN_SECONDS` includes `smartrecruiters`); research §3 | Compliance regression introduced by this project. Default list is empty, so nothing runs today. |
| DEF-06 | **`pages: 2` in `jobspy_providers` is a no-op.** It is copied through to the search dict but never used for pagination (`grep pages` finds only the copy loop). | `scanners/jobspy_scanner.py:130`; `config/portals.yml:174-201` | Misleading configuration, introduced last session. Providers return one page per query. |
| DEF-07 | **AI routing has no error taxonomy.** 429 → sleep ≤5 s → next key; other failures are broad `except Exception`. No jitter, no persisted key cooldown. | `agents/smart_router.py:234-240, 64, 103, 290` | A failed call and a malformed answer are not distinguishable; retry policy is implicit. No direct tests. |
| DEF-08 | **Workday scanner cannot exceed the 2,000-result cap** and reads `total` on every page. | `scanners/workday.py:37, 147-201`; no test imports it except my mocked wiring test | Large tenants truncate silently. `tracked_companies: []` so unused by default. |
| DEF-09 | **CV text is sent to an external AI provider** by "Convert my CV" without a data-flow notice. | `jobhunter_ui/service.py:457-476` | Privacy gap against the "never expose unnecessarily" rule. |
| DEF-10 | **Contact details live in `config/profile.yml`** inside the repository tree. | `config/profile.yml` (candidate block) | Easy to push publicly by mistake; no template/real split. |
| DEF-11 | **No direct tests** for `smart_router`, `evaluator`, `excel_export`, `telegram` (only faked via UI tests), `jd_cache`, `run_health`, `workday`; `pdf_generator` is only exercised through the integration test. | grep over `tests/` | "Works" is unproven for the AI, notification and export paths. |
| DEF-12 | **Dedup is URL + company/title only.** No canonical id, no cross-source merge, no lifecycle (new/updated/closed). | `utils/dedup.py:1-9` | Same job from LinkedIn + employer ATS appears twice. |
| DEF-13 | **Title filter is substring-based, IT-specific and silent.** Negative terms match as plain substrings (`lead` removes "Lead Generation", `staff` removes "Staffing", `architect` removes "Architecture"); the shipped negatives (`Senior, Lead, Principal, Staff, Director, Head of, Architect, 5+/7+/10+ years`) and 51 positive terms encode one entry-level IT profile; rejected jobs are dropped without any record. | `utils/filters.py:37-38, 46-52`; `config/portals.yml` `title_filter` | Relevant roles disappear invisibly; unusable for a multi-profession, multi-user platform. Found by code reading, not by a failing test. Added in Revision 1 (doc 08). |
| DEF-15 | **The JobSpy scanner drops the link fields that discovery needs.** JobSpy 1.4.1 returns `job_url_direct` (Indeed, ZipRecruiter, BDJobs, Naukri) and `company_url_direct` (Indeed, Glassdoor, ZipRecruiter, BDJobs); the scanner never reads `job_url_direct`, `company_url` or `company_url_direct`, so no employer link ever reaches the pipeline. The LinkedIn scraper exposes none of them (only a LinkedIn company page). | `scanners/jobspy_scanner.py` (row parsing); `jobspy/*/__init__.py` in 1.4.1 | Discovery at scale has no input today; also the planned harvest cannot rely on LinkedIn. Added in doc 09. |

### 4.2 Duplication / divergence

| Item | Copies | Problem |
|---|---|---|
| Score weights 30/20/20/20/10 | `evaluator.py` prompt text, `evaluator._save_report` table, `jobhunter_ui/ranking.py DEFAULT_WEIGHTS` | Three hand-synchronised copies. |
| Greenhouse/Lever/Ashby/SmartRecruiters parsing | `scanners/ats.py` (mine) vs `ats-scrapers` adapters (Decision D2) | Parallel implementations once D2 is executed. |
| Remote OK / We Work Remotely | `scanners/feeds.py` (mine) vs `ats-scrapers` modules `remoteok`, `weworkremotely` | Same. |
| "Create CV" | `run_evaluate.py` (auto) vs `jobhunter_ui/service.py:305 create_cv` (explicit) | Two call sites into `CVTailor`; only one honours the new policy. |
| Job identity | `queue_exporter.canonicalize_url` (mirrors UAA) vs `ranking.job_id` (sha1 of URL) vs dedup URL strings | Three notions of "same job". |

### 4.3 What the research/decision inputs get wrong or leave out (verified against the packages)

1. **Workday facet splitting already exists in `ats-scrapers` 0.3.0** (`workday.py`, 672 lines: `PAGE_LIMIT = 20`, `QUERY_TOTAL_CAP = 2000`, subdivision by `jobFamilyGroup`, detail fetch by `externalPath`). Research marks Workday "Partial; needs custom paginator" and Decision D3 says "Build". What is genuinely missing is **persisted incremental detail state** (its `seen` set is per-run, `workday.py:226-235`) and a global rate cap.
2. **Adapters the research lists as "Missing; build" exist**: `rippling` (241 lines), `breezy` (314), `bamboohr` (346), `teamtailor` (180), plus `bundesagentur`, `eures`, `personio`, `workable`, `recruitee`. Whether they implement the specific traps in D5 was only spot-checked: Greenhouse has **no** `pay_transparency` call (gap confirmed), Recruitee has **no** 401 fallback (gap confirmed), Workable has detail-fetch concurrency 4 and retries but no `v3`/shortcode grouping seen, Personio sends only a User-Agent header (no `X-Company-ID`, consistent with the D5 finding).
3. **`pip install "ats-scrapers[all]"` (Decision D2) installs stealth/anti-detect tooling** (`cloakbrowser`, `httpcloak`, `playwright`). Adapters `darwinbox` and `uber` default to the "cloak" TLS-impersonation engine; `avature`, `meta`, `tesla` use the cloak browser; `fetch_escalate` (retry a 403/406 through impersonation) defaults to **False** for every adapter. A plain install without extras fails on import (`bs4` missing). This conflicts with the no-bypass rule (primary doc §7.4); resolution is in doc 02.
4. **`ats-directory` covers 5 providers and mostly startup boards.** It cannot resolve Workday, Personio, Workable, SmartRecruiters or Teamtailor, and says nothing about Gulf/Egypt employers. The "six-cheap-ATS probe order" in D10 needs a slug source for Personio/Workable that the directory does not provide.
5. Several Decision Log claims are **not independently verified** here: "34-column DataFrame", "~95% of consumer boards", "4.5k stars". Versions, the 30-column schema, licences and wheel availability are verified.

### 4.4 Candidate proficiency: what `config/profile.yml` really contains

`config/profile.yml` has **no structured per-skill proficiency**. It has:
`skills.technical` (6 free-text group strings), `skills.non_technical` (5 strings, the last being `"Arabic (Native), English (C2), German (C1)"`), `preferences`, `target_roles`, `evaluation`, `queue_export`.
No other file in either repository carries skill levels. Language levels appear in four places and **disagree**:

| Source | English | German |
|---|---|---|
| `config/profile.yml` and `agents/evaluator.py:34` | C2 | C1 |
| `CV_Example.py:196` (sample CV generator) | C1 (IELTS 7) | A2 |
| `jobhunter_ui/static/cv.example.md:52` | — | "Intermediate" |
| Owner's statement earlier in this project | — | B2 certified, C1 self-assessed |

Consequence for the design: the candidate model must store **level + provenance** (confirmed / self-declared / extracted-unconfirmed / unknown) and the migration may **not** promote any of these values to "confirmed" on its own (doc 04 §3).

## 5. Test inventory (all currently passing; run 2026-11-01)

| Test file | Tests | What it proves |
|---|---:|---|
| `test_queue_exporter.py` | 38 | UAA export contract, skip reasons, determinism |
| `test_german_policy.py` | 46 | German-policy decisions (rules, not AI) |
| `test_identity_golden_contract.py` | 29 | `application_id` hashing/canonical URL golden values |
| `test_export_queue_wq2.py` / `test_uaa_contract.py` / `test_run_all_export_integration.py` | 17 / 9 / 6 | Export CLI and handoff |
| `test_candidate_profile_truthful.py` | 12 | Exporter never invents profile facts |
| `test_filters.py` / `test_dedup.py` / `test_bridge.py` | 21 / 9 / 6 | Filtering, URL dedup, pipeline writing |
| `test_evaluation_store.py` / `test_jd_fetcher.py` / `test_utf8_logging.py` | 12 / 10 / 7 | Store, JD fetch parsing, logging |
| `test_ui_service.py` / `_server.py` / `_ranking.py` | 19 / 11 / 7 | Local app; AI and Telegram **faked** |
| `test_ui_integration.py` | 3 (skipped unless WeasyPrint is installed) | Real `CVTailor` + real WeasyPrint PDF with **faked AI** (Linux only) |
| `test_extra_sources.py` | 24 | Extra scanners; all HTTP **mocked** |
| **Total** | **286 passed** (283 without WeasyPrint) | |

Everything involving a real AI provider, real job site, Telegram, or Windows is **unverified**. A test environment without WeasyPrint silently skips the only test that proves CV/PDF generation; the design makes that a CI failure (doc 06 §2).

## 6. Capability matrix

Maturity: IV = implemented & verified · IU = implemented, unverified · PI = partially implemented · BR = broken · DI = duplicated/inconsistent · DO = documented only · NI = not implemented · OB = obsolete.
Treatment: PRESERVE · EXTEND · REFACTOR · CONSOLIDATE · REPLACE · REMOVE · BUILD.

| # | Capability | Current implementation | Maturity | Evidence | Known problems | Treatment (justification) |
|---|---|---|---|---|---|---|
| 1 | JobSpy ingestion | `scanners/jobspy_scanner.py`, 98 searches × config | IU (parsing: mocked tests) | file; `test_extra_sources.py` | `pages` no-op (DEF-06); link fields dropped (DEF-15); no query-matrix; no pydantic mapping; no live run | **EXTEND** (D1 says wrap, not replace; keep config format) |
| 2 | Workday/SmartRecruiters direct scanner | `scanners/workday.py` | PI | DEF-08 | 2,000 cap; no tests | **REPLACE internals** with `ats-scrapers` Workday adapter behind the same `tracked_companies` config (adapter already does facet splitting) |
| 3 | ATS boards (GH/Lever/Ashby/SR) | `scanners/ats.py` | IU (mocked) | tests | DEF-05; duplicates D2 | **REFACTOR — keep as tested fallback** (doc 10 F5) into the adapter contract; keep parsers' fixtures as regression tests |
| 4 | Remote feeds | `scanners/feeds.py` | IU (mocked) | tests | duplicates `ats-scrapers` feeds; no live proof | **CONSOLIDATE** (keep Remotive/Jobicy/Arbeitnow cooldown rules) |
| 5 | Title/location filters | `utils/filters.py` | IV | 21 tests | substring location match; allow-list only | **PRESERVE** (becomes a domain service; add structured location later) |
| 6 | Dedup | `utils/dedup.py` | PI | DEF-12; 9 tests | URL + company/title only | **EXTEND** to the D4 dedup engine (Stage 3 deferred by owner in Revision 1) behind the same interface |
| 7 | Pipeline bridge | `scanners/bridge.py` | PI | 6 tests; DEF-04 | non-atomic; file-only | **REFACTOR** into `IngestionService`; `pipeline.md` becomes a derived export |
| 8 | JD fetch + cache | `utils/jd_fetcher.py`, `jd_cache.py` | IV (parse) / IU (cache) | 10 tests | Playwright fallback path; cache untested | **PRESERVE**; add "no escalation after 401/403/429" rule |
| 9 | AI evaluation | `agents/evaluator.py` | IU | DEF-02, DEF-03, DEF-11 | hard-coded facts; model total trusted | **REFACTOR** into structured extraction + deterministic scorer (doc 03 §6); no second engine |
| 10 | AI routing | `agents/smart_router.py` + 2 clients | IU | DEF-07 | no taxonomy/jitter/cooldown | **REFACTOR** (provider interface, error classes); keep key rotation + Google→OpenRouter fallback |
| 11 | CV tailoring | `agents/cv_tailor.py` (JSON-patch) | IV with faked AI on Linux (run: 3 integration tests pass); real AI output unverified | `test_ui_integration.py` | auto path DEF-01 | **PRESERVE** the patch approach; **change trigger** to explicit-only |
| 12 | PDF generation | `utils/pdf_generator.py` | IV on Linux (PDF produced in integration test); Windows unverified | `test_ui_integration.py`; no direct unit test | WeasyPrint needs GTK/Pango runtime on Windows (README: MSYS2) | **PRESERVE**; add Windows verification gate |
| 13 | Cover letters | `agents/cover_letter.py` | IU | used in UI tests (faked AI) | — | **PRESERVE**, explicit-only |
| 14 | Telegram | `utils/telegram.py` | IU | no direct test | single channel/single format | **EXTEND** (notification service with rules) |
| 15 | Excel DB | `utils/excel_export.py` | IU | no test | file-lock fallback exists | **PRESERVE** as derived export |
| 16 | Evaluation store | `utils/evaluation_store.py` | IV | 12 tests | JSON array, rewritten per append | **PRESERVE** as compat export; DB becomes source of truth (doc 04) |
| 17 | UAA queue export | `utils/queue_exporter.py` | IV | 99+ tests, golden hashes | requires CV+cover PDFs | **PRESERVE** byte-for-byte; input changes to DB view |
| 18 | Health check | `run_health.py` | IU | no test | file/env only | **EXTEND** into diagnostics service |
| 19 | Local dashboard | `jobhunter_ui/` | IV (faked AI) | 37 tests | 3 screens; reads files directly; own ranking | **REFACTOR** onto shared services; add screens per doc 05 |
| 20 | Ranking | `jobhunter_ui/ranking.py` | DI | DEF-03, 4.2 | weights copied | **CONSOLIDATE** into `domain/scoring` |
| 21 | Candidate profile | `config/profile.yml` | PI | 4.4, DEF-10 | no proficiency; PII in repo | **EXTEND** (canonical profile model + sync rules) |
| 22 | CV ingestion/extraction | UI "Convert my CV" (`service.py:457`) | PI | DEF-09 | full text to provider; no review step | **EXTEND** (rule-based first, optional AI with consent, review/confirm) |
| 23 | Application tracking | `app_state.json` statuses, `applications.md` | PI | `service.set_status` | no events/history | **EXTEND** |
| 24 | Skill-gap analysis | evaluator free-text gaps | PI | UI shows gaps from evaluation | not structured | **BUILD** (from structured requirements) |
| 25 | Learning recommendations | — | NI | — | — | **BUILD** (small, rule-based, optional) |
| 26 | Database + migrations | — | NI | no DB in tree | — | **BUILD** (SQLite) |
| 27 | Source registry/health | `portals.yml`, `run_check_sources.py`, cooldown JSON | PI | files | no states/history | **BUILD** on top of existing config |
| 28 | Monitoring/anomaly | `logs/scan.log` only | NI | — | — | **BUILD** |
| 29 | Sample CV script | `CV_Example.py` | OB-ish | 4.4 | conflicting claims | **REFACTOR**: move to `examples/`, strip language claims, mark as sample |
| 30 | Docker/deploy | `Dockerfile`, `docker-compose.yml` | IU | not run | Windows is primary target | **PRESERVE**, deprioritise |

## 7. Reference value of the GitHub rewrite

Harvest, do not merge: SQLite schema and `PRAGMA user_version` migration pattern (`store.py`, `migration.py`), exactness tests, `matching.py` requirement cues, `requirements.py`/`evidence_mapping.py` evidence idea, `source_health.py` gating idea, the Scrapling-based engine (rejected here: new dependency not in the Decision Log). Do not adopt its removal of CV/PDF features or its `AGENTS.md` push policy.

## 8. Addendum (2026-11-02): evidence added after this assessment

This document is a point-in-time assessment of `feature/extra-sources` @ `3177234`; its findings stand. Later work added evidence and two defects, summarised here so nothing is hidden:

| Item | Result | Source |
|---|---|---|
| DEF-13 title filter (substring, IT-specific, silent) | added to §4.1 | doc 08 §4.10 |
| DEF-15 JobSpy link fields dropped; LinkedIn exposes none | added to §4.1 | doc 09 A1, A2 |
| Library resolver `resolve_careers_url` | exists; 34/34 on hand-written URLs | doc 10 E1 |
| `ats-scrapers` maturity | 3 releases, first 2026-07-22, single author | doc 10 E4 |
| `python-jobspy` churn | 1.2.0 → 1.4.1 in 21 days; 34 output columns confirmed | doc 10 E4, E5 |
| Capability 3 (`scanners/ats.py`) treatment | changed from CONSOLIDATE to **REFACTOR, kept as tested fallback** | doc 10 F5 |
| Disposition totals | Preserve 9 · Extend 7 · Refactor 6 · Consolidate 2 · Replace 1 · Build 5 (= 30) | this table |

