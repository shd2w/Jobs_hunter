# Autonomous discovery implementation and qualification

## 1. Outcome and evidence boundary

JobHunter now has an additive, finite, local intent-to-query-to-observed-source-to-intake runner. It does not replace the existing scanners, server scheduler, CLI, source permissions, SQLite job IDs, applications, aliases, Markdown history, or UniversalAutoApplier queue.

**Demonstrated:** generated candidate-based queries retrieving real jobs from known providers; controlled discovery of an unregistered supported ATS followed by actual adapter execution, canonical intake, reversible duplicate grouping, local matching and persisted reporting; isolation of source failures and restart/cursor behavior.

**Not demonstrated:** a real external run discovering an unregistered supported source and collecting a relevant vacancy from it. Three bounded real trials found **zero recognized reusable-source leads**. Real unknown-source discovery and incremental relevant unique coverage remain unqualified. This is a substantial implementation slice, **not completion of every R01–R12 acceptance condition or operational autonomy**.

Baseline: clean `4b0302ec7024e21bce3bd323d69ca3c932b1327f`, with only the final critique added since reviewed `9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1`. No pre-existing user modifications or private runtime data were edited. Original audits remain unchanged. Routine code was published only after regression checks; no private run artifacts belong in Git.

Evidence labels below: **S** inspected implementation; **U** synthetic/unit test; **C** controlled integration with external transports replaced; **E** bounded real external execution. E does not mean sustained live reliability or measured coverage improvement. Scores are engineering judgments, not experimental measurements.

## 2. Changes and architecture

```text
candidate facts/preferences + region/language + finite operator budget
  -> search_strategy.plan / immutable QuerySpec with provenance and signature
  -> discovery_run (persist plan; approvals/readiness/cache; bounded dispatch)
       -> existing JobSpy provider, using generated runtime query
       -> existing native/public/Scrapling source
       -> optional configured search API (not required)
       -> observed result/description/direct-link evidence
            -> source_discovery recognition / optional bounded public inspection
            -> source_catalog (evidence separate from source permission)
            -> existing supported ATS/feed adapter, subject to access approval
  -> existing sources.scan / validation / Store.ingest transaction
       -> existing source observations + query-scoped or source checkpoint
       -> pending legacy projection outbox
  -> opportunity_identity.reconcile (anchored, reversible metadata)
  -> pending-only local matching + bounded legacy projection
  -> persisted task/run report + query/locale coverage + quality observations
       -> eligible next generated variant / due revisit / explicit deferred reason
```

### R01: truthful outcomes first

`run_scan.py` dispatches only selected scanner factories and records scanner task IDs, times, states, counts and errors. A top-level JobSpy exception becomes a failed result, not silence. Successful independent results still reach the original bridge. A total failure with zero jobs retains exit 1; partial success retains legacy exit 0 **with explicit error/status**. `scanners/jobspy_scanner.py:JobSpyScanner.scan` also records per-query attempts.

The missing-error regression was reproduced before fixing it: 1 failed/1 passed. The R01 related suite then passed 70 tests **before R02 began**. See `tests/test_scan_outcomes.py`. Legacy exit 0 alone must never be presented as all-source success.

### Runtime strategy and progress

`jobhunter_app/search_strategy.py:QuerySpec/plan` generates bounded queries from factual skills and declared preferences, with compact backend/data/software role packs in English, German and Arabic. Every request identifies profile, intent hash, provider, adapter version, query, region, language, exclusions and limits. Unsupported language/default breadth is reported, not concealed. Unknown occupations can fall back to skills/broad terms; the vocabulary is not a general occupation ontology or learned translator.

`expanded_sources.collect(request=...)` supplies runtime parameters without rewriting `config/portals.yml`. Explicit title exclusions still apply; the static positive-title filter no longer discards unfamiliar titles on this new runtime path. Legacy static scans keep their old filters. Local matching remains separate from retrieval and is not proof of relevance, language fluency, immigration status or remote eligibility.

`discovery_state.ensure` adds an independently versioned, backed-up SQLite extension. Existing `Store` schema version 5 remains unchanged; the opt-in extension is version 1. New tables store query progress, runs, tasks, lead evidence, quality observations, reversible group memberships and pending projections. Migration takes a SQLite backup before transactional additive changes and rejects an unknown extension version. `sources.scan(request=...)` checks source/profile alignment and commits query cursor **with intake**. Native snapshots keep source-wide checkpoints; profile changes do not force gratuitous full native recrawls.

### Evidence-backed finding and onboarding

`source_discovery.discover/recognize` preserves observed result URLs, direct destinations and description links before lossy normalization. JobSpy, native Jobicy/Arbeitnow and already-fetched fixed-host Scrapling detail pages contribute sidecars; extra fields do not pollute the canonical job model. Recognizers support observed Greenhouse, Lever, Ashby, SmartRecruiters, supported Workday and feed shapes. There is no tenant-name guessing. Unknown URLs remain unsupported candidates, **not discovered reusable sources**.

Optional `inspect_public` reads robots plus one observed first-party page using Scrapling parsing, at most two inspections per run. It returns observed recognized links, not arbitrary crawl coverage. Pacing/robots/access errors are explicit. The real trials did not execute this path; controlled tests establish only the method contract.

`source_catalog` retains evidence separately from authoritative source approvals. A new supported source can be bound without application code changes. Operator `--approve-public-ats` is an explicit reviewed access/terms policy for **new** ATS bindings; it never reapproves an existing pause. Feeds require separate explicit approval. Actual bounded collection and source-backed valid records inform assessment; lexical profile fit distinguishes relevant evidence, low relevance and uncertainty. An existing permission decision cannot be bypassed by discovering another link.

`workday_source.collect` reuses the existing direct Workday scanner, bounded to its five listing pages and up to 100 details. Detail failures retain listings without invented descriptions and are exposed as provider errors. No live Workday reliability was established.

### Intake, identity and completion

All collected jobs pass the existing `sources.scan` and `Store.ingest` validation, canonicalization and source-sighting transaction. `opportunity_identity.reconcile` groups a syndicated destination only when an actual native source sighting anchors the matching ATS board/posting identity. No title/company-only automatic merging is introduced. Group removal leaves job IDs, applications, aliases and observations intact. Exact conservative grouping will leave many duplicates unconfirmed; it is not a measured universal identity resolver.

`Store.ingest` invalidates matches only for changed job data and queues changed/new records atomically when the extension exists. `discovery_processing.finish` evaluates pending local matches independently of fresh insert count, then attempts up to 100 pending legacy projections. Failures remain pending; original title/location filter rejections are reported as **filtered**, not delivered. Projection does not bypass legacy evaluation or application submission. Old records predating the extension are not automatically backfilled into its projection table.

`run_all.py` performs pending local matching when its SQLite profile exists and does not exit early if the legacy Markdown queue still has unchecked work. Existing cloud evaluation and queue exporters remain optional, separate stages.

### Feedback, quality and bounded execution

`search_coverage.coverage` records generated query × region × language states and usable counts, distinguishing unsearched/deferred gaps from successful observations. The next eligible pre-generated variant can execute after an empty result; it does **not** invent an unlimited new strategy. Priority uses conservatively confirmed relevant-group contributions rather than raw URL insertion counts, prioritizes supported leads, explores cold-start sources and reserves every fifth dispatch for eligible native exploration. Contributions overlap and must not be summed as global novelty.

`observe` marks degradation after three comparable same-signature failed/invalid observations; valid empty results alone are not broken. Existing cooldowns, provider gates and failure handling remain authoritative. There is no generic schema self-repair, automatic reauthorization, market recall estimator or comprehensive category-aware gap model.

`discovery_run.run/report` persists tasks before dispatch, records terminal/deferred reasons and reconciles interrupted runs on reopening. Query caches expire after an hour; compatible unfinished queries resume their cursors. Cancellation and finite attempt/deadline budgets stop new dispatch. The deadline **does not forcibly terminate an in-flight vendor call**; JobSpy calls may include vendor-managed requests. The opt-in QA harness uses a separate 120-second child-process timeout. No daemon, cloud host or paid model is required.

### Optional search and structured HTML

`search_provider.BraveSearch` is executable code against the documented Brave API, not a browser-search link. It requires local key plus explicit access/cost consent and limits credential scope to its endpoint. Only offline contract tests passed; no credentials/cost access were available for live validation. It is optional, not an enabled service.

`structured_source.collect` reuses Scrapling for an opt-in, explicitly registered/approved same-origin JSON-LD `JobPosting` method: robots, conservative pacing, at most five reads, bounded pending details/next-page state, strict shared intake and explicit unsupported-schema errors. It does not alter fixed-host collectors or auto-onboard arbitrary domains. Registration of unknown structured sites still requires operator/developer review. This is an advanced reusable collection method, not a claim of autonomous universal adapter development.

## 3. Source coverage and qualification

| Family/method | Implemented scope now | Evidence this implementation | Still unknown/blocked |
| --- | --- | --- | --- |
| JobSpy: LinkedIn, Indeed, Google Jobs, Bayt, Glassdoor, ZipRecruiter, Naukri, BDJobs, HelloWork | All nine existing registered providers preserved and eligible for generated requests; selection remains gated/budgeted, not every provider on every run | U/C generated/scoped execution; E Indeed and LinkedIn only | Seven others not live requalified; provider syntax/country/restrictions still apply; Naukri is not Naukrigulf |
| Greenhouse, Lever, Ashby, SmartRecruiters | Existing collectors plus observed URL recognition/catalog binding | C held-out Lever discovery-to-native-intake; U/C other family recognition and existing adapter regressions | No new unregistered live employer qualification |
| Workday | Existing legacy scanner plus new observed identity wrapper into SQLite source pipeline | C HTTP fixtures, including detail failure | Live access, schema diversity, all regional hosts unverified |
| Jobicy, Arbeitnow | Existing native and fixed-host Scrapling mechanisms preserved, evidence links retained | Existing U/C regression; E native Arbeitnow and Jobicy collection | Fixed-host Scrapling was not live requalified here |
| RemoteOK, Remotive, We Work Remotely | Existing collectors preserved | Existing U/C regression; E RemoteOK and Remotive | WWR not live requalified |
| Wuzzuf/Naukrigulf and other previously scoped boards | Existing approved/authorized collectors unchanged | Existing regressions retained | Access/setup and live functionality not assumed |
| RSS/Atom | Existing intake/approval plus recognition of observed feed URLs | U/C, existing regressions | No newly discovered live feed qualified; access still explicit |
| USAJOBS, HN and scoped social/community APIs/imports | Existing methods preserved; no outreach changes | Existing full-suite regressions | Credentials, authorized scopes, manual feed/channel/thread setup and source-specific limits remain |
| General structured employer HTML | New reusable approved same-origin Scrapling JSON-LD method | C held-out pages, continuation, invalid/missing schema and approval | No live generic site qualification; no automatic unknown-domain onboarding, JS/login/custom schema support |
| Optional Brave search API | Implemented provider and response-to-lead path | U/C contract/credential boundary | No approved key/account/cost; E not run |
| Monster, StepStone and arbitrary regional/custom employer portals | No new dedicated adapters promised | Indirect evidence links may be cataloged | Unsupported families still need a reviewed collection method; directory names are not adapters |
| Agency, NGO, university/research/government beyond existing adapters, specialist/freelance/startup sites | Indirect ATS/feed/structured routes where genuinely available | No representative live category trial this implementation | No broad newly qualified category coverage, email ingestion, unrestricted communities or login automation added |

A source adapter existing is not live verification. Scrapling is a primary reusable parsing/collection engine in its reviewed paths, not a separate autonomous agent or permission-bypass mechanism. Source count is not unique publisher coverage.

## 4. Before/after autonomy comparison (0–5)

Baseline scores are from Part 4. After values assess demonstrated **bounded implementation scope**, not full real-world qualification. No 4/5 or 5/5 is awarded. The lack of a real unknown-source trial limits any discovery claim.

| Dimension | Before | After | Evidence / reason and ceiling |
| --- | ---: | ---: | --- |
| Query generation | 1 | 2 | U/C EN/DE/AR dispatch; E generated Python Developer query. Compact role packs, not comprehensive semantic planning. |
| Independent source discovery | 0 | 2* | C observed unseeded ATS lead → recognized binding; real trials found zero recognized leads. |
| Previously unknown websites | 0 | 1* | Evidence catalog and optional observed-page inspection C; no real new reusable website qualified. |
| Source integration/extensibility | 2 | 3* | C held-out supported employer reaches intake without new adapter; operator access policy still needed. |
| Source-category breadth | 2 | 2 | Existing breadth preserved, not newly established comprehensive live category coverage. |
| Global/multilingual discovery | 2 | 2 | New EN/DE/AR requests C; regional relevance/recall and source-specific locale behavior not broadly E-qualified. |
| Retrieval/normalization | 3 | 3 | Existing intake plus C new bindings; bounded E known-source retrieval. No sustained degradation qualification. |
| Cross-source deduplication | 2 | 2 | New reversible anchored groups C; too narrow/no representative precision/recall study to upgrade globally. |
| Coverage-gap identification | 1 | 2 | C query/locale gap triggers another generated variant; category/market coverage model incomplete. |
| Adaptive source prioritization | 2 | 2 | C confirmed-group priority and exploration; no measured live relevance/coverage gain. |
| Broken-source detection/recovery | 2 | 2 | New comparable quality observations, partial failures/restarts C; generalized repair absent. |
| Unnecessary user-input reduction | 3 | 3 | Ordinary generated search and supported onboarding C remove query/ID work; general source management still remains. |
| End-to-end autonomy verification | 2 | 2 | Broad synthetic regression plus bounded E known-source runs; real A03/A05 still open. |

\* These are explicitly C-scoped judgments, not scores for verified live independence. No aggregate score or percentage improvement is calculated.

## 5. User-input reduction

- **Eliminated on the new ordinary path:** per-search YAML edits, exact title strings for covered role families, predefined company lists, candidate-supplied board URLs and website lists. `run_local.py discover` consumes skills/preferences and optional regions/languages.
- **Eliminated in controlled supported-family expansion:** manually transcribing an ATS board ID from an observed recognized URL and writing a new adapter/config entry for that employer. The engine records the actual observed evidence, selects an existing method and attempts collection when authorized.
- **Still legitimate:** accurate candidate facts/skills, desired role/region/languages, explicit exclusions/remote choices, finite budget, access/terms approval, optional credentials/cost consent, ambiguous identity/relevance review.
- **Still unnecessary work not eliminated generally:** unsupported domains need method development/review; custom feeds/communities need lawful scope setup; ordinary supported queries outside the small vocabulary may need better semantic expansion; generic structured sites still need registration/approval. No request to provide hundreds of URLs is a prerequisite for starting discovery.

## 6. Tests and executed evidence

Baseline unmodified: **1,764 passed in 64.93s**. Release: **1,793 passed in 90.04s**, adding 29 cases. Package checkpoints are recorded in `IMPLEMENTATION_PROGRESS.md`. Existing test files were not weakened or deleted. All new evidence is synthetic/disposable except the three separately identified public trials.

| Acceptance | Verification actually executed | Remaining qualification |
| --- | --- | --- |
| A01 no source URLs | C real runner with skills only; E synthetic profile/region generates known-source search | Representative real user workflows not evaluated |
| A02 useful generated terms | C parameter/provenance assertions; E generated query retrieves canonical records | Usefulness not human-adjudicated across occupations |
| A03 unregistered source finding | C fake board response contains observed held-out Lever URL, not initial registry | **E not passed: zero recognized new source leads** |
| A04 assess usefulness | C source-backed vacancy and lexical evidence vs uncertain/access states | Real relevance/source-value study open |
| A05 real attempt from discovered source | C native HTTP boundary fixture receives actual call through adapter | **E new-source retrieval not demonstrated** |
| A06 normalize/persist | C existing validation/transactions and pending matching; E known-source records stored | New-source E path open |
| A07 identity | C native anchor + syndicated URL group, distinct requisitions remain separate, unlink keeps application | Representative labeled precision/recall open |
| A08 partial failure | C R01 scanner exception and independent runner provider failure | No induced real publisher outage trial |
| A09 degradation | U/C three comparable invalid/failed vs valid-empty cases | Longitudinal real degradation/recovery open |
| A10 coverage feedback | C valid-empty first variant followed by actual second query dispatch | Full category/semantic search expansion not implemented |
| A11 languages/regions | C EN/DE/AR generation and German/Arabic actual fake-provider dispatch/intake; E Germany/en | Locale usefulness and broad provider matrix open |
| A12 resume/repeat avoidance | C cursor separation, crash/reopen persisted task recovery and second-run no repeated board/ATS calls; E reused same state/gates | Sustained scheduler/restart fault study open |
| A13 no ordinary config edits | C configuration bytes unchanged; E no supplied sources/queries/config edits | Unsupported family onboarding still manual |
| A14 honest report | C reconciled terminal task counts, leads/bindings/records, failed/deferred states and persisted report | No claim raw URLs/inserts equal useful novel opportunities |

Core new tests: `test_scan_outcomes.py`, `test_runtime_queries.py`, `test_source_leads.py`, `test_discovery_processing.py`, `test_autonomy_acceptance.py`, `test_structured_source.py`. The controlled flow calls real application methods but replaces external JobSpy/HTTP. Those fixtures are **not external discovery**, however held out their identifiers are.

Local test runtime: Python 3.13, existing pinned JobSpy/Scrapling environment, no dependency installations in this work. A Python non-loopback socket guard was used for regressions; it is **not an OS sandbox and does not guarantee native-process isolation**. External boundaries in new tests are mocked. `pip check` found no broken requirements; Scrapling FetcherSession/Selector imports passed. The integrated preparation/learning smoke passed (47 local HTTP operations, zero external requests, synthetic CV hash preserved). Windows, optional real search API, paid models and long-term throughput remain unexecuted.

## 7. Real external qualification: honest negative new-source result

The opt-in `qa/autonomy_discovery_live.py` used a synthetic Python/SQL/backend profile, Germany/en, no source/company/URL/exact query input, two adapter attempts and a hard child timeout. All trials reused the same disposable state, retained cooldown/access gates, used no paid API/model/login, and did not autoapprove new ATS access. Raw artifacts/database/logs remain outside Git; only aggregate non-private results are recorded here.

| Trial | Actual observations | What it proves / does not prove |
| --- | --- | --- |
| 2026-10-30, first; run `347b843990be42f0b57f687b121449b8`, 09:56:10–09:56:20 UTC | Generated Python Developer query: Indeed 20 canonical inserts; independent Arbeitnow DE 300. Partial/budget-deferred work. **0 recognized source leads**. | E generated known-source querying/intake. The earlier receipt field `source_leads: 248` was unrecognized candidate URLs, not reusable discovered sources; current report separates them. |
| Same state, second; started 10:03:41 UTC | Eligible Jobicy 100 inserts and RemoteOK 99. Partial. 199 candidate URLs, **0 recognized source leads**; optional public inspection requested but **0 executed**. | E eligibility/known-source collection, not live public-inspection qualification. |
| Same state, LinkedIn-scoped query trial | LinkedIn 20 inserts and Remotive 12. Partial. 12 candidate URLs, **0 recognized source leads**, **0 public inspections executed**. | E generated second-provider collection, not new-source discovery. |

Do not add these raw insert counts and label the sum unique/relevant opportunities. No matched-budget before/after comparison or human relevance adjudication was performed. No ATS native-anchor duplicate success was established in these real trials. Receiving arbitrary job URLs is insufficient for A03; successful known-source intake is insufficient for A05. The supported-family chain is C-verified, E-unqualified. More repeated requests simply to manufacture a success are not justified.

## 8. Remaining work and engineering verdict

1. **Highest-value next qualification:** under explicit lawful access, obtain a real permitted result containing a previously unregistered supported ATS/feed destination, retain acquisition evidence, approve the actual new source as required, and run its real adapter through intake, identity and matching. Record no-result/blocked outcomes honestly. Optional authorized search API may help but is not presumed necessary or available.
2. **Extend strategy/coverage:** richer role/skill/locale mappings and source-category intent, then evidence-driven new query construction beyond the finite packs. Current query-gap reporting is not the complete R08 coverage model.
3. **Qualify identity/value feedback:** labeled syndicated/distinct requisition corpus and matched-budget real relevance/novelty comparisons before adaptive-value or coverage-increase claims.
4. **Qualification-dependent methods:** live approved Workday/structured HTML, optional search API, publisher schema/access changes and sustained quality/revisit tests. Generic structured recipes still need reviewed activation; no autonomous new-adapter coding is shipped.
5. **Operational limits:** in-flight cancellation/deadline behavior, finite projection batch, retained provider cooldowns and credentials/setup. Pending report and next runs expose unfinished work instead of hiding it. Never clear gates merely to increase throughput.

**Direct verdict:** JobHunter is more autonomous in generating and executing covered queries and has a working controlled supported-source expansion pipeline. It can recognize/bind observed previously unconfigured supported sources and retrieve their jobs **under controlled integration**. This has not yet been demonstrated against a real newly discovered source. Ordinary searches no longer need manually constructed queries or configuration edits; comprehensive unknown-domain and cross-category expansion still needs engineering plus lawful real qualification. The full roadmap must not be marked operationally complete. See `RUNNING_LOCALLY.md` and the package-by-package progress ledger.
