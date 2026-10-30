# Final autonomy critique and engineering verdict

**Scope:** job discovery only; synthesis of Parts 1–5, not a new application implementation. **Reviewed repository:** `shd2w/Jobs_hunter`, baseline `9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1`. The five published reports were checked byte-for-byte against the saved copies before synthesis.

**Reading guide:** [01 Repository map](01_repository_map.md), [02 Execution trace](02_search_execution_trace.md), [03 Source coverage and manual dependencies](03_source_coverage_and_manual_dependencies.md), [04 Scorecard and root causes](04_autonomy_scorecard_and_root_causes.md), [05 Target architecture, roadmap and acceptance tests](05_target_architecture_roadmap_and_tests.md). Exact source references and controlled-test details remain there. **Static** means implementation inspected; **controlled** means real application paths with synthetic state/replaced external boundaries; **historical live** means an existing recorded sample, not a fresh availability test. **Proposed** means not implemented by this review.

## 1. Executive verdict

**JobHunter is a partially autonomous, known-source collector—not an independently expanding job-discovery system.** It can start without candidate-supplied URLs or exact queries, search a finite configured universe, retrieve bounded results, normalize/store observations and conditionally match jobs. It cannot currently derive a full retrieval strategy from candidate information, discover a previously unconfigured website as a source, recognize its collection method and onboard it automatically. No realistic profile → new query → unknown source → useful persisted/evaluated opportunity run has been demonstrated. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md#L5-L15]

The candidate should supply **job intent, factual qualifications, exclusions and acceptable geography/languages**. Today, expanding beyond defaults also requires an operator/developer to maintain search vocabulary, identify employers/ATS IDs/feed URLs/community scopes, register sources and qualify unsupported methods. Access consent, credentials and genuinely ambiguous records still require legitimate human decisions; exhaustive website and synonym maintenance should not.

The three largest capability gaps are **(1) no executable source-discovery/onboarding loop, (2) no candidate-to-query expansion and terminology-recovery loop, and (3) no coverage/quality feedback that selects further useful searches**. Separate pipeline identities and outcome reporting weaken the feedback signal. Adding more hard-coded URLs or merely installing another scraping library does not resolve these causes. The magnitude of missed real suitable opportunities remains unmeasured. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md#L146-L180]

## 2. Verified current capabilities

| Current capability | Evidence and precise boundary |
| --- | --- |
| Automatic known-source startup and scheduling | `jobhunter_app/automatic.py:17–25,54–85,164–208`, starter definitions, seeding and `cycle()`: 16 starters; approved/due source selection; at most ten attempts/cycle. Blank-profile collection is allowed. `run_local.py:250–253` enables automatic server mode by default; `web.serve()` itself defaults automatic off. It is not universal background execution. |
| Three scanner engines and a separate source-service path | `run_scan.py:57–111`, `run_scan()`: Scrapling, direct employer APIs, JobSpy, then legacy bridge/SQLite mirror. `sources.scan()` instead dispatches registered source kinds under locks/gates. The CLI does not automatically run every adapter in `POLICIES`. |
| Static, provider-aware queries | `scanners/jobspy_scanner.py:53–117`, `_load_searches/_load_primary`: literal configured terms/locations or explicit entries; provider constraints and optional CLI overrides. `expanded_sources.py:23–53`, `collect()`: one provider/query/page progression per source scan. Empty results advance the finite plan, not invent a new one. |
| Reusable known-source retrieval | `sources.py:93–148,156–247`, `Source`, `fetch` and normalizers; `collection.py` collectors. Controlled new-ID tests succeeded for Greenhouse, Lever, Ashby and SmartRecruiters. This proves endpoint reuse **after an ID is supplied**, not source finding or live service availability. |
| Real Scrapling integration within fixed scopes | `scrapling_engine.py:10–38,112–167`, fixed Jobicy/Arbeitnow definitions and bounded collection; actual Selector/transport fixtures exercised. It is not a generic arbitrary-domain crawler. Optional authorized-board parsing is a separate role. |
| Validated intake and durable continuation | `validation.py:33–53`, `normalize_job`: title, company and valid public canonical URL required; description may be missing. `sources.py:264–354`, `scan/_scan_locked`: locks, approvals, publisher gates and atomic observations/checkpoint/completion. Controlled rollback/cancellation cases preserve prior state. |
| History, matching and some failure recovery | `store.py:185–229` canonical URL/sightings; local matching is conditional in `automatic.py:204–208`. `source_health.py:8–60` implements gates/health/reset; interrupted-run and specific Jobicy-expiry recovery exist. A source/query failure often leaves others running; general self-repair does not exist. |

Implementation/controlled evidence: Parts 1–3 and the source references below. None of these rows asserts current live reliability, complete descriptions, global recall or arbitrary-site compatibility. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/01_repository_map.md#L100-L115] [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/02_search_execution_trace.md#L87-L105] [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/03_source_coverage_and_manual_dependencies.md#L242-L258]

### Reconciled findings—not contradictions

- **Zero-input startup is real; independent discovery is not.** Sixteen seeded records and thirty registered kinds are different counts. Kinds include multiple mechanisms for the same publisher; neither count equals distinct working live publishers. Directory output is manual guidance: the controlled directory call returned Google links, made zero external requests and added no sources.
- **Query execution is automatic; semantic query generation is manual.** Changing candidate skills does not create outbound terms. Selected English/German/Arabic post rules do not establish multilingual retrieval generation.
- **Deduplication exists, but not one cross-source identity policy.** SQLite merges canonical URLs/aliases; legacy rules use company/title/location heuristics. The controlled same-fields/different-URLs case remained two SQLite records. New canonical URLs are not necessarily new opportunities.
- **Collected, retained, evaluated and exported are different populations.** JobSpy/legacy prefilters can reject unfamiliar titles before evaluation; native/primary Scrapling SQLite intake is broader. The legacy mirror follows SQLite commit. `run_all.py:77–104` gates downstream evaluation on legacy `new_added`; zero new legacy inserts need not mean no pending SQLite/evaluation work.
- **Error isolation is useful but not uniformly observable.** A controlled top-level `JobSpyScanner.scan()` failure was logged while `run_scan.main()` returned an empty error list and exit 0. Ordinary per-query and per-source failures have stronger isolation/accounting. This is a specific verified CLI reporting gap, not a claim all failures are hidden.

These distinctions resolve Part 1's static risks using later controlled evidence; remaining live/quality uncertainties are not resolved by inference. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/02_search_execution_trace.md#L178-L260] [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md#L48-L74]

## 3. Autonomy scorecard

Scale: **0 absent; 1 manual; 2 partially automated; 3 mostly autonomous; 4 highly autonomous; 5 operationally autonomous under realistic verified conditions.** Scores retain Part 4's calibration; the design in Part 5 earns no capability upgrade. These are ordinal engineering judgments, not percentages or an averaged product score.

| Dimension | Score / 5 | Concise justification |
| --- | --- | --- |
| Search-query generation | **1** | Automatically expands human-authored strings; no profile-derived vocabulary/translation/rewrite loop. |
| Independent source discovery | **0** | Selection starts from seeded/registered identity; directory links are not executed discovery. |
| Previously unknown website discovery | **0** | Unknown job URLs may appear in results, but no career-site recognition/onboarding path follows. |
| Source integration/extensibility | **2** | Reusable ATS/feed contracts; identity resolution/onboarding manual; unsupported protocols need code. |
| Breadth across source categories | **2** | Several families implemented; category coverage uneven, indirect or access-dependent. |
| Global/multilingual discovery | **2** | Regional settings and selected multilingual rules; no dynamic native-language query strategy or recall proof. |
| Retrieval/normalization | **3** | Ordinary supported configured cases run automatically with bounded intake/continuation; live robustness unverified. |
| Cross-source deduplication | **2** | Canonical URLs, legacy heuristics and reviewed aliases; no general cross-URL opportunity resolution. |
| Source-coverage gap identification | **1** | Telemetry informs humans, not intended-versus-observed scope analysis. |
| Adaptive source prioritization | **2** | Time/readiness/gates affect ordering; relevance/novelty yield does not drive it. |
| Broken-source detection/recovery | **2** | Structured failures, gates and specific resume/recovery; layout/access repair often manual. |
| Reduction of unnecessary input | **3** | Defaults remove starter URL/query burden; expansion still requires source/vocabulary management. |
| End-to-end autonomy verification | **2** | Extensive offline/control evidence plus historical samples; desired realistic unknown-source outcome unproven. |

Evidence/next-level criteria for every dimension are retained in Part 4, E01–E13 and its scorecard. Retrieval/input reduction can score 3 for normal known-source contracts while discovery remains 0; none implies operational end-to-end autonomy. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md#L48-L144]

## 4. Source coverage

**“Verified” below means implementation plus executed offline/controlled contracts, unless explicitly historical live. No source received a fresh live availability qualification during this review.** A missing dedicated adapter does not mean vacancies can never arrive through upstream indexing, supported ATS/feed or authorized imports.

| Source/category | Current functional scope and limitations |
| --- | --- |
| JobSpy boards | Nine provider IDs: **LinkedIn, Indeed, Glassdoor, ZipRecruiter, Bayt, Naukri, BDJobs, HelloWork, Google**. Dispatch/intake tested offline. Historical positive samples exist for LinkedIn, Indeed, Naukri, BDJobs and HelloWork; recorded 403s for Glassdoor, ZipRecruiter and Bayt. Google Jobs has a configured adapter/error handling but no successful usable collection established. Historical outcomes are not current pass/fail assertions. |
| Other general/regional boards | Wuzzuf/Naukrigulf bounded authorized listing adapters tested offline; require explicit permitted listing URLs. Historical Wuzzuf blocked; Naukrigulf HTTP timed out but an explicitly selected ordinary-browser sample returned jobs. Monster/StepStone: **no direct adapters**. Naukri is not Naukrigulf. |
| Employer ATS | Greenhouse, Lever, Ashby, SmartRecruiters: reusable ID-based adapters, controlled intake verified. Workday exists in the legacy direct scanner and needs explicit tenant/board API/base configuration; default tracked-company list empty. Legacy SmartRecruiters known-company mapping is narrower than the generic source-service account-ID route. No automatic employer/ATS finding. |
| Other ATS/arbitrary career pages | Eightfold, Taleo, SuccessFactors, iCIMS, Workable, Recruitee, Personio, Teamtailor, BambooHR: no dedicated adapter in the inspected dispatch. No generic career-site/sitemap crawler or ATS fingerprinting. Scrapling's current scoped JSON-LD extraction is not universal support. |
| Remote/fixed publishers | Native Jobicy, Arbeitnow DE/UK, Remotive, Remote OK, We Work Remotely plus primary Scrapling Jobicy/Arbeitnow: offline verified, bounded publisher-specific retrieval. These overlap publishers; UK Arbeitnow is not a starter. Himalayas is directory-only, not a working adapter. |
| Social/public hiring/community | Official scoped LinkedIn organization posts, X user timeline, Reddit subreddit submissions, Telegram bot update queue and Discord channel messages: offline verified, actual rights/setup unverified. **Not** global platform search/account/community discovery. Telegram is not channel-history search. HN needs a supplied Who-is-hiring story ID; newest-thread lookup absent. Other forums mainly indirect feeds/supplied posts. |
| Government/institutions/agencies | USAJOBS keyed public API implemented/tested; credentials, keywords and approval required. Other government, university, research, NGO/UN and recruitment-agency pages are generally **indirect** via known ATS/feed/import, not dedicated discovery/collection. No recruiter outreach assessment. |
| Freelance/startup/niche | Contract roles can arrive from general sources; no dedicated freelance-marketplace search or startup/VC portfolio traversal. Niche/industry/internship roles depend on known providers, terms, feeds or imports. Directory labels do not confer coverage. |
| Feeds/newsletters/alerts/imports | Public RSS/Atom ingestion and canonical CSV/JSON/JSONL/optional XLSX tested; URLs/files must already be obtained. Generic feeds do not automatically fetch linked job descriptions. Authorized copied posts/local newsletter text can be triaged; no general newsletter crawler or mailbox/EML connector. |
| Search engines/languages | No executable general-web discovery client; source directory only generates browser search links. Google Jobs route remains unproven. English/German query terms and finite regional mappings; selected Arabic post extraction does not imply Arabic query discovery. Global language/category recall unknown. |

Full source statuses, required scopes, exact paths and historical artifacts: Part 3's matrix. Access-blocked historical samples, unprovisioned optional runtimes and deliberately uninspected production credentials are **inaccessible/unverified evidence**, not grounds to declare permanent provider failure. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/03_source_coverage_and_manual_dependencies.md#L40-L127]

## 5. Manual-input dependencies

The M01–M28 inventory in Part 3 is grouped below without discarding its distinctions. **Eliminating manual entry means the engine obtains/validates needed facts—not that endpoints, permissions or candidate intent become unnecessary.** All remedies are proposed.

| Current burden / owner | Remove or reduce it by | Keep legitimate human decisions |
| --- | --- | --- |
| Exact title/keyword/synonym/translation lists and repeated per-company terms; operator/developer (M02/M05/M06/M12) | Versioned candidate-intent query planner, tested role/skill/locale packs, provider formatting and bounded evidence-backed variants after low yield. | Candidate job goals/exclusions; optional diagnostic query override. |
| Lexical allowlists and geographic/provider mapping; operator/developer (M03/M04/M28) | Normalize requested geography; maintain provider capabilities centrally; evaluate unfamiliar titles with descriptions before irreversible positive-only rejection. | Acceptable locations, languages, seniority, remote constraints; never infer worldwide eligibility. |
| Exhaustive employer/source lists and hard-coded site scopes; operator/developer (M07/M08/M15) | Extract observed career/apply/feed leads; optional executable search API; catalog discovered sources rather than expand core URL lists. | Favorite/excluded employers as optional preferences; reviewed collection methods. |
| ATS IDs, SmartRecruiters account IDs, Workday tenant/board endpoints; operator (M09–M11) | Family recognizers derive/validate bindings from first-party source evidence and use existing adapters. | Access restrictions; unsupported protocol review. Never guess company domains/endpoints. |
| Listing/feed URLs and HN thread IDs; operator (M13/M14/M16) | Discover explicit supported listing/feed links and current permitted hiring-thread metadata; bounded validation/probes. | Required authorization and source-specific limits. |
| Social account/community/channel scopes; operator (M18/M19) | Authorized scope discovery/relevance assessment and persisted validated scopes where APIs permit. | Actual API/member rights, consent, cost approval and tokens; a setup flag cannot create remote access. |
| Repeated registration, source selection and reset/retry decisions; operator (M23/M24/M26) | Policy-aware supported-family onboarding, existing due scheduling, durable task state and cause-specific retries. | Reapproval when necessary; respect publisher gates/Retry-After. Existing automatic mode already removes much batch selection. |
| Manual files/copied text/field repair; candidate/operator (M20–M22) | Prefer supported retrieval and source-backed detail enrichment; retain review only for unresolved evidence conflicts. | Content rights, factual uncertainty and ambiguous identity. No fabricated job fields. |
| Runtime setup/schema repair/new adapters; operator/developer (M25/M27) | Clear readiness checks, quality drift detection, reusable family collectors and reviewed generic structured-HTML method later. | One-time dependencies/access; genuinely new protocols still need engineering, not autonomous arbitrary code. |
| Candidate profile and authorized service setup (M01/M17/M19) | Reuse stored preferences; generate USAJOBS keywords; make missing setup explicit once. | Candidate facts and authorized keys/consent remain necessary where used. |

These inputs are not all mandatory at startup. Blank-profile seeded collection needs neither hundreds of URLs nor social/model credentials; additional optional sources impose their own setup. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/03_source_coverage_and_manual_dependencies.md#L137-L184]

## 6. Root causes

| Priority by product impact | Direct cause—not merely a symptom | Engineering consequence |
| --- | --- | --- |
| **RC1: critical** | No lead acquisition → family recognition → validated onboarding path. Registry starts after identity is known. | Fix this shared boundary instead of writing unrelated category adapters or bigger seed lists. Main potential reach gain; not measured yet. |
| **RC2: critical** | Candidate intent is downstream of static retrieval vocabulary and path-dependent lexical acceptance. | Move evidence-backed strategy upstream; descriptions cannot rescue a job discarded before matching. |
| **RC3: high** | No intended-versus-observed coverage model or useful-opportunity feedback. | Health/counts alone cannot select the next best query/source or detect missing scope. |
| **RC4: high, foundational** | CLI/source/legacy paths differ in identity, acceptance, persistence and completion/error semantics. | Establish comparable outcomes and reversible identity before optimizing novelty; preserve compatibility rather than rewrite. |
| **RC5: source-dependent high** | Source lifecycle and schema/runtime/access qualification mostly manual beyond narrow recovery contracts. | Automate routine permitted recovery; isolate genuine unsupported/access/schema cases for review. |
| **RC6: high assurance gap** | No realistic desired autonomy outcome qualification. | Fixture totals cannot establish field value, availability, multilingual recall or real unique coverage. |

RC1/RC2 are the largest product limitations; narrow RC4 observability work comes first in delivery order because it makes their results measurable. Difficulty ranges from localized reporting to cross-pipeline migrations and externally constrained collection; no monetary, time or coverage-gain estimate is defensible yet. RC6 limits confidence; it does not itself cause absent source discovery. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md#L146-L180]

## 7. Target architecture — proposed, incremental and local

Keep the current Python application, SQLite, JobSpy, primary Scrapling collectors, native ATS/feed/post adapters, locks/gates and legacy entry points. **One finite on-demand local runner** is sufficient; a scheduler can call it later, but no continuous cloud service, LLM or multi-agent platform is required.

```text
stored candidate intent -> bounded strategy / runtime queries
  -> known-source collection + executed lead discovery
  -> inspect / assess / recognize supported family -> validated catalog binding
  -> gated retrieval -> shared normalization / durable observations
  -> reversible opportunity grouping -> local matching / pending projection
  -> coverage + health evidence -> bounded next action or persisted deferral
  -> reconciled results / failures / limits -> exit
```

| Component / proposed interface | Main change and existing reuse |
| --- | --- |
| Strategy, `search_strategy.py` | `build_intent` / `plan` produce versioned `Intent` and `QuerySpec` from candidate evidence, locale packs and bounded variants. Extend real JobSpy/native parameter paths, not YAML per run. |
| Discovery, `source_discovery.py` | `discover -> LeadBatch`: preserve observed employer/apply/feed metadata and inspect permitted links; later one permitted real search API. Current `JobPosting.to_dict()`/JobSpy normalization loses non-core discovery metadata, so an envelope/sidecar must be added. |
| Capabilities/catalog, `source_capabilities.py`, `source_catalog.py` | `recognize -> BindingCandidate`, assess/probe/bind/activate. Code recognizes a family once; runtime catalog stores employer IDs, evidence and access state. Reuse known ATS/feed adapters; Workday needs a wrapper. Discovery is not approval. |
| Runner/ledger, `discovery_run.py` | Run/task IDs, finite budgets, outcomes, cancellation and durable resume; call existing `sources.scan` enforcement. Query-dependent cursors scoped to profile/intent/source/query signature/adapter version; source-wide snapshots may share compatible progress. Gates stay publisher/source scoped. |
| Shared intake/identity | Proposed intake facade reuses `normalize_job`, `Store.ingest` and source transaction. Keep source observations/URL-keyed jobs; add reversible high-confidence first-party opportunity grouping. Do not destructively re-key applications/history or merge on title/company alone. |
| Coverage/health/priority | Requested role/region/language/category cells versus actual evidence; distinguish empty/blocked/unsupported/deferred. Deterministic next-action ranking with exploration/fairness, comparable quality monitoring and cause-specific revisits. Preserve existing quotas/gates. |
| Evaluation/reporting | Process pending/changed work independent of new legacy insert count; optional idempotent projection outbox. Report discovered, recognized, activated, attempted and collected separately; distinguish canonical records, opportunity groups and evaluated/reviewable jobs. |

**Integration boundary:** prefer recognized public ATS APIs/feed methods. Existing provider evidence may expose no usable new leads; in that case report the limitation, not discovery success. Optional web-search access must be implemented in the local application—chat search tools are not a runtime dependency. Unknown structured HTML needs a **new reviewed generic Scrapling/JSON-LD method later**, not silent removal of current fixed-host restrictions. Unsupported/denied sites remain explicit outcomes; no universal scraper claim.

Budgets distinguish provider calls, instrumented HTTP reads, returned rows and wall time. JobSpy may make internal vendor requests; one provider call is not one HTTP request. Stop dispatching when due/budget exhausted, persist deferred work and exit. Hard kill deadlines require process isolation, not assuming threads are cancellable. Full proposed contracts/migration/identity rules: Part 5. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/05_target_architecture_roadmap_and_tests.md#L31-L169]

## 8. Prioritized improvement plan

IDs preserve Part 5 so this summary is directly actionable. **M** several interfaces/tests; **L** cross-pipeline/migration; **XL** new general method plus external qualification. Relative effort is not a calendar estimate. Acceptance IDs refer to Section 9. All work below is proposed.

| Order / item | Dependencies; effort | Measurable acceptance |
| --- | --- | --- |
| **P0 R01: truthful run/task outcomes and report** | First; M–L. `run_scan.py`, `scanners/base.py`, `sources.py`, `store.py`, proposed runner/reporting. | Top-level scanner failure produces failed/partial report, not error-free success; all planned tasks reconcile to completion/failure/defer. A08/A14. |
| **P0 R02: runtime query requests/scoped progress** | R01; L. Existing scanners/`expanded_sources`/source service/store. | Correct cursor on repeat/reorder/profile/version change; old entry points and gates preserved; no config edit. A01/A12/A13 plus migration/rollback tests. |
| **P1 R03: intent/query/locale planner and acceptance policy** | R02; M–L. Strategy, retrieval vocabulary, existing matching/filter interfaces. | Profile skills/intent produce and actually dispatch unseen useful variants; excluded intent not invented; tested locale/provider semantics. A02/A11. |
| **P1 R04: observed lead extraction/family recognition** | R01–R03; L. Provider envelope/discovery/capabilities. | Held-out source absent from seed/catalog emerges from executed evidence, not user URL/per-employer code. A03. |
| **P1 R05: catalog/probe/supported onboarding** | R02/R04; L. Reuse registration, ATS/feed/Workday logic and health gates. | Useful permitted supported lead becomes real vacancy requests and accepted rows; blocked/unsupported accurately classified. A04–A06/A13. |
| **P1 R06: shared intake/reversible identity** | R01/R02; L; parallel with lead work. | Same first-party opportunity at two URLs groups; distinct requisitions remain distinct; application/alias/history state preserved. A06/A07. |
| **P1 R07: pending evaluation/projection completion** | R01/R02/R06; M–L. `run_all`, evaluation/compat/store interfaces. | Pending changed work processes even with zero inserts; mirror failure remains pending/reportable and retry idempotent. A06/A12/A14. |
| **P2 R08: coverage and explainable next-action ranking** | R03/R05–R07; L. Coverage/strategy/automatic interfaces. | Known gap produces an actual new eligible task; utility affects ordering without bypassing gates or starving cold starts. A10/A12; equal-budget replay. |
| **P2 R09: comparable quality monitoring/revisits** | R01/R02/R08; M–L. Health/ledger. | Repeated schema degradation detected; valid empty response not mislabeled; due work resumes next local invocation. A08/A09/A12. |
| **P2 R10: optional executable search-lead API** | R04/R05 and verified provider access; M–L. | Real search response leads to held-out supported source and actual collection; unavailable setup reported, not mock-passed. A03–A05/A10/A11. |
| **P2 R11: representative qualification** | Start evidence harness at R01; release gate after applicable work; M–L. Existing `tests/`, `qa/`. | Layered A01–A14 evidence and held-out real trial; adjudicated incremental relevant opportunity, false-merge checks and honest unavailable scope. |
| **P3 R12: reusable structured-HTML recipe/further methods** | R04–R06/R09/R11; XL; optional advanced stage. | Held-out structured publishers collected under reviewed method plus schema-change/unsupported cases; no arbitrary generated code or universal-site promise. |

Foundation through R07 provides the supported-source vertical slice; feedback/general web/HTML expansion must not postpone proving that slice. R11 is a qualification gate, not a last-minute test-writing step. No source/workflow should be removed to make a demo pass. Full limitation→root cause→implementation→file→verification mapping remains in Part 5. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/05_target_architecture_roadmap_and_tests.md#L171-L202]

## 9. Autonomous-search verification

The following are **acceptance requirements, not current passes**. Part 5 specifies preconditions/actions/results/evidence individually. **M:** mocked logic; **CI:** real application/adapter/store against controlled HTTP; **R:** local real end-to-end invocation with actual permitted discovery/collection and no injected source leads/jobs. Controlled loopback fixtures use test transport, not relaxed production host rules.

| Test | Required observable outcome | Verification layer |
| --- | --- | --- |
| A01 Profile, no URLs | Stored intent alone starts finite executable queries and retrieves/persists jobs; no company/query list supplied. | M/CI/R |
| A02 No exhaustive title list | Skills/role intent generates and dispatches positive variants not entered as exact queries; negative controls respected. | M/CI; R for usefulness |
| A03 Previously unknown source | Initial catalog/config lacks source; real discovery evidence produces recognized source identity with provenance. An unseen job URL alone does not pass. | M/CI/**R** |
| A04 Source value | Relevant probe yields vacancy evidence; irrelevant/uncertain/blocked leads have distinct reasons, not fabricated value. | M/CI; R for live value |
| A05 Actual collection | Validated binding makes actual listing/detail calls and returns a vacancy; website recommendation/zero/blocked result fails positive case. | CI/**R** |
| A06 Existing pipeline | Accepted rows, invalid-row accounting, durable observations/checkpoints, matching/readiness and pending projection reconcile; rollback preserves state. | CI; R for real intake |
| A07 Cross-source identity | Two URLs for evidenced same first-party posting form one group; distinct requisitions remain separate; no destructive history rewrite. | M/CI; adjudicated R samples |
| A08 Partial failure | Broken/rate-limited source does not stop eligible others; top-level scanner errors remain visible; access gates respected. | M/CI; R where permitted |
| A09 Degradation | Comparable repeated invalid/schema/quality observations trigger reasoned warning; one valid empty page is not breakage. | M/CI; repeated R qualification |
| A10 Coverage gap | Missing requested cell selects and dispatches further query/source work or records a justified next-run deferral. | M/CI; R gap/action evidence |
| A11 Languages/regions | Tested EN/DE/AR packs produce correct supported parameters/retained fixtures; unsupported locale explicit; real claims tested per locale. | M/CI; R per claimed scope |
| A12 Successive runs | Fresh completed work not needlessly repeated; compatible progress resumes; changed request cannot consume wrong cursor; due refresh happens. | M/CI; repeated R |
| A13 No config editing | Ordinary new profile/supported-source runs leave source/YAML/dependency hashes unchanged, including read-only config control. | CI/R |
| A14 Honest report | Ledger reconciles leads/bindings/attempts/collections, records/groups/evaluation, failures/deferred work and limits; cancellation/restart truthful. | M/CI/R |

**Minimum real proof:** candidate intent → generated query → genuinely previously unregistered supported source discovered through executed evidence → permitted retrieval → normalized durable observations → identity/local-evaluation/report outcome. Preserve starting-state/config hashes, code/intent/adapter versions, task/query/source IDs, network boundary manifest, inspectable permitted response evidence and timestamps, before/after store assertions, and reconciled report. A URL/hash alone proves neither content nor retrieval.

To claim **increased useful coverage**, additionally show at least one adjudicated genuinely additional relevant opportunity from the discovered source against a comparable declared-budget baseline; otherwise state no demonstrated incremental gain. Replay fixed responses for causal comparisons; changing live results are not controlled inputs. Report false merges/uncertain identities, descriptions, locales and blocked/unsearched scope. Do not invent total-market recall. A blocked live trial may prove failure handling, never positive discovery/collection. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/05_target_architecture_roadmap_and_tests.md#L204-L330]

### Evidence limits and final review validation

- Parts 2–5 exercised unchanged baseline regression tests and controlled real methods, not the proposed architecture. Historical successful/blocked samples were not rerun as current provider validation. No new live discovery, model, mailbox, browser, container or sustained scheduler qualification occurred in this final synthesis.
- Final documentation-phase baseline regression: **1764 passed in 50.03s**; JUnit reports 1,764 tests, zero failures/errors/skips, 49.964s, started 2026-10-30T08:55:23.406609+00:00. Existing isolated runtime and disposable execution copy; `pytest -q -p no:cacheprovider` with separate temporary/JUnit paths. A Python socket guard permits loopback and blocks Python non-loopback connects; it is not an OS sandbox or proof of native subprocess network isolation. Provider boundaries are mocked. No dependency installation. This verifies unchanged existing behavior, not A01–A14 or real autonomy.
- Production credentials, approvals/checkpoints, user data and host uptime were deliberately not inspected. Optional runtime/access readiness, multilingual relevance, current remote schemas, real unique-job gain and sustained recovery remain unknown. Earlier static unknowns were upgraded only where later controlled evidence exists; operational unknowns remain open.
- The extracted snapshot is not a Git working tree. Publication is through the connected GitHub integration against the verified remote revision. Preserve original baseline files, all five reports, application/configuration/dependencies and existing data; add only this final critique. No roadmap implementation or proposed acceptance tests were added.

## 10. Recommended next action

**Implement R01 as one narrow engineering change: a truthful run-outcome contract with a regression for the demonstrated top-level scanner failure.** Start at `run_scan.py:57–111` / `scanners/base.py`, carry source/query attempt outcomes into a minimal run receipt, and reconcile its report/exit semantics without changing retrieval or dropping legacy compatibility. Link existing source-run evidence rather than immediately designing a large new state platform.

**First-change acceptance:** inject a top-level JobSpy failure plus a successful independent scanner result; the latter survives, the former is represented, the run is partial/failed rather than error-free, and all declared attempts reconcile. Existing entry points/tests/data remain intact. Use controlled failure tests, then inspect an ordinary local run receipt; no new live-autonomy claim follows from this change alone. The failure itself was directly executed in Part 2. [^https://github.com/shd2w/Jobs_hunter/blob/9a2e910ca91e76e7d3ee6a9101f9c40aa90828b1/docs/jobhunter_autonomy_review/02_search_execution_trace.md#L240-L260]

**Why this first:** it is bounded, addresses a proven defect and provides the evidence contract required to distinguish “found a lead,” “retrieved a job” and “silently failed.” It enables—not replaces—the highest-value capability work: R02/R03 runtime candidate-derived searches and R04/R05 discovery-to-supported-source collection. Do not spend the first release building a general platform or expanding hard-coded URL lists. The next capability milestone is the real supported-source vertical slice in Section 9, not a higher adapter count.
