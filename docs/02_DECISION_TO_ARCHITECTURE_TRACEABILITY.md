# 02 — Decision-to-Architecture Traceability

Status: design document, 2026-11-01. Part of [FINAL_SYSTEM_STRATEGY_AND_DESIGN.md](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md).
Inputs: `Decision_log.md` (D1–D10 and Conflicts 1–4), `Final_research_summary.md`, the final-design brief, `docs/PROMPT.md` (working contract), [01 assessment](01_EXISTING_SYSTEM_ASSESSMENT.md).

## 1. Authority and how conflicts were handled

Order used (as the brief requires): **repository state → Decision Log → research → older project documents.** The brief itself is the newest instruction and the owner's own statement of constraints, so where it is explicit ("never", "must not") it outranks the Decision Log's wording but **not** the Decision Log's intent. The Decision Log carries no approval metadata; it is treated as approved because the brief calls it the approved-decision record.

Nothing below reopens a decision's *goal*. Four decisions need their *method* adjusted because the repository or package evidence contradicts an assumption they rest on. Each adjustment is labelled **SCOPE-ADJUSTED** and needs the owner's one-line acknowledgement (OT-1…OT-3 in the primary document).

## 2. Conflicts between instruction sources

| ID | Conflict | Sources | Resolution | Needs owner? |
|---|---|---|---|---|
| RC-1 | **Automatic CV creation.** `docs/PROMPT.md` §3 allowed an opt-in setting `evaluation.create_cv`; the brief says the system must **never** modify/tailor/generate a CV merely because a job was found. | PROMPT.md §3 vs brief §5.3; code `run_evaluate.py:298-343` | **Brief wins.** The automatic path is removed in phase P1. `create_cv` and `auto_cv_threshold` keys stay readable for one release (warning), then are ignored; threshold survives only as a *notification/highlight* threshold. CLI `--create-cv` becomes valid only together with `--url` (one explicit job). | No (already stated by the brief) |
| RC-2 | **TLS impersonation / proxies / cap-bypass language** (D1 "bypass 1,000 caps", D6 proxy rotation, D2 `[all]`) vs brief §7.4 "must not depend on bypassing CAPTCHAs, rate limits, technical restrictions, platform terms". | D1, D2, D6, research §4 vs brief §7.4 and PROMPT.md §3 ("no stealth tricks") | See §4 (D1, D2, D6). Summary: partition queries (narrower searches are ordinary use); **no proxy rotation, no cloak/stealth adapters, no retry-after-block**; consumer boards are tier "restricted", default **off per provider**, and **nothing core depends on them**. | **Yes — OT-1** |
| RC-3 | **Automatic application submission is a non-goal**, but JobHunter already exports `application_queue.jsonl` for the separate UniversalAutoApplier (UAA). | brief §5.1 vs `utils/queue_exporter.py` (99+ contract tests) | JobHunter never submits. The export stays as an **explicit user hand-off**: a job enters the queue only after the user marks it "ready to apply" and has user-generated documents. Contract and hashes unchanged. | **Yes — OT-6** (confirm UAA hand-off stays in scope) |
| RC-4 | **Canonical schema.** D2/Conflict 1 adopts the 30-field `ats-scrapers` `Job` model; the repository's internal job type is the 8-field `JobPosting`, and UAA identity is a third concept. | D2, Conflict 1 vs `scanners/base.py`, `queue_exporter.py` | Adopt `Job` as the canonical *ingest* model (as approved). Map at the edges: `JobPosting → Job` for legacy scanners, `Job → queue row` for UAA. UAA `application_id` hashing is untouched (golden tests). | No |
| RC-5 | **New dependencies.** `docs/PROMPT.md` §8 says "stop and ask if a new dependency is needed"; D7 approves a large stack. | PROMPT.md §8 vs D7 | **D7 is the approval**, limited to the named packages and pinned versions. Anything else still needs a decision. Packages are installed in *groups* (core, ingestion, dedup) so a phase installs only what it uses. | No |
| RC-6 | **Research says "build" for adapters that already exist** (Rippling, Breezy, BambooHR, Teamtailor) and "needs custom paginator" for Workday which already facet-splits. | research §3 vs `ats-scrapers` 0.3.0 contents (doc 01 §4.3) | Decision intent kept (full ATS coverage); method changed from *build* to **verify, then patch gaps** (D3, D5). | **Yes — OT-2** (acknowledge D3 scope change) |
| RC-7 | **Research "postpone unless authorised" for SmartRecruiters** vs the SmartRecruiters scanner added in the previous session. | research §6C vs `scanners/ats.py` | Previous work is the error. SmartRecruiters becomes `disabled_by_policy`; each board needs `authorized: true` recorded by the owner (phase P1). | No (defect DEF-05) |
| RC-8 | **Profile truth.** Profile/evaluator/sample-CV disagree on language levels (doc 01 §4.4). | repo files | Levels are stored with provenance; the evaluator reads the profile; migration marks existing values `self_declared`, never `confirmed`. | **Yes — OT-5** (owner states the true levels) |
| RC-9 | **Free-first vs multi-account key rotation.** Existing router rotates up to 4 OpenRouter + 2 Google keys "to multiply quota". Provider terms for this practice were **not** checked. | `agents/smart_router.py:1-12` | Preserve (approved earlier, existing feature) but make it configurable and log per-key usage; flag for terms review. | **Yes — OT-9** |
| RC-10 | **Scope change to a platform** (any user, any country; English and German postings; Arabic removed; profession-agnostic) and **owner removals** (Stage 3 MinHash, source-state promotion rules). | owner instructions 2026-11-02 vs brief §12 (local Windows, no SaaS, free-first) | Newest instruction wins. Multi-user becomes a staged track (P13–P16) that is additive; the consumer-board tier is local-mode only in hosted mode. Full ledger and conflicts C-1…C-5: [08](08_REVISION_1_PLATFORM_SCOPE_AND_REVIEW_RESPONSE.md) §2. | **Yes — C-1…C-5** |
| RC-11 | **Plan said "retire `scanners/ats.py` after parity"** while D2 makes a 14-week-old, single-author library the ATS backbone. | doc 10 E4, F5 | Keep `scanners/ats.py` (24 mocked tests) as the tested fallback until library adapters pass ≥ 4 weeks of live verification; adopt only the resolver immediately. | No (OT-19 default) |

## 3. Decision-to-Architecture Traceability Matrix

| Decision | Final interpretation | Affected components | Architectural consequence | Design reference |
|---|---|---|---|---|
| **D1** python-jobspy for consumer boards | JobSpy is the **only** consumer-board engine (no home-grown LinkedIn/Indeed scrapers, no paid actors). Wrapped as one `SourceAdapter` per provider. Provider/error attrs are captured, DataFrame rows map to canonical `Job`, `certifi` floor enforced, queries partitioned. Providers are policy-gated and off by default. | `scanners/jobspy_scanner.py`, `jobspy_registry.py`, source registry, ingestion | `JobSpyAdapter` (EXTEND existing scanner); `QueryMatrix` planner; `coverage_complete=False` on all consumer scans so **lifecycle never closes a job because a consumer board stopped listing it** | 03 §5, 04 §5–6 | **Version churn (doc 10 F6):** pin an exact version with hash; contract test on the 34 output columns and `attrs["errors"]`; monthly upgrade review.
| **D2** `ats-scrapers` as ATS framework + canonical model | Use as a pinned library; subclass `BaseScraper`/`ScraperRegistry` at runtime, **no fork**. Install **without `[all]`**; add only needed extras (`beautifulsoup4`, `html2text`). Adapters on an **allow-list**; adapters using the cloak engine/browser (`darwinbox`, `uber`, `avature`, `meta`, `tesla`) are `blocked_by_policy`. Hosted Parquet snapshot off by default (cold-start only, owner opt-in). | new `adapters/ats/`, requirements, source registry policy gate | `AtsAdapterBase` wrapping `BaseScraper`; patches in `adapters/ats/patches/`; canonical `Job` model is the ingest contract; `scanners/ats.py` is **kept as the tested fallback** until the library adapters have passed live verification and run clean for ≥ 4 weeks ([10](10_METHODOLOGY_FEASIBILITY_REVIEW.md) F5) | 03 §5, 04 §2, 04 §5 — **SCOPE-ADJUSTED** (`[all]`) | **Library maturity (doc 10 F5, OT-19):** ~14 weeks old, 3 releases, single author — adopt the resolver now, keep the tested parsers as fallback, pin and hash, vendor into `third_party/` if upstream stalls.
| **D3** Workday facet paginator + detail fetcher | Goal kept (>2,000-job tenants fully collected, details only for new/changed postings, ≤ ~90 req/min global). Method: **reuse the library's existing facet splitter, add what it lacks**: persisted per-item state (`externalPath` + summary hash), global rate limiter, tenant case/locale validation. | `scanners/workday.py` (replace internals), `source_item_state` table | `WorkdayAdapter(AtsAdapterBase)`; `source_item_state` drives incremental detail fetch (Conflict 2 resolution) | 03 §5, 04 §4 — **SCOPE-ADJUSTED** |
| **D4** three-stage dedup + lifecycle | Built as a domain service. Stage 1 `global_id`+canonical URL (w3lib, strips `utm_*`, `gh_jid`…), Stage 2 normalised company + requisition id then RapidFuzz, plus exact `description_hash` matching. ATS record is canonical; consumer URLs become secondary links. **Stage 3 (MinHash LSH) is deferred by the owner (Revision 1, doc 08 §4.12).** Possible duplicates are auto-grouped with undo and never silently merged or deleted. Lifecycle `new/updated/closed` changes only after a *complete, successful* sync of that source scope. | `utils/dedup.py` (extend behind same interface), new `domain/dedup`, `domain/lifecycle`, tables `jobs`, `job_links`, `job_sightings` | `DedupService`, `LifecycleService`; auto-grouped list with undo (no mandatory review queue); UAA identity kept separate | 03 §5, 04 §6 |
| **D5** ATS protocol-trap patches | Greenhouse pay (confirmed gap) and Recruitee 2027 fallback (confirmed gap) are real builds. Personio, Workable, Rippling: **verify the existing adapter first**, patch only failing behaviours. All patches are offline-fixture tested. | `adapters/ats/patches/*`, fixtures | One patch module per provider; each has fixtures + contract tests; Recruitee JSON→XML→`data-props` ladder must be demonstrable with fixtures before **2027-02-10** | 03 §5, 06 §3, 07 P11 |
| **D6** LinkedIn query-matrix orchestrator | Goal kept (LinkedIn usable despite filter changes and result caps). Method limited to: filter→keyword translation, partition by city/date window, `matched_search_term` tag, 3–7 s jitter. **No proxy rotation**; stop on first 429 (circuit breaker, no retry); provider state `experimental`, default off, low volume. | `JobSpyAdapter` (planner), source registry | `LinkedInQueryPlanner` inside the adapter; circuit breaker is a registry feature shared by all adapters | 03 §5, 04 §5 — **SCOPE-ADJUSTED** (no proxies) |
| **D7** FOSS parse/retry/validate stack | Exact pins from the log (all verified to exist on PyPI; Windows wheels verified for the compiled ones). Hash-pinned lock file. `stamina` is the single retry layer (test mode in CI). `pydantic-xml` for Personio/Teamtailor feeds. Packages installed per phase group. | `requirements*.txt` → `pyproject.toml` + lock | New dependency groups: `core`, `ingestion`, `dedup`, `docs`; `extruct`/`crawlee` deferred until their phases | 06 §6, 07 P0 | **Addition (OT-18, assumed accepted):** `tldextract` in offline mode for company-domain merging.
| **D8** no paid Apify/Scrapfly | Enforced by a CI policy test over the lock file and config (no `apify-client`, no Scrapfly SDK). Useful actor patterns (cheap-ATS-first probe order, canary tests) re-implemented locally. | CI, `policy/blocked_dependencies.txt` | Policy test `tests/test_policy_blocked.py` | 06 §2 |
| **D9** no login scrapers / archived tools | Same blocked-list test also rejects `selenium`, `undetected-chromedriver`, `jobfunnel`, `python-jobscrape`, `jobspy2`, `jobsparser`. The existing single-URL Playwright **JD fetch** (`jd_fetcher.fetch_jd_playwright`) is not ingestion and stays, with a rule: never used after 401/403/429, no stealth plugins. | CI, `utils/jd_fetcher.py` | Policy test + JD-fetch escalation rule | 06 §2, 06 §5 |
| **D10** `ats-directory` | Vendored CC0 snapshot (1,804 rows verified; **providers: Ashby, Greenhouse, Lever, Recruitee, Rippling only**) with provenance and import date. Used as a *suggestion list* ("watch this company") and for probing; **never** auto-enabled. Probe order: Greenhouse, Lever, Ashby, Recruitee, then Personio/Workable only for slugs the owner supplies (directory has none). SmartRecruiters `200 totalFound:0` = not found. The owner's own target-company list (Egypt/Oman/UAE/Germany) is the primary discovery input. | `data/reference/`, source registry UI | `CompanyDirectory` service; "Add to watchlist" flow | 03 §5, 05 §3 |
| **Conflict 1** schema vs internal models | Adopt `Job` as canonical; map at the boundary. | ingestion, store | RC-4 | 04 §2 |
| **Conflict 2** Workday detail volume | Persisted `externalPath` + summary-hash; detail only if new/changed; ≤50 workers across distinct tenants, ≤ ~90 req/min globally. | `source_item_state` | D3 | 04 §4 |
| **Conflict 3** proxies vs free-first | **Start without proxies.** A proxy is considered only if telemetry shows failed requests on *high-value* queries above 20 % over 14 days **and** the owner approves a budget. Telemetry is built in phase P4. | `source_runs` metrics | No proxy abstraction is built now | 04 §5, 06 §7 |
| **Conflict 4** Recruitee fallback now | Build now (P11 first item), because the cut-off is 2027-02-10. | Recruitee patch | fixtures + ladder test | 07 P11 |
| **Recommendation set (Phase 0/1 days 1–10)** | Mapped one-to-one onto phases P0, P3, P5 (dependency lock, canonical contract, JobSpy wrapper, ATS base + directory, Stage 1 dedup). | roadmap | — | 07 |

## 4. Decision records (status, evidence, consequences, acceptance)

Status for every record: **approved** (D-series) unless stated. "Evidence" distinguishes *verified* (I checked it) from *claimed* (from the log/research only).

### D1 — JobSpy
- **Evidence:** verified — `python-jobspy 1.4.1` exists, MIT, `Requires-Python >=3.10`, depends on `curl_cffi>=0.16.2`, pandas, pydantic, requests, beautifulsoup4, markdownify. Claimed — 34 DataFrame columns, "~95% of consumer boards", 4.5k stars.
- **Consequences:** raise the existing pin from `>=1.1.75` to `>=1.4.1`; fix DEF-06 by either implementing paging or deleting the `pages` key; per-search results include `provider_errors` and `provider_warnings` in `source_runs`.
- **Dependencies/constraints:** provider access basis = `consumer_board_guest`; tier *restricted*; terms of each provider recorded in the registry; Google Jobs stays off (broken upstream per research).
- **Acceptance:** (a) a mocked `attrs["errors"]` result yields a failed run, not an empty success; (b) a 3-city × 2-term matrix produces 6 attributed sub-queries; (c) no consumer-board run can mark any job `closed`; (d) with all consumer providers disabled the system still discovers via ATS/feeds/imports.

### D2 — `ats-scrapers`
- **Evidence:** verified — v0.3.0, MIT, 30-field `Job`, 75 modules, `ScraperRegistry`/`BaseScraper` present; `[all]` adds `cloakbrowser`, `httpcloak`, `playwright`, `pycryptodome`, `pyarrow`, `aiohttp`.
- **Consequences:** install `ats-scrapers==0.3.0` + `beautifulsoup4` + `html2text` only; registry exposes an allow-list; upgrade requires contract tests green.
- **Acceptance:** import of the allow-listed adapters succeeds in a clean Windows venv; the blocked adapters cannot be activated from config or UI; an adapter marked `blocked_by_policy` is shown as such in Sources.

### D3 — Workday
- **Evidence:** verified in code — limit 20, 2,000 cap detection, `jobFamilyGroup` subdivision, detail by `externalPath`. **Not verified live** (no network).
- **Acceptance (live, owner's machine):** a known >2,000-job tenant returns > 2,000 unique `externalPath`s; second run issues detail requests only for new/changed items (`source_item_state` hit rate logged); global rate ≤ 90 req/min.

### D4 — Dedup & lifecycle
- **Consequences:** new tables in doc 04 §4; rules in doc 04 §6; possible duplicates are **auto-grouped (collapsed, undoable)** instead of a mandatory review queue (red-team 1.4); **Stage 3 near-duplicate detection is deferred by the owner** (doc 08 §4.12), so the three-stage design is currently two stages plus an exact description hash.
- **Acceptance:** golden duplicate sets (same job on ATS + two boards; repost under a new id with an identical description; multi-location Workable job) produce the expected links; a partial or failed sync produces **zero** `closed` transitions.

### D5 — Protocol traps
| Provider | Gap status (doc 01 §4.3) | Build/verify |
|---|---|---|
| Greenhouse | pay transparency **missing** | build (bounded per-job enrichment) |
| Recruitee | token-gate fallback **missing** | build now |
| Personio | zero-header behaviour consistent with finding | verify CDATA concatenation, `.de`/`.com` fallback |
| Workable | widget + detail with retries present; shortcode grouping, `<8 req/40 s` cap, `v3` fallback **not seen** | verify then patch |
| Rippling | adapter exists (241 lines) | verify v2 list + v1 detail, slug case |

### D6 — LinkedIn
- **Consequences/acceptance:** a planner unit test proves filter→keyword translation and partitioning without any network; a circuit-breaker test proves a single mocked 429 stops all further LinkedIn requests for the cool-down window; there is no proxy parameter anywhere in the adapter signature.

### D7–D10
See matrix. Acceptance: lock-file install on clean Windows; policy test green; directory snapshot checksum recorded; probe order test.

## 5. Deferred and unresolved decisions

| Item | State | Safe default used by this design |
|---|---|---|
| OT-0 which repository line is "the repository" | unresolved | clean line (doc 01 §1) |
| OT-1 consumer-board compliance posture | **unresolved** | restricted tier, off per provider, no proxies; **local mode only (not offered in hosted mode)** |
| OT-2 D3 method change | needs ack | verify-then-extend |
| OT-5 true language levels | needs owner input | stored as `self_declared`, evaluator reads profile |
| OT-6 UAA hand-off in scope | needs ack | explicit user "ready to apply" action only |
| Research items with **no Decision Log entry**: Bundesagentur, EURES, remote boards (Remotive/Jobicy/Arbeitnow/Rise), sitemap+JSON-LD harvester, `crawlee` fallback, hosted snapshot | **deferred** (not silently committed) | scheduled as optional phases P11–P12 behind the same adapter contract; `crawlee` and the harvester are *not* installed until a source needs them |
| SmartRecruiters, Google Jobs | research says postpone | `disabled_by_policy` |
| Proxy budget | deferred by Conflict 3 | none |
| Stage 3 near-duplicate detection (MinHash/LSH, `datasketch`) | **deferred by owner** (Revision 1) | exact `description_hash` + Stage 2 |
| Source-state promotion rules (multi-day, yield window) | **removed by owner** (Revision 1) | `validating → active` when fixtures are green and one canary run passes |
| OT-18 Public Suffix List dependency | **assumed accepted** (recommended default; confirm) | `tldextract` offline mode |
| OT-19 young-library dependency risk | **assumed accepted** (recommended default; confirm) | pin + hash, contract tests, `third_party/` copy if upstream stalls, tested fallback parsers kept |
