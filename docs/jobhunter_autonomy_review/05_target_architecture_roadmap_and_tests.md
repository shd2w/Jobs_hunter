# Part 5 — Target architecture, roadmap and acceptance tests

**Design date:** 2026-10-30 UTC. **Repository:** `shd2w/Jobs_hunter`. **Inspected baseline:** `465f21170ff983bd1507840470103b202d4cf214` (Part 4 report commit). This is a proposal, not implemented functionality. Existing behavior is identified explicitly; all new interfaces, modules, tables, commands, policies and tests below are proposed.

## 1. Recommendation and evidence basis

**Extend the existing local application with a bounded discovery run, not a replacement platform.** Keep JobSpy, the primary Scrapling collectors, native ATS/feed/post adapters, SQLite, existing locks/checkpoints, local matching, and legacy compatibility. Add the missing intent-to-query and discovered-lead-to-supported-source handoffs, then close the coverage/health feedback loop. Do not require cloud hosting, a continuously running scheduler, an LLM, or candidates supplying websites/company lists.

The four previous reports were read and checked against their published bytes before this design:

- [01 — Repository map](https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/docs/jobhunter_autonomy_review/01_repository_map.md): two orchestration paths and existing integration boundaries.
- [02 — Actual execution trace](https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/docs/jobhunter_autonomy_review/02_search_execution_trace.md): actual transforms, static queries, failure/gate behavior and controlled execution.
- [03 — Coverage/manual dependencies](https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/docs/jobhunter_autonomy_review/03_source_coverage_and_manual_dependencies.md): supported kinds, missing categories, M01–M28 and reusable ATS IDs.
- [04 — Scorecard/root causes](https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md): RC1 discovery/onboarding absent; RC2 intent/query/filter disconnect; RC3 missing strategic feedback; RC4 divergent identity/outcome contracts; RC5 limited source lifecycle; RC6 realistic qualification gap.

This recommendation does **not** claim adding a search library makes arbitrary websites collectible. Supported-family recognition can eliminate per-employer hard-coding; a genuinely new protocol may still require a reviewed adapter. Authorization, cost and candidate preferences remain explicit. Historical provider samples and offline tests do not establish current live availability.

### Current interfaces that constrain the design

| Evidence | Existing implementation and consequence |
| --- | --- |
| B1 | `scanners/jobspy_scanner.py:53–117`, `_load_searches/_load_primary`, builds literal YAML terms/locations; `jobhunter_app/expanded_sources.py:23–53`, `collect`, rotates one configured provider/query/page. Generated runtime queries require a new request path, not edits to `portals.yml` per run. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/scanners/jobspy_scanner.py#L53-L117] |
| B2 | `jobhunter_app/sources.py:93–148,255–261`, `Source/register`, can reuse known ATS/feed kinds, but requires their identity first; `source_directory.py` is not a search client. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/jobhunter_app/sources.py#L93-L148] |
| B3 | `jobhunter_app/sources.py:264–354`, `scan/_scan_locked`, owns scan locking, approvals, family gates, source checkpoint, atomic intake/completion. Preserve this contract; do not bypass it with an independent scraper writer. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/jobhunter_app/sources.py#L264-L354] |
| B4 | `jobhunter_app/store.py:20–23,46–65,185–229`, source checkpoints keyed only by source, global canonical jobs/sightings, profile matches and per-source runs. Query-plan progress needs its own scoped identity, not an old source cursor applied to a different query. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/jobhunter_app/store.py#L20-L65] |
| B5 | `scanners/base.py:16–40`, `JobPosting`, and `scanners/jobspy_scanner.py:247–284` preserve the main job URL, not general source-discovery metadata such as a direct employer URL. Preserve observed metadata deliberately; do not assume upstream fields are always supplied. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/scanners/base.py#L16-L40] |
| B6 | `jobhunter_app/scrapling_engine.py:10–47,112–167` fixes two hosts/path schemas; optional `scrapling_parser.py:10–31` changes extraction on already authorized HTML. General site recognition/recipe support is new work. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/jobhunter_app/scrapling_engine.py#L10-L47] |
| B7 | `jobhunter_app/source_health.py:8–60` implements family gates/health/reset; `automatic.py:171–202` orders registered due sources by last run/labels, not yield. Reuse enforcement; add strategy outside it. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/jobhunter_app/source_health.py#L8-L60] |
| B8 | `utils/filters.py:22–56` title gate differs from local matching; `store.py:185–229` canonical identity differs from `utils/dedup.py:101–142` legacy heuristics; `sources.py:356–365` mirror follows SQLite commit. `run_all.py:77–104` gates evaluation on legacy `new_added`. Avoid describing these as one already unified pipeline. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/run_all.py#L77-L104] |

## 2. Target workflow: bounded local discovery on demand

### Invocation and stopping behavior

A proposed `run_local.py discover --profile default` and corresponding **Discover now** local UI action start one finite run. Ordinary runs take stored candidate preferences; optional language/region/budget arguments refine intent, not source lists. Existing `run_scan.py`, `run_all.py --scan-only`, imports, manual source scans and optional automatic server mode remain supported.

The run plans, searches, discovers, collects, commits, matches and reports until its local budget is reached or no eligible action remains. It **does not sleep for hours waiting for cooldowns**. Persist deferred work and `next_allowed_at`; a later manual invocation resumes. Closing the application needs no cloud worker. An optional future schedule calls the same finite runner, not a separate mandatory architecture.

Budget units must be honest: count discovery/native HTTP reads when instrumented, JobSpy provider-search calls separately, elapsed time and returned rows separately. A JobSpy call can make additional vendor-managed requests; do not relabel it one HTTP request or promise an uninstrumented absolute request cap. Stop dispatching at deadline; label in-flight timeout semantics. A strict kill deadline requires a bounded worker process, similar to existing `qa/jobspy_platforms_live.py:46–60`, not an uncancellable thread assumption. [^https://github.com/shd2w/Jobs_hunter/blob/465f21170ff983bd1507840470103b202d4cf214/qa/jobspy_platforms_live.py#L46-L60]

### Twelve-step execution model

| Step | Target behavior | Reuse already available | Must be built / evidence of completion |
| --- | --- | --- | --- |
| 1. Generate strategy from preferences | Build a versioned intent snapshot: role families, supported skills, seniority, explicit exclusions, target regions/languages, remote restrictions and uncertainty. Plan bounded collection and discovery actions. | SQLite profile/matching settings, B1/B4. | Intent-to-retrieval planner; profile provenance; no invented qualifications or eligibility. A profile yields executable tasks, not only prose. |
| 2. Expand title/skill/language queries | Use tested role/skill-to-title mappings, synonyms and locale packs, then bounded variants learned from source-backed retrieved terminology. Format each provider's supported parameters. | JobSpy invocation and country/remote logic, existing matching aliases as input examples only. | Retrieval-specific vocabulary/versioning, locale validation, de-duplication of equivalent queries, fallback for unsupported language. Optional later model suggestions must pass the same validator; no model required. |
| 3. Discover source leads | Extract observed employer/career/apply/feed links from source payloads/permitted detail pages; optionally execute approved web-search API discovery queries. Retain discovery query, parent evidence, URL and time. | Existing board/API collections can supply evidence; directory category taxonomy can suggest scopes. | Executable lead provider and metadata preservation. A URL becomes a **lead**, not an integrated source. No invented URL from a company name. |
| 4. Select collection method | Inspect bounded first-party evidence; recognize supported ATS host/path/token, explicit RSS/Atom, known provider or supported structured HTML. Return binding or reason not collectible. | Existing Greenhouse/Lever/Ashby/SmartRecruiters/Workday/native/feed/JobSpy/Scrapling implementations. | Recognizers, method capability registry, validated runtime binding, inspection budgets. Access/setup requirements surfaced before activation. |
| 5. Evaluate source value | Estimate candidate-scope fit, fresh vacancy evidence, potential distinct employers/opportunities, description usability and expected collection cost. Use a small actual probe when allowed. | Source notices, normalization, local matching, existing counters. | Evidence-backed assessment with confidence/unknowns. Reject non-vacancy pages; do not equate keywords, famous domain or search rank with value. |
| 6. Retrieve/normalize jobs | Dispatch approved due bindings and runtime queries; follow bounded pages/details, validate canonical fields and commit observations/progress atomically. | B3, native collectors, `normalize_job`, post/feed processing. | Request/result envelope and orchestration context; shared intake facade; report attempted versus completed retrieval. Missing description can be retained but flagged not evaluation-ready. |
| 7. Consolidate duplicate opportunities | Keep URL-level source observations; group high-confidence same-opportunity records using first-party posting identity/evidence. Keep ambiguous matches separate or in review. | Canonicalization, sightings, existing reviewed aliases/history. | Reversible opportunity grouping, cross-URL rules, no destructive re-key of existing jobs/applications. Same title/company alone is insufficient. |
| 8. Identify coverage gaps | Compare intended role × locale × region × source-category cells with executed evidence, outcomes and unsearched/blocked scope. | Query/checkpoint/health data and match results. | Coverage analyzer; bounded cell construction, explicit unknowns and partial windows. Zero jobs is a search outcome, not proof coverage is complete. |
| 9. Discover/prioritize further work | Select useful eligible gaps, new supported leads, due refreshes and a bounded exploration allocation. Resolve duplicate publisher families first. | Existing eligibility/gates and fair ordering. | Transparent priority policy; feedback triggers a new action within budget or records the next-run action. Avoid starvation/cold-start suppression. |
| 10. Monitor/degradation | Track transport, schema validity, usable descriptions, freshness, novelty and scope-correct outcomes over comparable observations. | Existing structured failures/health and interrupted-run handling. | Profile-independent transport health versus profile-specific relevance; baseline comparisons and reason-coded degradation. A single empty page is not a broken source. |
| 11. Revisit intelligently | Distinguish zero-yield, invalid-query, transient outage, changed schema, quota/access failure and exhausted scope. Mutate query or schedule due retry according to cause; resume durable progress. | Gates, checkpoints, specific Jobicy cursor restart. | Persisted retry/variant history, cache expiry, policy-respecting recovery and finite stop conditions. No repeated immediate retries or automatic transport bypass. |
| 12. Evaluate/report outcomes | Match retained jobs locally; optionally run configured cloud evaluator later. Report actual searches, lead provenance, binding/probe/collection outcomes, grouped novelty, review and unresolved scope. | `Store.evaluate`, source health, legacy evaluation/export and provenance. | Run-level reconciliation and readable/JSON report. Local lexical match is not legal eligibility, cloud evaluation or human confirmation. |

```text
stored candidate intent -> bounded plan -> runtime queries + discovery actions
  -> observed source leads -> inspect / assess / bind supported family
  -> due authorized collection -> shared validation + durable observations
  -> reversible opportunity grouping -> local evaluation / optional legacy work
  -> gap + health evidence -> bounded next actions OR persisted deferral
  -> reconciled report -> exit local run
```

This is a logical call/data flow, **not a proposal for microservices or many autonomous agents**. Keep one local process/SQLite execution model initially; reuse existing serialization while correctness is established.

## 3. Practical architecture and interfaces

### Component responsibilities

Names in the **proposed module** column are design suggestions, not existing files. They can initially be a few small modules, not separate deployable services.

| Component / proposed module | Responsibility and interface | Reuse / boundary |
| --- | --- | --- |
| Strategy — `jobhunter_app/search_strategy.py` | `build_intent(profile, overrides) -> Intent`; `plan(intent, capabilities, history, budget) -> SearchPlan`. Produce typed query/discovery tasks with reasons and evidence. | Read profile/settings; adapters format provider parameters. Do not use local saved searches as outbound search. |
| Source discovery — `jobhunter_app/source_discovery.py` | `discover(discovery_request, evidence, budget) -> LeadBatch`; providers for observed career/apply/feed links and optional permitted search API. | Preserve raw-source discovery metadata separately from `JobPosting` core fields; no obligation to fetch every link. |
| Capability/recognition — `jobhunter_app/source_capabilities.py` | `recognize(lead, inspection) -> BindingCandidate`; adapter declares supported families, query fields, scopes, prerequisites, pagination/limits and validation probe. | Wrap existing adapter families; code defines a method once, runtime catalog stores per-employer/domain bindings. |
| Catalog — `jobhunter_app/source_catalog.py` | `upsert_lead`, `assess`, `bind`, `activate_if_allowed`; deduplicate normalized source identity; record evidence, access basis and capability version. | Separate **discovered/assessed** metadata from existing `sources` executable registrations/approvals. Never call current `register(..., approved=True)` as a substitute for permission. |
| Runner/ledger — `jobhunter_app/discovery_run.py` | `run_discovery(intent, budget, resume) -> RunReport`; finite queue, ordering, action attempts, cancellation, terminal states and restart. | Invoke the same gated source execution service; optional coordinator/CLI become callers. No continuously running cloud dependency. |
| Adapter execution — existing `sources.py`, `collection.py`, `expanded_sources.py`, scanners | `collect(CollectionRequest) -> CollectionEnvelope`; provider-native request formatting, bounded pages/details, normalized payload/provenance and typed failure. | Extend incrementally behind compatibility wrappers; preserve all existing kinds and source-specific limits. Do not replace JobSpy with generic HTML. |
| Shared ingestion — proposed `jobhunter_app/discovery_ingestion.py` | `commit_observations(envelope, context) -> IngestOutcome`; validate, store sightings/identity evidence/checkpoints/task completion; enqueue idempotent projection work. | Use `normalize_job`/`Store.ingest` and existing source transaction. Do not build a second direct database writer for a new scraper. |
| Opportunity identity — `jobhunter_app/opportunity_identity.py` | `resolve(observations) -> IdentityDecisions`; trusted exact first-party identity, candidate matches, review and reversible grouping. | Preserve URL-keyed jobs and human aliases; group rather than erase histories. |
| Coverage/priority — `jobhunter_app/search_coverage.py` | `analyze(intent, ledger, opportunities) -> Gaps`; `rank(eligible_tasks, gaps, health, history) -> Decisions`. | Eligibility remains authoritative in `source_health`/source execution. Initial policy is deterministic and explainable, not learned optimization. |
| Health — extend `source_health.py` | `observe(attempt, quality) -> HealthUpdate`; distinguish transport/schema/source freshness from candidate relevance. | Keep provider-family gates, Retry-After, pauses and interrupted recovery. No automatic engine-switching around a denied source. |
| Evaluation/report — extend local matching and proposed `discovery_reporting.py` | Evaluate changed/pending local records independently of new-insert count; summarize scope and canonical/grouped outcomes plus failures/deferred/review work. | Legacy cloud path stays optional; reconcile its own population and projection status explicitly. |

### Minimal typed contracts

The following are **proposed logical records**, not a database migration or complete API specification:

```text
Intent:
  profile_id, profile_fingerprint, version, role_families, evidenced_skills,
  seniority, exclusions, languages, regions, remote_scope, uncertainties
QuerySpec:
  query_id, intent_version, role/skill evidence, language, region,
  provider, provider_parameters, generation_rule/version, parent_query, reason
SourceLead:
  lead_id, observed_url, normalized_source_hint, discovered_by,
  parent_attempt/evidence, observed_at, assessment, binding_state
SourceBinding:
  source_id, adapter_family/version, endpoint_identity, publisher_family,
  supported_scope, access/setup_state, validation_evidence
CollectionRequest:
  run_id, task_id, source_id, query_spec?, cursor_scope, checkpoint,
  budget_allocation, cancellation
CollectionEnvelope:
  observations/posts, discovered_leads, next_checkpoint,
  source/query provenance, observed_bounds, request_units, warnings/failure
IngestOutcome:
  accepted/invalid observations, canonical jobs inserted/updated,
  opportunity groups new/existing/uncertain, pending evaluation/projection
RunReport:
  attempted/completed/deferred/failed tasks, queries, source leads/bindings,
  actual retrieval/intake outcomes, opportunity novelty, health, gaps, limits
```

**Compatibility detail:** keep old `fetch(source, checkpoint, cancel_event)` and scanner `scan() -> ScanResult` call shapes through wrappers until migrated. Proposed explicit-query execution must reuse `JobSpyScanner._run_search` functionality without changing the global YAML registry or converting each query into a fresh provider registration to evade cooldowns. `JobPosting.to_dict()` currently drops non-core metadata (B5); add a compatible envelope/sidecar rather than silently discard discovery evidence.

### Persistence: add only what current tables cannot represent

Use additive, backed-up schema migrations in the existing local store; do not re-platform persistence. Proposed logical additions:

- **Search run and task records:** run/profile/intent version, budgets, query signature, attempt outcome, timestamps, checkpoint reference and completion/projection/evaluation states. Link existing per-source `runs` where applicable rather than duplicating unexplained totals.
- **Source leads/catalog bindings:** source identity, parent discovery evidence, method/version, assessment/permission/setup state and refreshed observations. Existing `sources` remains executable registration; existing `provider_gates` remains the provider gate authority.
- **Scoped task progress:** `(profile_id, intent_version, source_id, query_signature, adapter_version)` for query-dependent cursors; source-wide feeds/ATS snapshots can retain shared checkpoint scope. Do not apply a query index/page from one reordered/changed plan to another. Resume stable task identities; reuse completed tasks only if semantic request signature, freshness and version are compatible.
- **Opportunity grouping/identity evidence:** grouping membership and reversible decisions across existing job IDs, plus first-party external identity/URL evidence. Keep reviewed `job_aliases` authoritative; do not silently label automatic decisions human-confirmed.
- **Idempotent projection work:** when required, a small SQLite outbox for legacy mirror/evaluation/report projections, committed with observations and retried locally next invocation. Preserve post-commit failure truthfulness, not a fake cross-store transaction.

A profile change creates a new intent version, not a destructive source reset. Query semantic signature and freshness decide which compatible prior tasks can be reused; changed intent invalidates relevance judgments while transport checkpoints may remain valid only when their request scope truly matches. Approval/cooldown is source/provider scoped, never per generated query/profile as a bypass. Existing jobs/application state, backups, CVs and legacy files remain intact.

## 4. Discovery and integration without per-website hard-coding

### First practical discovery channels

1. **Harvest observed employer/direct-apply/career/feed evidence from existing supported collections.** Preserve optional direct URLs/metadata when providers expose them and bounded permitted detail-page links when inspected. Today the wrapper retains only main job fields (B5); this preservation and lead extraction must be built. Do not assume every provider returns a direct employer link or derive domains by guessing company names.
2. **Recognize families once, bind employers at runtime.** Versioned recognizers extract Greenhouse board tokens, Lever/Ashby board names, SmartRecruiters account IDs, or supported Workday tenant/board shapes from observed first-party evidence. Validate through the existing family's bounded public endpoint. A new employer is a catalog record, not a new branch in core Python or a YAML edit.
3. **Discover explicit feed links and validate feed contents.** Resolve permitted first-party RSS/Atom announcements; use existing feed parser and triage. A feed with ambiguous prose is not necessarily an automatically collectible job board.
4. **Add one optional executable web-search lead provider after selecting a permitted, locally usable API/contract.** Queries derive from intent/category/locale; response URLs enter the same catalog/recognition path. One-time operator access/credential/cost setup is acceptable; manually supplying URLs each search is not. The application's runtime cannot assume Notion AI chat search tools are available. A provider recommendation or Google browser link is not an implementation.

**MVP boundary:** channels 1–3 can discover new supported employer sources when actual observed links exist. They do not guarantee open-web breadth. If the current provider exposes no usable leads and the optional search provider is unavailable, report that discovery channel as limited/unavailable; do not mark unknown-source acceptance passed. A real held-out-source trial decides whether this channel delivers useful expansion.

### Method-selection ladder

| Observed evidence | Proposed method decision | Activation / fallback rule |
| --- | --- | --- |
| Supported ATS identifier verified from career/apply evidence | Existing native public ATS adapter; Workday uses supported configured shape | Bind runtime record and probe, then activate only within applicable access policy. Unknown host/protocol is not guessed into an endpoint. |
| Recognized supported board query/source | Existing JobSpy/native/fixed HTML route | Preserve provider scope and readiness; engine existence is not proof of current access. |
| Explicit permitted public RSS/Atom link with valid payload | Existing generic/source-specific feed collector | Probe actual entries; require source evidence and use review where completeness is absent. |
| Already supported authorized Wuzzuf/Naukrigulf listing | Existing bounded HTTP/explicit browser transport and optional parser | Carry required authorization/setup; no silent browser switch around failure. |
| Unknown publisher with public structured JobPosting HTML | **Later**, bounded generic JSON-LD recipe collector using Scrapling parsing/transport where appropriate | Needs new reviewed generic method, source binding and probe. No arbitrary code generation; do not remove fixed-host restrictions from existing primary collectors. |
| Authorized social scope with actual API rights | Existing official scoped adapter | Needs exact verified scope/setup; no platform-wide search inferred from timeline support. |
| Login/challenge, denied access, unsupported API/layout, unrecognized content | `needs_access`, `unsupported_method`, `schema_failed`, or `needs_review` | Record evidence and continue other work. Optional adapter backlog; do not fabricate listings or activate an unverified method. |

A declarative binding describes **where to apply reviewed code**, not arbitrary executable extraction instructions. Generalizing a method per family is practical; universal autonomous adapter creation is not an MVP prerequisite and is not promised.

### Source usefulness, opportunity identity and coverage

**Usefulness assessment:** before collection, record role/locale/category evidence, supported method, access readiness and uncertain prior value. A bounded permitted probe produces observed valid vacancy records, description readiness, freshness evidence, candidate relevance signal and new/existing/uncertain opportunity groups. Unknown age/location remains unknown. Low relevance for one profile is not source transport failure. A lead with no complete vacancy in the probe can be low-evidence/deferred, not automatically declared a permanently useless site.

**Identity:** retain every source-backed URL observation. Exact canonical employer posting URL or verified `(first_party_employer, ATS_family, posting_id)` is strong identity evidence. Provider-local IDs from different boards are not interchangeable. Similar company/title/description/location suggests a candidate match, not automatic same opportunity; distinguish separate requisitions, cities, contracts and reposts. Initially auto-group only high-confidence cases; human review handles ambiguity. Preserve conflicting facts and source freshness. User-facing grouped novelty and raw canonical insert counts must be separate. Do not delete/re-key job/application/history rows just to improve a dedup metric.

**Coverage:** represent only relevant requested role/locale/region/category cells and observed evidence—avoid a Cartesian explosion of every country/title/site. States include not planned, planned, attempted, partial, usable records, empty, blocked, unsupported and deferred. A current feed snapshot or all configured queries exhausted is not global coverage. Missing source-category coverage can trigger another discovery query; repeated valid emptiness can trigger a bounded synonym/location variant without changing explicit hard preferences.

**Prioritization:** gate eligibility first; then transparent tiers for due incomplete work, high-evidence relevant probes, fresh likely useful sources and a reserved bounded exploration share. Compare observed new opportunity groups and usable descriptions per measured collection cost, with uncertainty and cold-start handling. Do not suppress new sources because they have zero history. Preserve fairness and publisher-family quotas; log chosen/skipped reasons. No ML optimizer is needed initially.

**Degradation/revisits:** compare like-for-like query/scope windows using versioned quality thresholds. Transport/schema failures get immediate reason codes; valid empty responses need repeated comparable evidence or explicit source evidence before a degradation warning. Cache completed queries/leads; refresh when due, source changed, profile/locale request changed or a bounded variation has a justified reason. Respect Retry-After/reapproval; changed schema may need a developer, not a different transport. Never infer vacancy closure from absence.

## 5. Prioritized roadmap

Effort is relative **S** (localized change), **M** (several interfaces/tests), **L** (cross-pipeline behavior/migration), **XL** (new general collection capability with external qualification). These are planning judgments, not time/cost estimates. Expected unique-job gains are hypotheses until acceptance/replay/live evidence exists. A01–A14 refer to Section 6; all are **proposed**, not passed.

### Foundation: truthful execution and reusable runtime queries

| ID / priority | Limitation / root cause | Proposed implementation and relevant files | Dependencies / effort / autonomy impact | Objective acceptance and verification |
| --- | --- | --- | --- | --- |
| **R01 / P0** Run contracts and honest reporting | Scanner-wide error can disappear from CLI summary; no run-level query/discovery/outcome reconciliation. RC4/RC6. | Add finite run/task ledger, typed outcomes, reconciled JSON/local report and failure status rules. Extend `run_scan.py`, `scanners/base.py`, `sources.py`, `store.py`; proposed `discovery_run.py`, `discovery_reporting.py`. Keep normal per-query isolation. | No new discovery required; **M–L**. Trustworthy execution evidence before optimizing counts. | A08/A14: injected scanner-wide failure is failed/partial, never error-free success; every planned task terminal/deferred, counts reconcile. Mocked + controlled integration, then real representative report. |
| **R02 / P0** Runtime requests, cursor identity and additive persistence | Queries tied to global YAML/index; source-only checkpoint cannot safely distinguish generated requests. RC2/RC4. | Request/envelope wrappers, scoped task signatures/checkpoints, safe migration/backups; pass runtime `QuerySpec` into JobSpy/native execution through existing gated transaction. `expanded_sources.py`, `sources.py`, `store.py`, `scanners/jobspy_scanner.py`; proposed runner/intake modules. | R01; **L**. Enables ordinary profile searches without config edits, correct repeat/resume. | A01/A12/A13 plus migration tests: changed/reordered queries cannot consume wrong cursor; same request resumes; gates/old entry points/previous data preserved. Controlled crash/restart and byte-diff checks. |
| **R03 / P1** Evidence-grounded strategy and language packs | Static terms, profile skills not converted to retrieval; lexical gate loses unfamiliar titles. RC2. | Deterministic intent/role/skill mappings, tested locale packs, bounded variants, provider-aware formatting; separate hard exclusions from reviewable unknown titles/description relevance. `store.py`, `match_config.py`, `utils/filters.py`, `jobspy_scanner.py`; proposed `search_strategy.py` and retrieval vocabulary data. | R02; **M–L**. Reaches useful new terminology on existing sources; no cloud model dependency. | A01/A02/A11/A13: skill/role profile produces expected positive and excluded queries in supported locales; variants actually dispatched; no fabricated qualifications/YAML edits. Mocked vocabulary + controlled query capture + real searches. |
| **R04 / P1** Executable lead discovery and family recognition | Directory links and discarded discovery metadata; no held-out source finding. RC1. | Preserve observed direct/career/feed metadata in envelope; collect leads and recognize existing ATS/feed families with provenance and bounded inspection. `scanners/base.py`, `jobspy_scanner.py`, `expanded_sources.py`, `collection.py`; proposed `source_discovery.py`, `source_capabilities.py`. | R01–R03; **L**. New supported employer/source can be found without candidate URLs, when lead evidence exists. | A03: held-out URL absent from seed/config is produced by executed discovery, recognized from evidence, not passed by user/fixture-specific production code. Mocked provider, controlled HTTP discovery, and required real discovery trial. |
| **R05 / P1** Catalog, probe, usefulness and supported-family onboarding | Known ID reuse is manual; recommendation not actual collection. RC1/RC5. | Lead/assessment/binding state machine, endpoint validation, small real probe, source-policy-aware activation and subsequent bounded collection. Reuse `sources.register/fetch`, `collection.py`, `feeds.py`, `source_health.py`; proposed `source_catalog.py`. Add Workday binding wrapper without requiring per-run YAML edits. | R02/R04; **L**. Converts discovered supported leads into observed jobs; preserves legitimate access setup. | A04–A06/A13: relevant supported lead yields actual requests + canonical DB rows; irrelevant/unsupported/blocked leads get truthful reasons. No approval bypass. Controlled integration and real held-out-source receipts. |
| **R06 / P1** Shared intake and reversible cross-URL identity | Canonical URLs/legacy heuristics do not establish unique opportunities. RC4. | Single intake facade and opportunity-group evidence/membership; trusted first-party identity auto-group, ambiguity review; preserve aliases/applications/history. `store.py`, `validation.py`, `posts.py`, `scanners/bridge.py`, `compat.py`; proposed `discovery_ingestion.py`, `opportunity_identity.py`. | R01/R02; can run parallel to R04; **L**. Less duplicate effort and honest novelty signal, not automatically more external reach. | A06/A07/A12: two syndicated URLs one evidenced opportunity, distinct requisitions remain distinct; same fixtures idempotent; rollback and prior state preserved. Labeled controlled integration; live samples manually adjudicated. |
| **R07 / P1** Evaluation/projection completion independent of new insert count | New legacy additions gate pending evaluation/export; cross-store projection best-effort. RC4. | Select pending/changed local match/evaluation work by ledger, not `new_added`; idempotent projection/outbox reconciliation. Preserve cloud/legacy modes and distinguish returned failure from exception. `run_all.py`, `run_evaluate.py`, `sources.py`, `scanners/compat.py`, `store.py`, proposed reporting/intake. | R01/R02/R06; **M–L**. Retrieved opportunities reach intended pipeline stages truthfully without manual re-run tricks. | A06/A12/A14 plus regression: zero new inserts with pending changed work still processes appropriate work; failed projection stays pending and reported; no false cloud-success claim. Controlled failure/restart tests. |

### Feedback and broader discovery: after the foundation

| ID / priority | Limitation / root cause | Proposed implementation and relevant files | Dependencies / effort / autonomy impact | Objective acceptance and verification |
| --- | --- | --- | --- | --- |
| **R08 / P2** Coverage analysis and explainable priority | No strategic gap detection or yield-responsive allocation. RC3. | Intended-versus-observed cells, actionable gaps, deduplicated query/source history, cold-start exploration and deterministic ranking. Extend `automatic.py`, `source_health.py`; proposed `search_coverage.py`, strategy/ledger/catalog. | R03/R05/R06/R07; **L**. Further searches target justified scope, not repeated static rotation. | A04/A10/A12: a known fixture gap produces a new eligible task/reason, yields affect choices but quotas/fairness survive. Replay equal-budget baseline before claiming coverage gain; real-run gap report. |
| **R09 / P2** Quality monitoring and cause-specific revisits | Health lacks comparable quality history; routine/manual recovery uneven. RC5/RC3. | Versioned transport/schema/description/freshness/relevance observations, degradation thresholds, bounded query mutation versus permitted due retry versus review. `source_health.py`, `sources.py`, `automatic.py`, ledger/reporting. | R01/R02/R08; **M–L**. Routine recovery/deferred work managed locally, no cloud daemon. | A08/A09/A12/A14: empty page not immediate breakage; repeated invalid schema detected; one source failure does not stop others; second local invocation resumes due work without gate reset. Controlled clock/restart tests, then repeat live observation. |
| **R10 / P2** Broader executable search-lead provider | Payload-link discovery may expose few/no useful new sources. RC1. | Implement one permitted search API provider behind `discover` contract; intent/category/locale queries; bounded result inspection; documented optional local auth/quota/cost setup. Proposed `source_discovery.py` provider module, capabilities/catalog; do not treat chat web tools as app runtime. | R04/R05; actual provider feasibility/access first; **M–L**, external constraint. Extends reach beyond links on current collectors. | A03–A05/A10/A11: executable query response discovers held-out supported site, validates and retrieves, not merely suggests it. If unavailable, mark unavailable/deferred; mocked tests do not pass real discovery gate. |
| **R11 / P2** Representative qualification and useful-coverage measurement | Fixture totals/historical samples insufficient for operational autonomy. RC6. | Add replay/controlled suites and opt-in real end-to-end harness with evidence manifest; compare stable budget/intent baseline; adjudicate grouped novelty/false merges and suitability. Extend `qa/`, `tests/`; proposed `qa/autonomy_discovery_live.py` and test fixtures. | Starts baseline work with R01; release gate after relevant implementation; **M–L**. Determines real value and next score, not an invented percentage. | All A01–A14 at required layers; real end-to-end receipts for new query → held-out source → persisted evaluated/grouped outcome; failures and unavailable setup disclosed. No operational-autonomy claim from fixture pass. |

### Advanced autonomous integration: optional, not first-release blockers

| ID / priority | Limitation / root cause | Proposed implementation and relevant files | Dependencies / effort / autonomy impact | Objective acceptance and verification |
| --- | --- | --- | --- | --- |
| **R12 / P3** General structured-HTML recipe and further methods | New non-ATS/non-feed sites need bespoke code; fixed Scrapling scopes intentionally narrow. RC1/RC5. | Separate reviewed generic JSON-LD collector with declarative runtime source binding, bounded listing/detail rules, schema/continuation tests and safe unsupported outcome. Reuse `scrapling_transport.py`, parser concepts; add a new family instead of broadening existing fixed collectors silently. Optional model-assisted assessment only after deterministic path proven. | R04–R06/R09/R11; **XL**. New domains under a reusable proven method, not arbitrary code generation or guaranteed universal scraping. | Extend A03–A09 to held-out structured publishers with real collection + schema-change cases; no source-specific production fixture map. Unsupported/challenged sites stop honestly. Specialized ATS/social/agency methods still need their own access/adapter validation. |

**Release order:** foundation through R07 establishes a practical supported-source-discovery vertical slice; R08–R11 improve feedback/reach and qualify value. R12 is optional advanced expansion, not a reason to postpone supported ATS reuse. Do not replace existing engines or delete workflows to make a new demo pass.

## 6. Concrete acceptance tests

### Levels and shared evidence rules

- **M — mocked/unit contract:** fake discovery/provider responses and fake clock where needed. Tests logic, not network/schema/live availability.
- **CI — controlled integration:** real proposed runner, recognizer, adapter, parsing, gates, SQLite/intake/matching/reporting against deterministic HTTP fixtures or captured permitted responses. Only network/auth/optional model boundaries replaced. Loopback fixtures use an explicit test transport; never relax production public-host rules just for tests.
- **R — real end-to-end:** actual local invocation, real permitted discovery/collection and persisted outcomes, with no injected lead/result/job payload. Required for real discovery/retrieval/autonomy claims. Historical samples are not current R passes.

For every pass, preserve: code/version, profile/intent fingerprint, starting registry/catalog and request-cache state, budgets, invocation/config hashes, query/task/source IDs, network/transport boundary manifest, response/request evidence, state before/after and reconciled report. Use synthetic profiles; retain sanitized response snapshots/hashes and human-adjudication notes where permitted, not credentials/private content. A response hash alone proves neither content nor source identity: include inspectable permitted evidence/field excerpts and real request destination/time/status. All tests below are **specified, not implemented/executed in Part 5**.

A real blocked/unavailable source can verify honest failure handling, but does **not** pass a test that requires discovering and collecting a valid vacancy. Record `blocked`, `failed`, `not run` or `not applicable with reason`; never turn a lack of real evidence into a pass.

### A01 — Profile, no manually supplied source URLs

- **Preconditions:** synthetic profile with role intent/skills, target language/region; only baseline source capabilities/seeds, no user URLs/company list/exact queries; optional provider access set once if used.
- **Action:** one local **Discover now** / proposed CLI invocation; no daemon/cloud worker or file edits.
- **Expected:** executable derived queries, bounded collection and usable canonical jobs on the deterministic fixture path; local match/evaluation-readiness recorded; gaps/failures explicit. Real run must show actual returned records, not recommendations.
- **Pass evidence:** input/registry/config snapshots, generated/dispatched task trace, HTTP/collection receipts, committed jobs/matches and run report. **M + CI + R**; R proves realistic no-URL flow only for tested scope.

### A02 — Useful queries without every title entered

- **Preconditions:** profile lists Python/SQL and backend-role intent, but no exact “Python Developer” or “Backend Engineer” query list; tested vocabulary pack and negative seniority examples.
- **Action:** plan then execute bounded queries on two fixture providers.
- **Expected:** at least those two relevant positive variants generated with skill/intent provenance and dispatched; excluded senior roles not synthesized as positive intent. A labeled held-out fixture role is retrieved/retained, not just printed in a plan. Human-rated live relevance separate from lexical match.
- **Pass evidence:** expected mapping assertions, actual captured provider parameters, origin rule/version, negative cases and returned record linkage. **M + CI; R** for claims of useful real retrieval.

### A03 — Source absent from initial configuration

- **Preconditions:** held-out source identity/domain absent from seed/config/catalog; discovery fixture/API/actual source payload contains evidence but application code has no special case for that employer. Candidate supplies no URL.
- **Action:** execute lead discovery, inspect evidence, recognize supported ATS/feed and create catalog lead/binding.
- **Expected:** new validated source identity, parent query/observation and method reason. A new vacancy URL alone or a hard-coded test-domain lookup is insufficient.
- **Pass evidence:** starting-registry absence, real discovery-call trace, original lead evidence, recognizer output and new catalog row; code/config review excludes per-employer cheating. **M + CI + R**; R lead must arise from actual provider response, not operator injection.

### A04 — Evaluate source usefulness

- **Preconditions:** relevant supported vacancy lead, irrelevant/non-hiring page, unknown low-evidence lead and access-blocked lead; finite probe budget.
- **Action:** assess and probe only allowed relevant/uncertain candidates.
- **Expected:** evidence-backed fit/value states; relevant probe receives valid vacancy records and can progress; irrelevant not queued as a job source, uncertainty not fabricated, blocked access not classified successful. Priority changes explainable and does not starve new sources.
- **Pass evidence:** assessment inputs/reasons, probe requests/content, quality/relevance evidence, chosen/deferred decisions. **M + CI; R** for actual source-value claims. Search snippets alone do not establish value.

### A05 — Attempt actual collection, not website recommendation

- **Preconditions:** A03 supported binding validated; access/setup and cooldown permit a small collection.
- **Action:** execute adapter listing/detail requests through gated collection.
- **Expected:** inspectable real/fixture vacancy payload, normalized accepted record and terminal collection outcome. A source marked integrated only after a link/recommendation fails this test; zero/blocked results do not pass the positive retrieval case.
- **Pass evidence:** destination/method/time/status, returned vacancy evidence, parser output, task/source IDs and intake linkage. **CI + mandatory R** for live collection claim; M only tests request dispatch.

### A06 — Normalize into the existing pipeline

- **Preconditions:** A05 rows with valid, malformed and description-incomplete cases; local profile; legacy compatibility enabled in one variant; transaction/projection fault injector.
- **Action:** shared intake, local evaluation, requested legacy projection; repeat after induced write/projection failure.
- **Expected:** valid rows canonical in SQLite/sightings; invalid reason counted; description readiness distinct from validity; eligible legacy view uses existing acceptance policy and reports rejections. Atomic checkpoint/completion rollback on DB failure; post-commit projection pending/retry truthful. No new-insert-only gate for pending evaluation.
- **Pass evidence:** DB/match/projection state, checkpoint before/after, rollback assertions and report reconciliation; existing application/history fixtures unchanged. **CI + R** for real collected-to-persisted outcome.

### A07 — Same opportunity across different sources

- **Preconditions:** two source URLs with verified same first-party employer posting identity, plus same-title/company jobs with distinct requisitions/locations; existing application and reviewed alias fixtures.
- **Action:** ingest and resolve identity; repeat in reverse order and replay.
- **Expected:** one high-confidence opportunity group for the true pair, both observations/provenance retained; distinct jobs not merged; ambiguity review; application/history/reviewed aliases unchanged. No false novelty on repeat.
- **Pass evidence:** labeled ground truth, decisions/reasons/member URLs, counts for records versus groups, negative controls, state diffs. **M + CI; adjudicated R** samples before real unique-opportunity performance claims.

### A08 — One source fails, others continue

- **Preconditions:** three eligible sources; one transport/schema/provider failure or timeout, two valid responses; repeat with 429/access-denied and scanner-wide exception variants.
- **Action:** run finite discovery/collection.
- **Expected:** successful sources commit; failure has typed terminal status; no phantom jobs or successful-empty substitution; cooldown/Retry-After enforced; denied source not retried via another engine. Session partial/failed according to actual outcomes, never silent exit-0 success for a fatal all-source failure.
- **Pass evidence:** request order/statuses, persisted source/task health, successful rows, failed checkpoint unchanged, CLI/UI/JSON agreement. **M + CI; R** verifies real mixed outcomes when encountered or in an opt-in permitted fault harness (fault itself disclosed).

### A09 — Detect degradation, not ordinary zero results

- **Preconditions:** comparable source/query baseline; fixture responses shift from valid complete listings to malformed schema or unusable text; separate legitimate-empty and changed-query controls. Test policy explicitly defines repeated quality threshold, e.g. two comparable invalid-schema observations.
- **Action:** two due invocations with controlled clock, then healthy recovery response.
- **Expected:** immediate schema errors, repeated degradation flagged with evidence; one valid empty page not called broken; low candidate relevance not transport failure. Recovery clears only appropriate health state after verified success.
- **Pass evidence:** comparable scope signatures, response samples, quality history, threshold/version and report transition; gates retained. **M + CI; repeated R** observations required for real degradation claim.

### A10 — Coverage gap selects further work

- **Preconditions:** intent includes a supported role/locale/category cell not searched; another cell overrepresented; available relevant lead/query; tight budget and controlled outcome history.
- **Action:** analyze coverage, rank and dispatch one justified additional eligible task.
- **Expected:** named gap and evidence, appropriate new query/source chosen rather than repeating covered work; cold-start exploration and gates preserved. Blocked/unsupported scope stays explicit; no claim of global completeness.
- **Pass evidence:** intended/observed coverage snapshots, selected/skipped reasons, actual task result and updated scope. **M + CI + R** for real adaptive-discovery qualification; replay equal-budget baseline for gain claims.

### A11 — Configured languages and regions

- **Preconditions:** tested English/German/Arabic retrieval packs, explicit target regions/provider capability; negative citizenship/remote assumptions; unsupported-language control.
- **Action:** generate and execute localized variants through supported providers.
- **Expected:** pack-defined examples such as Software Engineer / Softwareentwickler / مهندس برمجيات preserve intent and correct locale parameters; unsupported language reported rather than invented; unfamiliar relevant titles not lost by old positive-only gate. Remote not changed into worldwide eligibility.
- **Pass evidence:** exact text/parameters/pack version, translated/region labeled fixtures, retrieved/matched records, negative controls and explicit unsupported states. **M + CI; R** for each claimed real language/region, not one multilingual string assertion.

### A12 — Avoid unnecessary repetition over successive local runs

- **Preconditions:** fixed clock, two runs with same intent, completed cached requests and one interrupted task; then expiry, profile-change and adapter-version-change variants.
- **Action:** exit/restart application; resume within freshness period and after due time.
- **Expected:** no duplicate fresh completed query/probe or false new opportunity; interrupted work resumes committed scope; necessary due refresh happens; changed query cannot inherit wrong cursor. Compatible unchanged request may reuse cache; changed intent re-evaluates relevance. No sleeping daemon or quota reset.
- **Pass evidence:** request-count assertions by unit, stable semantic signatures/cursors, timestamps, new/existing/group counts and crash/restart logs. **M + CI; repeated R** runs to qualify actual behavior.

### A13 — No configuration-file edits for ordinary searches

- **Preconditions:** installed app with required optional access already set; record hashes/permissions for `config/portals.yml`, source code, seed definitions and dependency files; profile A then profile B and a newly recognized supported employer.
- **Action:** use local UI/CLI stored preferences, discover/bind/collect supported source and resume; make config files read-only in controlled variant.
- **Expected:** ordinary intent/queries/catalog/progress stored in SQLite, no edits to YAML/code/dependencies or per-employer hard-coded list. Missing one-time access clearly requested, not silently fabricated. Unsupported new protocols may require future adapter work and are not misclassified ordinary supported onboarding.
- **Pass evidence:** before/after hashes, local request trace, persisted runtime plan/binding and successful intake; original data preserved. **CI + R**, plus negative unsupported-source case.

### A14 — Honest results, failures and remaining limitations

- **Preconditions:** mixed discovered leads, unbound/blocked/rejected sources, duplicate observations, invalid records, successful collections, pending evaluation/projection and budget-deferred tasks.
- **Action:** produce JSON and human-readable report at normal exit, cancellation and restart recovery.
- **Expected:** distinct lists/counts for discovered, recognized, bound/activated, attempted, successfully collected and failed/deferred sources; queries and bounds shown. Canonical records versus opportunity groups versus locally relevant/reviewed outcomes separated. No fake success, fabricated role or global-coverage claim; optional cloud evaluation not claimed if unused.
- **Pass evidence:** ledger-to-report reconciliation, exhaustive task/source ID linkage, paired success/failure/cancel assertions, config/evidence manifest and real persisted rows. **M + CI + R**. Report totals must derive from ledger, not unverified display labels.

## 7. Release gates and measuring actual unique-job coverage

### Minimal useful release, before advanced HTML integration

Do not declare the vertical slice complete until A01–A08 and A11–A14 pass M/CI where applicable, plus a real local run that demonstrates **profile-derived query → previously unregistered supported source discovered through actual evidence → actual permitted retrieval → normalized durable rows → identity/evaluation/report outcome**, without user URLs or config edits. A09/A10 require controlled proof before feedback is enabled by default; repeated real qualification follows. A real trial blocked by access is a failed/blocked qualification, not permission to claim success from mocks.

A source discovered but not collectible is still a useful lead outcome, **not** a successful integration or positive A05 pass. A zero-result run may be honestly completed within its plan but does not prove positive retrieval. “Run complete” means its bounded tasks accounted for, not that the job market is exhausted.

### Outcome measurement instead of adapter counts

- Establish a reproducible baseline using the same synthetic intent, declared source/query budget units, starting store and time window. Replay the same permitted captured responses for causal comparisons; live services change and cannot be treated as identical experimental inputs.
- Measure new **adjudicated/high-confidence opportunity groups**, not merely canonical URL inserts. Also report uncertain groups, false merges/missed merges on labeled samples, duplicate observations, description readiness, locally relevant outcomes, invalid records and source failures.
- Demonstrate at least one genuinely additional relevant first-party opportunity from an autonomously discovered source in the held-out real trial, with inspectable evidence and no preloaded domain rule. If none is found, report no demonstrated incremental useful coverage; do not substitute a query count.
- Report languages/regions/categories actually tested, elapsed/local request units, setup/manual interventions and unsearched/blocked scope. Do not infer total-market recall without an external ground-truth denominator.
- Attribute gain conservatively: query expansion, new source, identity consolidation or repaired retrieval. Do not sum duplicate publisher routes or claim historical samples establish ongoing performance.

**Expected product benefit remains conditional:** R03 may improve reach within current providers; R04/R05 may add reachable employers through reusable adapters; R06 avoids duplicate effort; R08/R09 may improve allocation/recovery. None has a defensible numeric gain estimate yet. Use these tests to decide, not to justify a preselected architecture.

## 8. Part 5 validation, unknowns and preservation

This phase validates the **design document and unchanged baseline**, not the proposed architecture. Additional code inspection confirmed the metadata loss boundary, source-only checkpoint scope, additive SQLite migration pattern, compatibility wrappers, human-reviewed alias semantics and existing bounded JobSpy subprocess verification example (B1–B8). No proposed module, table, command, adapter, query generator or A01–A14 test was implemented or executed.

**Existing regression suite:** `1764 passed in 47.72s` (pytest console; JUnit: 1,764 tests, zero failures/errors/skips, 47.660s). Run started at 2026-10-30 08:13:11 UTC in the preserved disposable execution copy, using the existing isolated runtime, `pytest -q -p no:cacheprovider`, separate temporary directory and JUnit output. A Python socket guard allowed loopback and blocked Python non-loopback connections; this is not an OS-level sandbox and does not establish control over native subprocess networking. Provider boundaries in this suite are mocked. No package installation or production data access was needed. This is regression evidence for existing behavior, not proof that the proposed autonomy workflow or A01–A14 passes.

No new live discovery/collection/model/browser trial occurred. Search API feasibility/access, source permission for a specific new employer, generic structured-HTML compatibility, multilingual query quality and real incremental unique coverage remain unverified. A local runtime can make permitted network calls without requiring continuous cloud execution; this does not imply every external service is free or unauthenticated.

Preservation: only `docs/jobhunter_autonomy_review/05_target_architecture_roadmap_and_tests.md` is added for publication. Hash-check original baseline files and all four preceding reports; no application/runtime configuration, dependencies, existing data, source approvals, credentials or CVs changed. Existing suite execution uses disposable copies/state; audit artifacts remain outside Git. **Part 5 complete as design only; roadmap implementation remains deferred.**
