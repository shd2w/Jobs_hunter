# 04 — Data and Integration Design

Status: design document, 2026-11-01. Part of [FINAL_SYSTEM_STRATEGY_AND_DESIGN.md](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md).
Architecture: [03](03_TARGET_ARCHITECTURE.md). Decisions: [02](02_DECISION_TO_ARCHITECTURE_TRACEABILITY.md).

## 1. Storage strategy

**Today:** no database; flat files (doc 01 §3). **Target:** one SQLite database `data/jobhunter.db` (WAL mode, `foreign_keys=ON`, `busy_timeout`), plus files for binary artefacts. SQLite because: local-first, zero services, ships with Python, adequate for ≤ ~10⁶ job rows on a laptop. SQLite is the default for local single-user mode; **hosted multi-user mode (P13+) uses PostgreSQL** (OT-4, doc 08 §7). Application SQL stays portable and migrations are tested on both engines.

Migrations: `PRAGMA user_version` + ordered, idempotent SQL scripts `migrations/NNNN_name.sql`, each run inside a transaction, preceded by an automatic file backup (`data/backups/jobhunter-<utc>-pre-NNNN.db` via the SQLite backup API). Additive only (new tables/columns); no `DROP`/destructive change before a release that has been in use for ≥ 1 version. The pattern is borrowed from the reference rewrite (`store.py`, `migration.py`) but re-implemented.

### 1.1 Source of truth per entity (no entity has two authorities)

| Entity | Authority **after** cutover | Authority **before** cutover | Derived/compat artefact kept |
|---|---|---|---|
| Candidate profile | DB `profile_version` | `config/profile.yml` | `config/profile.yml` regenerated on request (and read on first import only) |
| Secrets, API keys | `.env` (never in DB/logs) | `.env` | — |
| Source definitions | DB `source` (seeded from `portals.yml`) | `config/portals.yml` | `portals.yml` still accepted as an *import*; UI edits write DB |
| Raw + canonical jobs | DB `raw_job`, `job` | `pipeline.md`, `scan-history.tsv`, `jd_cache.json` | `pipeline.md`, `scan-history.tsv` regenerated as exports |
| Evaluations / matches | DB `job_match`, `job_evaluation` | `evaluations.json` | `evaluations.json` regenerated (exact legacy shape, golden-tested) for the queue exporter and any external reader |
| Applications | DB `application`, `application_event` | `app_state.json`, `applications.md` | `applications.md` export |
| Documents | DB `generated_document` + files under `output/` | `output/*`, paths in `evaluations.json` | same paths kept |
| Original CV | file `data/cv/originals/<sha256>.<ext>` (read-only) + DB row | `cv.md` | `cv.md` kept as the *working base CV* (see 3.5) |
| UAA queue | derived: `data/application_queue.jsonl` | same | byte-identical contract (golden tests) |
| Excel DB | derived | `data/jobs_database.xlsx` | regenerated; never read back |

Cutover is per entity and reversible: an importer fills the DB from the files (idempotent, keyed by URL/ids), a verifier compares counts and golden samples, then a flag flips the authority. Files are never deleted by the migration.

## 2. Canonical job model

Decision D2/Conflict 1: the 30-field `ats-scrapers` `Job` is the ingest contract (verified fields): `global_id, url, title, company, ats_type, ats_id, location, country_iso, region, lat, lon, is_remote, salary_currency, salary_period, salary_summary, salary_min, salary_max, experience, employment_type, department, team, requisition_id, apply_url, commitment, description, posted_at, fetched_at, application_deadline, language, raw`.

JobHunter-specific data is **not** added to that model (no fork). It lives beside it:

| Concern | Where |
|---|---|
| Provenance (source, run, matched search term, fetched URL, attribution text) | `job_sighting` |
| Lifecycle (`status`, `first_seen`, `last_seen`, `closed_at`) | `job` |
| Dedup links | `job_link` |
| Evaluation/match | `job_match`, `job_evaluation` |
| Legacy 8-field `JobPosting` | mapped by `legacy_to_job()` (title, url, company, location, date_posted → `posted_at`, source → `ats_type="legacy:<source>"`, description, salary → `salary_summary`); `global_id = "{ats_type}:{sha1(canonical_url)[:16]}"` when the source has no id |

`global_id` rule (from D4): `"{ats_type}:{ats_id}"`; if a source supplies no id, a deterministic hash of the canonical URL — **never a random UUID** (a contract test asserts this).

## 3. Candidate profile

### 3.1 Model

`profile` (one row per user; **`user_id`** is present on every per-user table from the first migration, so hosted multi-user mode needs no destructive change — see §10) → immutable `profile_version` rows. A version holds structured children:

| Table | Key fields |
|---|---|
| `profile_version` | `id`, `user_id`, `profile_id`, `version`, `created_at`, `created_by` (`user`/`import`), `parent_version_id`, `note` |
| `profile_identity` | name, location (city/country), contact fields (never sent to AI) |
| `profile_skill` | `version_id`, `name`, `category`, `level` (`NULL`/`beginner`/`intermediate`/`advanced`/`expert`), `level_source`, `years` (nullable), `evidence_ref` (CV span or project) |
| `profile_language` | `version_id`, `language`, `cefr` (`A1…C2`/`native`/NULL), `level_source`, `certificate` (text, nullable) |
| `profile_experience` | employer, title, start, end, bullets, `source` |
| `profile_education` | institution, degree, field, start, end, grade (text) |
| `profile_preference` | target roles, locations (incl. relocation), remote/hybrid/on-site, employment types, industries, salary expectation (optional), **exclusions** (companies, keywords, industries) |

### 3.2 Proficiency semantics (brief §9.1)

`level_source` ∈ `confirmed` · `self_declared` · `extracted_unconfirmed` · `unknown`. A skill row with `level IS NULL` means "present, level unknown". Absence of a row means "not in profile". The four candidate states plus absence are exactly the table in doc 03 §6. Rules:
1. Only an explicit user action (button "Confirm") sets `confirmed`. No import, migration, AI call, or sync may.
2. CV extraction writes `extracted_unconfirmed` only.
3. Matching and gaps read the state; the UI shows it next to every skill/level that influenced a score.
4. Language levels are **never** inferred from names, locations, or the vacancy's language.

### 3.3 `config/profile.yml` → canonical model

`profile.yml` has no skill levels (doc 01 §4.4); mapping is therefore partial by construction and **invents nothing**:

| `profile.yml` field | Maps to | Level/state |
|---|---|---|
| `candidate.full_name`, `location`, `email`, `phone`, `linkedin`, `github` | `profile_identity` | — |
| `candidate.university`, `degree_current`, `degree_bachelor` | `profile_education` (one row each, deduped by degree) | — |
| `target_roles.primary`, `scope` | `profile_preference.target_roles` | — |
| `preferences.locations`, `language`, `hours_per_week`, `german_required` | `profile_preference` | — |
| `skills.technical[*]` (6 group strings) | one `profile_skill` per recognisable item parsed from the parentheses, **or** one row per group if unparseable; `level=NULL` | `unknown` |
| `skills.non_technical` language item `"Arabic (Native), English (C2), German (C1)"` | `profile_language` rows with `cefr` taken literally | **`self_declared`** (never `confirmed`) |
| `evaluation.*` | `app settings` (thresholds, model lists); `create_cv`, `auto_cv_threshold` deprecated (RC-1) | — |
| `queue_export.output_path` | settings | — |

First import produces a **review screen** (doc 05) listing every mapped field; unreviewed items stay `unknown/self_declared`. The German level conflict (doc 01 §4.4) is shown as a visible warning until the owner sets and confirms it (OT-5).

### 3.4 Authority, sync, conflicts

- **After onboarding the DB is authoritative.** `profile.yml` is read once (import), then only *written* on explicit "Export profile.yml".
- If `profile.yml` changes on disk later, the app detects it by hash at startup and shows a diff with "Import changes / Ignore"; it never merges silently.
- Every UI edit creates a new `profile_version` (history, undo = revert to parent). Matching results store the `profile_version_id` they used; a changed profile marks affected matches `stale` and offers re-scoring (never silent).
- Validation on import/edit: CEFR vocabulary, dates, non-empty roles; contact fields excluded from AI payloads by construction.

### 3.5 CV documents

| Table | Purpose |
|---|---|
| `cv_document` | `id`, `sha256`, `filename`, `mime`, `size`, `stored_path` (read-only file), `uploaded_at`, `kind` (`original`/`working_base`) |
| `cv_extraction` | draft fields with `confidence`, `source_span`, `status` (`draft`/`accepted`/`rejected`/`edited`), `extractor` (`rules`/`llm:<model>`), `consent_id` if an external provider was used |
| `generated_document` | see 3.6 |

Original uploads are stored by hash and **never modified**. The existing `cv.md` is kept as the *working base CV* used by `CVTailor` (first import creates a `cv_document(kind=working_base)` row with its hash; edits create a new row, previous one kept).

### 3.6 Scoring signals and legacy mapping

`match_score` = Σ group weight × group score (group = mean of its *known* signals); unknown signals are dropped from the mean and reduce `confidence`.

| Legacy dimension (weight) | Signals in the group |
|---|---|
| `skills_match` (30) | skill coverage (required 2×, preferred 1×), proficiency fit, experience relevance, industry relevance |
| `education_match` (20) | education requirement vs profile, certification requirement |
| `location` (20) | location/relocation, remote/hybrid/on-site, employment type |
| `language` (20) | required language levels vs `profile_language` (state-aware) |
| `growth` (10) | seniority compatibility (stretch up is positive, > 1 level above is not), role-direction fit to `target_roles` |

Veto: any explicit exclusion → `match_score=0`, reason shown. Cap: a **required** requirement with confirmed absence caps `match_score` at 59 (default, configurable). Weights are stored in settings (one place), editable in UI; the UI's existing five sliders map directly. `confidence` = known-signal weight share × evidence quality (JD completeness, share of requirements with evidence quotes, profile confirmation share), reported as `high ≥ 0.75 / medium ≥ 0.5 / low`. Existing `skip_german` policy outcomes (46 tests) are preserved as a veto rule reading the German policy setting.

### 3.7 Generated documents

`generated_document(id, job_id, kind[cv|cover], version, status[draft|approved|exported|discarded|failed], base_cv_id, profile_version_id, patch_json, md_path, pdf_path, model, requested_by_action NOT NULL, created_at, exported_at, export_path)` with `UNIQUE(job_id, kind, version)`. `requested_by_action` references `audit_event(id)` of type `user.document.request`; the `NOT NULL` + FK is the database-level guarantee that nothing is generated automatically.

## 4. Principal entities (DDL sketch)

```sql
-- sources
CREATE TABLE source(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL,            -- jobspy|ats|workday|feed|import|gov
  provider TEXT NOT NULL, identifier TEXT,            -- e.g. greenhouse / 'acme'
  config_json TEXT NOT NULL DEFAULT '{}',
  access_basis TEXT NOT NULL,                         -- official_api|public_feed|ats_public|consumer_board_guest|user_import
  policy TEXT NOT NULL DEFAULT 'review',              -- allowed|review|disabled_by_policy
  authorized INTEGER NOT NULL DEFAULT 0,              -- owner acknowledgement (SmartRecruiters, consumer boards)
  state TEXT NOT NULL DEFAULT 'proposed',             -- see 5.3
  enabled INTEGER NOT NULL DEFAULT 0,
  rate_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(provider, identifier));
CREATE TABLE source_run(
  id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id),
  started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,   -- ok|partial|failed|blocked|skipped_cooldown
  coverage TEXT NOT NULL DEFAULT 'unknown',                           -- complete|partial|unknown
  fetched INTEGER DEFAULT 0, new_jobs INTEGER DEFAULT 0, updated INTEGER DEFAULT 0, requests INTEGER DEFAULT 0,
  http_status_json TEXT, errors_json TEXT, warnings_json TEXT);
CREATE TABLE source_item_state(                         -- incremental detail fetching (D3)
  source_id TEXT NOT NULL REFERENCES source(id), external_id TEXT NOT NULL,
  summary_hash TEXT NOT NULL, detail_fetched_at TEXT, last_seen_run INTEGER,
  PRIMARY KEY(source_id, external_id));
-- jobs
CREATE TABLE raw_job(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES source_run(id),
  source_id TEXT NOT NULL, external_id TEXT, payload_json TEXT NOT NULL, fetched_at TEXT NOT NULL);
CREATE TABLE job(
  id TEXT PRIMARY KEY,                                  -- = global_id of the canonical record
  global_id TEXT NOT NULL UNIQUE, canonical_url TEXT NOT NULL, title TEXT NOT NULL, company TEXT NOT NULL,
  company_norm TEXT NOT NULL, requisition_id TEXT, location TEXT, country_iso TEXT, is_remote INTEGER,
  employment_type TEXT, salary_min REAL, salary_max REAL, salary_currency TEXT, posted_at TEXT,
  description TEXT, description_hash TEXT, language TEXT, job_json TEXT NOT NULL,  -- full canonical Job
  status TEXT NOT NULL DEFAULT 'new',                   -- new|active|updated|closed|expired
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, closed_at TEXT, miss_count INTEGER NOT NULL DEFAULT 0);
CREATE INDEX job_status_seen ON job(status, last_seen DESC);
CREATE INDEX job_company_req ON job(company_norm, requisition_id);
CREATE INDEX job_desc_hash ON job(description_hash);
CREATE TABLE job_sighting(job_id TEXT NOT NULL REFERENCES job(id), source_id TEXT NOT NULL REFERENCES source(id),
  run_id INTEGER REFERENCES source_run(id), url TEXT NOT NULL, matched_search_term TEXT, attribution TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY(job_id, source_id, url));
CREATE TABLE job_link(a_job_id TEXT NOT NULL REFERENCES job(id), b_job_id TEXT NOT NULL REFERENCES job(id),
  kind TEXT NOT NULL,                                   -- same_posting|possible_duplicate|possible_repost
  stage INTEGER NOT NULL, score REAL, status TEXT NOT NULL DEFAULT 'proposed',  -- proposed|confirmed|rejected
  decided_by TEXT, created_at TEXT NOT NULL, PRIMARY KEY(a_job_id, b_job_id, kind));
-- matching
CREATE TABLE job_match(job_id TEXT NOT NULL REFERENCES job(id), profile_version_id INTEGER NOT NULL,
  match_score REAL, score_1_5 REAL, confidence REAL, signals_json TEXT NOT NULL, missing_critical_json TEXT,
  weights_json TEXT NOT NULL, stale INTEGER NOT NULL DEFAULT 0, computed_at TEXT NOT NULL,
  PRIMARY KEY(job_id, profile_version_id));
CREATE TABLE job_evaluation(id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES job(id),
  status TEXT NOT NULL,                                  -- complete|partial|failed|pending
  requirements_json TEXT, rationale TEXT, recommendation TEXT, model TEXT, prompt_version TEXT,
  ai_call_id INTEGER, failure_reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE skill_gap(job_id TEXT NOT NULL, profile_version_id INTEGER NOT NULL, skill TEXT NOT NULL,
  required INTEGER NOT NULL, state TEXT NOT NULL, needed_level TEXT, PRIMARY KEY(job_id, profile_version_id, skill));
CREATE TABLE learning_reco(id INTEGER PRIMARY KEY, skill TEXT NOT NULL, resource_json TEXT NOT NULL, source TEXT NOT NULL, status TEXT DEFAULT 'suggested');
-- tracking, notifications, audit
CREATE TABLE application(job_id TEXT PRIMARY KEY REFERENCES job(id), status TEXT NOT NULL, updated_at TEXT NOT NULL, note TEXT);
CREATE TABLE application_event(id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES job(id),
  from_status TEXT, to_status TEXT NOT NULL, note TEXT, at TEXT NOT NULL, audit_id INTEGER);
CREATE TABLE notification(id INTEGER PRIMARY KEY, channel TEXT NOT NULL, dedupe_key TEXT NOT NULL UNIQUE,
  event TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER DEFAULT 0, created_at TEXT, sent_at TEXT);
CREATE TABLE ai_call(id INTEGER PRIMARY KEY, task TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, key_alias TEXT,
  status TEXT NOT NULL, error_class TEXT, tokens_in INTEGER, tokens_out INTEGER, latency_ms INTEGER, cache_hit INTEGER DEFAULT 0, at TEXT NOT NULL);
CREATE TABLE ai_key_state(key_alias TEXT PRIMARY KEY, provider TEXT NOT NULL, cooldown_until TEXT, status TEXT NOT NULL);
CREATE TABLE audit_event(id INTEGER PRIMARY KEY, type TEXT NOT NULL, actor TEXT NOT NULL,  -- user|system
  details_json TEXT, at TEXT NOT NULL);
CREATE TABLE saved_search(id INTEGER PRIMARY KEY, name TEXT NOT NULL, filters_json TEXT NOT NULL, created_at TEXT NOT NULL);
```
(Profile and CV tables: section 3.) Foreign-key and unique constraints above carry the integrity rules; `audit_event` rows are append-only.

**Indexing:** by lifecycle/recency, `(company_norm, requisition_id)` for Stage 2, `description_hash` for exact repost lookup; Stage 3 near-duplicate indexing (MinHash/LSH) is **deferred** (doc 08 §4.12); exact `description_hash` is the only text-based lookup. Redis persistence from the research is **not** adopted.
**Retention (defaults, configurable):** `raw_job` payloads 30 days; `closed` jobs 12 months unless saved/applied; `ai_call` 12 months; `audit_event` and application events kept indefinitely; backups: 7 daily + 4 weekly.

## 5. Source adapter contract

```python
class SourceAdapter(Protocol):
    descriptor: SourceDescriptor          # provider, kind, access_basis, default_policy, default_rate, supports_detail, coverage_semantics
    def validate_config(self, cfg: dict) -> list[ConfigIssue]: ...
    async def health_check(self, ctx: RunContext) -> HealthResult: ...      # cheap probe, no bulk fetch
    def plan(self, cfg, checkpoint) -> list[Query]: ...                     # e.g. QueryMatrix partitions
    async def discover(self, ctx: RunContext, query: Query, checkpoint) -> AsyncIterator[RawBatch]: ...
    def normalize(self, raw: RawRecord) -> list[Job]: ...                   # pure, fixture-testable
    def classify(self, exc_or_status) -> ErrorClass: ...                    # rate_limited|blocked|transient|permanent|malformed
    async def close(self) -> None: ...
```
`RunContext` supplies the throttled HTTP client (per-host token bucket, `stamina` retries for transient only, user-agent, timeouts), `source_item_state` access, the logger and the cancellation token. Adapters never sleep, retry or write to the DB themselves.

| Aspect | Rule |
|---|---|
| Pagination/continuation | adapter returns `next_checkpoint`; "more pages exist" is reported only when the provider's response proves it (total/next token). UI never says "more pages" otherwise. |
| Coverage | each batch/run declares `complete|partial|unknown`. Consumer boards = `partial`; ATS list endpoints that return everything = `complete`; Workday = `complete` only if facet subdivision exhausted without hitting a cap. |
| Raw handling | raw payload stored (30-day retention) before normalisation so parsers can be fixed and replayed. |
| Provenance | every `Job` carries source id, run id, fetched URL, attribution, `matched_search_term`. |
| Error classes | `rate_limited`/`blocked` (401/403/429) → circuit breaker opens; `transient` → backoff; `permanent` (404/410 for a board) → `state=degraded`, owner notified; `malformed` → run `partial`/`failed` with sample saved for fixtures. |
| Config validation | slugs match `[A-Za-z0-9_-]{1,80}` (Workday tenants keep case and locale rules); host allow-list per adapter. |

### 5.1 Source registry fields (brief §7.1)

`source` carries identity/metadata, adapter selection (`kind`+`provider`), enable switch, config, auth requirements (none expected; any secret referenced by `.env` key alias), restrictions (`access_basis`, `policy`, `authorized`), rate limits (`rate_json`), and the *derived* health fields from `source_run`: last attempt, last success, last error class, 7-day yield median, freshness (hours since last `complete` run), reliability (success share of last 20 runs).

### 5.2 Controlled expansion process

1 identify → 2 reuse assessment (library/adapter exists?) → 3 access-policy review (record `access_basis`, robots.txt/terms note, `authorized`) → 4 adapter + offline fixtures → 5 isolated validation (`health_check` + one canary query, output not saved) → 6 compatibility tests (normalised `Job` validates; id is deterministic) → 7 integration test through ingest → 8 **shadow** activation (data stored, not shown/notified) → 9 **active** → 10 monitoring, with rollback = set `enabled=0` (jobs keep their provenance; nothing deleted).

### 5.3 Source states

`proposed → validating → shadow → active → degraded → blocked → disabled → retired`. A first successful request only moves `validating → shadow`. **Promotion rule (simplified in Revision 1):** `validating → active` when the adapter's fixtures are green and one canary run passes; the earlier multi-day and yield-window criteria were removed by the owner. `degraded` = yield anomaly or intermittent errors; `blocked` = breaker open (needs cool-down or manual re-enable); `disabled_by_policy` is a policy flag (SmartRecruiters, Google Jobs, cloak-engine adapters) that the UI cannot override without the owner setting `authorized` and acknowledging the stated risk.

## 6. Dedup, identity and lifecycle rules

| Stage | Key | Action |
|---|---|---|
| 1 deterministic | `global_id`; canonical URL (lower-case host, strip `utm_*`, `gh_jid`, `oga`, tracking params, fragments, sort query; via `w3lib`) | merge as `same_posting`; one `job` row, additional `job_sighting` rows |
| 2 requisition/fuzzy | `(company_norm, requisition_id)` exact; else RapidFuzz token-set on title ≥ 92 and location ≥ 85 and same `company_norm` | `same_posting` if req id equal; otherwise `possible_duplicate` (score stored) |
| 3 near-duplicate | **Deferred** (MinHash/LSH and `datasketch` removed — doc 08 §4.12). Interim: identical `description_hash` under different ids → `possible_repost` link | auto-grouped and undoable; **never auto-merged or deleted** |

Canonical record choice: ATS > government portal > feed > consumer board; consumer URLs are kept as secondary sightings. Thresholds start conservative; the "Possible duplicates" queue in the UI lets the owner confirm/reject; rejected pairs are remembered so they are not proposed again. `company_norm`: casefold, strip legal suffixes (GmbH, Inc, Ltd, LLC, …), collapse whitespace.

**Identity separation:** `job.id/global_id` (internal) ≠ UAA `application_id` (sha256 of canonical URL/external id per `queue_exporter.py`). The exporter keeps computing the latter exactly as today; a column map links them. No internal change may alter an existing `application_id` (golden contract).

**Lifecycle:** `new` (first sighting) → `active`; description/title/location hash change → `updated`; a job absent from a run with `coverage=complete` and `status=ok` increments `miss_count`; at 2 → `closed` (`closed_at`); any reappearance → `active`, `miss_count=0`; `expired` = provider says closed/expired or `application_deadline` passed. Runs that are `partial`, `failed`, `blocked`, or from consumer boards never change `miss_count`. Reposts: a reappearing job with a *new* id and similar description gets a `possible_repost` link, status stays independent. **Volume guard (Revision 1):** for a scope with ≥ 5 prior complete runs, a run with `count < 0.5 × median(last 7 complete runs)` (median ≥ 4), or 0 results when the median is > 0, is recorded `partial` with `note=volume_guard`; no `miss_count` changes and nothing closes. A 304 *not modified* response counts all known ids as seen. A URL change never creates a new job for ATS sources (`global_id` is the ATS id). **Recovery (v2, doc 10 F1):** after 3 consecutive flagged runs with `max/min ≤ 1.15` the new level is stored as the scope baseline and closing resumes; a drop of more than 80 % (including zero) needs 8 runs spanning ≥ 24 h, a passing `health_check` and no simultaneous global-breaker trip, so a stable outage is never re-baselined to zero.

## 7. API and module contracts

`Result[T]`: `{status: ok|partial|failed, data: T|null, errors: [{code, message, field?}], warnings: [..]}`; the same object is the CLI `--json` output and the HTTP body. Versioned prefix `/api/v1`; JSON only; errors use the codes (`no_ai`, `source_blocked`, `profile_unconfirmed`, `not_found`, `conflict`, …) so the UI shows specific messages.

Core endpoints: `GET/PUT /profile`, `POST /cv`, `GET/POST /cv/{id}/extraction` (review/accept), `GET /jobs?…`, `GET /jobs/{id}`, `POST /jobs/{id}/documents`, `PUT /documents/{id}` (approve/discard), `POST /documents/{id}/export`, `PUT /applications/{jobId}`, `GET/POST /sources`, `POST /sources/{id}/check`, `POST /runs`, `GET /runs/{id}`, `GET /diagnostics`, `GET/PUT /settings`, `POST /exports/queue`. Mutations require the per-session CSRF token already used by the UI server; server binds to `127.0.0.1` only.

## 8. Existing-to-Target architecture mapping

| Existing component | Current responsibility | Target component | Action | Migration / compatibility notes |
|---|---|---|---|---|
| `run_scan.py` | scan orchestration | `DiscoveryService` + CLI shim | refactor | same flags/exit codes; golden CLI test |
| `scanners/jobspy_scanner.py`, `jobspy_registry.py` | JobSpy searches | `adapters/sources/jobspy` | extend | keep config format; add planner, attrs capture, fix `pages` |
| `scanners/workday.py` | Workday/SR direct | `adapters/sources/workday` (wraps `ats-scrapers`) | replace internals | `tracked_companies` config key kept |
| `scanners/ats.py`, `feeds.py`, `net.py` | extra sources (mocked-tested) | `adapters/sources/{ats,feeds}` | refactor (`ats.py` kept as tested fallback), consolidate feeds | fixtures re-used as parity tests; `net.py` host allow-list kept; SmartRecruiters gated; `ats.py` stays until library adapters pass ≥ 4 weeks of live verification (doc 10 F5) |
| `scanners/bridge.py` | filter+dedup+pipeline.md | `DiscoveryService`/`IngestionService` | refactor | `pipeline.md` becomes export; atomic write |
| `utils/filters.py` | title/location | `app/jobs.py` filters (same code) | preserve | 21 tests unchanged |
| `utils/dedup.py` | URL dedup | `domain/dedup.py` | extend | keep `DeduplicatorStore` interface until callers moved |
| `utils/jd_fetcher.py`, `jd_cache.py` | JD text | `adapters/sources/jd` | preserve | add no-escalation-after-block rule |
| `agents/evaluator.py` | LLM scoring | `EvaluationService` + `domain/scoring` | refactor | stored total ignored; legacy dims as view; prompts read profile |
| `agents/smart_router.py` + clients | AI routing | `adapters/ai` | refactor | rotation kept; taxonomy added |
| `agents/cv_tailor.py`, `cover_letter.py`, `utils/pdf_generator.py` | documents | `adapters/docs` via `DocumentService` | preserve, change trigger | outputs & paths unchanged |
| `utils/evaluation_store.py` | evaluations.json | export writer | preserve | exact shape golden-tested |
| `utils/excel_export.py` | Excel DB | export writer | preserve | derived only |
| `utils/queue_exporter.py` | UAA queue | `ApplicationService.export_queue` | preserve | byte-identical; input from DB view |
| `utils/telegram.py` | Telegram | `adapters/notify/telegram` | extend | no PII in messages |
| `jobhunter_ui/service.py` | file-based UI logic | thin handlers over services | refactor | endpoints grow, old ones kept until UI updated |
| `jobhunter_ui/ranking.py` | UI ranking | `domain/scoring` | consolidate | 7 tests ported |
| `config/profile.yml` | profile + settings | `profile_version` + `settings` | extend | section 3.3 |
| `config/portals.yml` | sources/filters | `source` seed + filters | extend | still accepted as import |
| `run_health.py`, `run_check_sources.py` | diagnostics | `HealthService` | extend | CLI names kept |
| `CV_Example.py` | sample CV | `examples/` | refactor | remove language claims |
| `Dockerfile`, compose | container | unchanged | preserve | low priority |

Unchanged: filters, queue exporter, evaluation-store shape, Excel format, CLI names/flags, `.env` conventions. New: `jobhunter/` package, DB + migrations, registry/health, dedup stage 2 (+ exact-hash linking), lifecycle, profile model, scoring domain, document versioning, notifications service.

## 9. Migration principles and procedure

1. Back up (`data/backups/pre-migration-<utc>.zip` of `data/`, `config/`, `cv.md`, `output/`) before any migration; show its path.
2. Create DB; run importers in order: profile → sources → jobs (from `pipeline.md`, `scan-history.tsv`, `jd_cache.json`) → evaluations (`evaluations.json`; legacy rows keep `score_1_5` and mark `stale=1` for re-scoring under the new scorer) → applications (`app_state.json`, `applications.md`) → documents (paths from evaluations).
3. Verify: per-entity counts, URL set equality, 20-row golden sample, `application_id` equality for every exportable job, queue file **byte-identical** to the pre-migration export.
4. Flip authority per entity (setting `authority.<entity>=db`); legacy files continue to be regenerated as exports.
5. **Rollback:** set the authority back to `file`; the original files were never modified; delete or keep the DB. Schema rollback is not needed because migrations are additive.
6. Existing databases (users of the Excel/JSON era) follow the same path; no destructive step exists; a second run of the importer is a no-op.

## 10. Revision 1 additions (schema, rules, contract)

Authoritative where it differs from §3–§9. Details and rationale: [08](08_REVISION_1_PLATFORM_SCOPE_AND_REVIEW_RESPONSE.md) §4.

**Tenancy.** `user_id TEXT NOT NULL` is added to every per-user table from migration 0001: `profile`, `profile_version` (+ children by FK), `cv_document`, `cv_extraction`, `generated_document`, `job_match`, `job_evaluation`, `skill_gap`, `learning_reco`, `application`, `application_event`, `notification`, `ai_call`, `ai_key_state`, `saved_search`, `job_feedback`, `import_item`, `audit_event`. Local mode uses one fixed `user_id`. Global (shared) tables: `source`, `source_run`, `source_item_state`, `source_http_cache`, `raw_job`, `job`, `job_sighting`, `job_link`, `job_version`, `job_salary`, `job_eligibility`, `company`, `scheduler_lease`. Hosted mode enforces `user_id` in the repository layer (every query takes a user context) and tests isolation.

```sql
ALTER TABLE job ADD COLUMN visibility TEXT NOT NULL DEFAULT 'visible';      -- visible|hidden
ALTER TABLE job ADD COLUMN hidden_reason TEXT;                              -- language|malformed|spam|duplicate_group
ALTER TABLE job ADD COLUMN language TEXT;                                   -- en|de|other|unknown
ALTER TABLE job ADD COLUMN seniority_level TEXT;                            -- student|entry|mid|senior|lead_exec|unknown
ALTER TABLE job ADD COLUMN role_family TEXT;                                -- ISCO-08 major group via ESCO
ALTER TABLE source ADD COLUMN redistribution TEXT NOT NULL DEFAULT 'personal_only'; -- allowed|link_only|personal_only
ALTER TABLE source ADD COLUMN cadence_seconds INTEGER;

CREATE TABLE job_version(job_id TEXT NOT NULL REFERENCES job(id), version INTEGER NOT NULL, content_hash TEXT NOT NULL,
  fields_json TEXT NOT NULL, run_id INTEGER, seen_at TEXT NOT NULL, PRIMARY KEY(job_id, version));
CREATE TABLE job_salary(job_id TEXT PRIMARY KEY REFERENCES job(id), min REAL, max REAL, currency TEXT,
  period TEXT, basis TEXT, tax_note TEXT, raw_text TEXT, origin TEXT NOT NULL, confidence REAL);   -- stored as stated, never scored
CREATE TABLE job_eligibility(job_id TEXT PRIMARY KEY REFERENCES job(id), location_restriction_json TEXT,
  nationality_restriction_json TEXT, work_auth_required TEXT, sponsorship TEXT, relocation_support TEXT,
  work_mode TEXT, onsite_days INTEGER, clearance_required INTEGER, timezone_requirement TEXT,
  evidence_json TEXT NOT NULL, extractor TEXT NOT NULL, extracted_at TEXT NOT NULL);
CREATE TABLE job_eligibility_verdict(user_id TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES job(id), profile_version_id INTEGER NOT NULL,
  status TEXT NOT NULL, reasons_json TEXT NOT NULL, computed_at TEXT NOT NULL, PRIMARY KEY(user_id, job_id, profile_version_id)); -- eligible|blocked|unknown_check
CREATE TABLE profile_work_authorization(version_id INTEGER NOT NULL, country_iso TEXT NOT NULL, status TEXT NOT NULL, valid_until TEXT, source TEXT NOT NULL,
  PRIMARY KEY(version_id, country_iso));
CREATE TABLE profile_nationality(version_id INTEGER NOT NULL, country_iso TEXT NOT NULL, PRIMARY KEY(version_id, country_iso));  -- never sent to AI
CREATE TABLE profile_relocation_plan(version_id INTEGER PRIMARY KEY, willing TEXT NOT NULL, countries_json TEXT, earliest_start TEXT,
  needs_sponsorship INTEGER, needs_relocation_support INTEGER, notes TEXT);
CREATE TABLE profile_remote_constraints(version_id INTEGER PRIMARY KEY, home_country TEXT, tz_min_offset INTEGER, tz_max_offset INTEGER, remote_only INTEGER);
CREATE TABLE company(id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL, aliases_json TEXT, domain TEXT, country_iso TEXT,
  careers_url TEXT, ats_provider TEXT, ats_identifier TEXT, source_id TEXT REFERENCES source(id), status TEXT NOT NULL DEFAULT 'candidate',
  discovered_via TEXT NOT NULL, first_seen TEXT NOT NULL, verified_at TEXT, last_ok_at TEXT, UNIQUE(ats_provider, ats_identifier));
CREATE TABLE job_feedback(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES job(id), event TEXT NOT NULL,
  reason TEXT, at TEXT NOT NULL);
CREATE TABLE import_item(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, raw_ref TEXT, status TEXT NOT NULL,
  job_id TEXT REFERENCES job(id), confidence REAL, created_at TEXT NOT NULL);
CREATE TABLE scheduler_lease(name TEXT PRIMARY KEY, holder TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE source_http_cache(source_id TEXT NOT NULL, url TEXT NOT NULL, etag TEXT, last_modified TEXT, fetched_at TEXT NOT NULL,
  PRIMARY KEY(source_id, url));
```

**Adapter contract changes.** `RawBatch` gains `not_modified: bool` (set on HTTP 304; lifecycle treats all known ids as seen, never as an empty result). `RunContext` sends `If-None-Match`/`If-Modified-Since` from `source_http_cache` where the provider supports them. `SourceDescriptor` gains `redistribution` and `default_cadence_seconds`. Connector rule: **one class per provider, registered in the registry; shared code contains no provider branching** (lint test).

**Imports.** `ImportAdapter` kinds: `paste_text`, `paste_urls`, `eml`, `mbox`, `telegram_forward`, `csv`. Output `Job` rows carry `ats_type="import:<kind>"`, `access_basis=user_import`, `redistribution=personal_only`; in hosted mode they are visible only to the importing `user_id` unless their canonical URL equals a public corpus job.

**Filters.** Ingestion never deletes: global quality rules set `visibility/hidden_reason`; user filters are query-time, per user, token/phrase based, and report "N hidden — why".

**Review defaults.** Extraction fields above the confidence threshold are written as accepted with `level_source=extracted_unconfirmed` and an undo record; `confirmed` still requires an explicit user action (§3.2).

**Cutover.** Unchanged: per-entity and reversible (§1.1, §9; owner choice recorded as OT-16).

## 11. Revision 2–3 additions (schema and contract; authoritative where it differs)

Rationale: [09](09_REVIEW_AND_METHODOLOGY_SPECIFICATION.md) B1–B6, B10, B12; [10](10_METHODOLOGY_FEASIBILITY_REVIEW.md) F1–F4, F8–F11.

```sql
-- discovery funnel (global tables)
CREATE TABLE company_candidate(id INTEGER PRIMARY KEY, kind TEXT NOT NULL,        -- url|domain|name
  value TEXT NOT NULL, channel TEXT NOT NULL,                                     -- C1..C7
  discovered_via TEXT NOT NULL, first_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
  outcome TEXT, ttl_until TEXT, UNIQUE(kind, value, channel));
ALTER TABLE company ADD COLUMN company_type TEXT NOT NULL DEFAULT 'unknown';     -- employer|agency|aggregator|unknown (agency = advisory flag)
ALTER TABLE company ADD COLUMN registrable_domain TEXT;                          -- via tldextract, offline snapshot
ALTER TABLE company ADD COLUMN recognition_status TEXT;                          -- recognized_supported|recognized_blocked_by_policy|recognized_unsupported|unrecognized
ALTER TABLE company ADD COLUMN tier TEXT;                                        -- A|B|C|dormant
ALTER TABLE company ADD COLUMN value_score REAL;
ALTER TABLE company ADD COLUMN language_mix_json TEXT;
ALTER TABLE company ADD COLUMN next_probe_at TEXT;
CREATE TABLE domain_probe(domain TEXT PRIMARY KEY, last_probed_at TEXT NOT NULL, outcome TEXT NOT NULL, ttl_until TEXT NOT NULL); -- careers-page probe results (optional adapter)
-- guard v2 and monitoring
CREATE TABLE source_scope_state(source_id TEXT NOT NULL REFERENCES source(id), scope_key TEXT NOT NULL,
  baseline_count REAL, baseline_updated_at TEXT, flagged_buffer_json TEXT, state TEXT NOT NULL DEFAULT 'normal',
  PRIMARY KEY(source_id, scope_key));                                              -- normal|flagged|frozen
ALTER TABLE source_run ADD COLUMN metrics_json TEXT;                             -- counts, null rates, language mix, status mix, parse failures
ALTER TABLE source_run ADD COLUMN guard_note TEXT;                               -- volume_guard|rebaselined|cycle_breaker
CREATE TABLE cohort_metric(provider TEXT NOT NULL, tier TEXT NOT NULL, day TEXT NOT NULL, jobs INTEGER NOT NULL, boards INTEGER NOT NULL,
  PRIMARY KEY(provider, tier, day));
-- enrichment refinements
ALTER TABLE job ADD COLUMN seniority_hint TEXT;                                  -- title-only guess, low confidence, never hides a job
ALTER TABLE job ADD COLUMN seniority_evidence_json TEXT;
ALTER TABLE job ADD COLUMN language_unknown INTEGER NOT NULL DEFAULT 0;          -- visible only when token count < 40 and no provider language
```
**Rules.** `lead_exec` is stored only with an executive title or a scope cue together with ≥ 8 years; years alone never produce it. `language`: `unknown` with ≥ 40 tokens is stored as `other` and hidden (`hidden_reason=language`). The registry admits at most **20 new boards per day** (setting `onboarding_boards_per_day`) with a first-sync budget per board. `SourceDescriptor` gains the capability flags listed in doc 03 §14. Per-board drift detection runs only when `baseline_count ≥ 20`; `cohort_metric` feeds the provider-level detector.

