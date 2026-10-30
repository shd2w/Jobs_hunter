# Part 4 — Autonomy scorecard and root-cause analysis

**Assessment date:** 2026-10-30 UTC. **Repository:** `shd2w/Jobs_hunter`. **Inspected published baseline:** `fd72589708388a2dca41c499cc1adeae229fc803` (Part 3 report commit). All application path/line references below refer to this immutable baseline. No application implementation changed between the three preceding audits and this assessment.

## 1. Executive verdict

**JobHunter is a partially autonomous, known-source job collector—not an independently expanding job-discovery system.** It can start without candidate-supplied websites or exact queries, schedule a finite seeded/approved source set, retrieve bounded results, normalize/store them, and perform conditional local matching. It does not independently generate its retrieval vocabulary from a candidate profile or discover and onboard new websites. This distinction follows the actual coordinator, query builder, source registry and fixed-host collectors, not documentation claims. Evidence: E01–E04, E07, E12 below; Parts 1–3.

The **three most consequential limitations** are:

1. **No executable discovery-to-onboarding path for unknown sources.** Broad missing categories and manual employer/feed/channel management share this cause; they are not all unrelated adapter defects. RC1.
2. **Candidate intent is disconnected from outbound query expansion and early lexical gates.** Useful skills, new terminology and language variants do not cause new searches; some unfamiliar titles are rejected before evaluation. RC2.
3. **No closed-loop coverage/quality control.** Source health and canonical-record counts exist, but they do not identify missing search space or drive useful-opportunity prioritization; separate persistence/evaluation populations also make those counts incomplete outcome evidence. RC3, amplified by RC4.

These are architecture-level conclusions with direct source/controlled-execution support. Their impact on **real unique suitable jobs missed** remains unmeasured. Access permissions, API costs, eligibility uncertainty and explicit candidate exclusions are legitimate constraints, not defects to remove.

## 2. Assessment method and scope

### Prior reports read and reconciled

- [Part 1 — repository map](https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/docs/jobhunter_autonomy_review/01_repository_map.md): entry points, closed retrieval paths, source/test inventory and original unknowns.
- [Part 2 — execution trace](https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/docs/jobhunter_autonomy_review/02_search_execution_trace.md): Sections 3–7 trace the actual stages, controlled transformations, scheduling and failure branches; Sections 8–9 bound autonomy claims.
- [Part 3 — source coverage/manual inputs](https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/docs/jobhunter_autonomy_review/03_source_coverage_and_manual_dependencies.md): source matrices, 28 input dependencies (M01–M28), reuse boundaries and historical-versus-current verification.

Their local bytes match the published baseline. Part 1's inferred error/population risks were subsequently exercised in Part 2; this assessment uses those stronger results. Part 3's “implemented and verified” labels explicitly mean offline fixture scope, **not currently live verified**. Recorded 2026-10-29 provider samples remain historical evidence, not tests rerun in this phase.

**Working boundary:** `/data/jobhunter-autonomy-part2/snapshot` is an extracted archive, not a Git working tree; no local Git-status assertion is made. Execution uses its separate disposable copy and the existing isolated runtime. No private profile, production source state, credentials or existing user data was read or changed. No live provider/browser/cloud/mailbox call, paid service or application action was initiated.

### Scoring rules

The requested scale is applied literally:

| Score | Meaning |
| --- | --- |
| 0 | Absent: no meaningful implementation of the named capability. |
| 1 | Manual: the user/developer supplies the relevant knowledge, instructions, sources or configuration. |
| 2 | Partially automated: some relevant work is automatic, substantial manual intervention remains. |
| 3 | Mostly autonomous: normal **stated-scope** cases run automatically, with important limitations. |
| 4 | Highly autonomous: independently performs most of that workflow and manages routine exceptions. |
| 5 | Operationally autonomous: end-to-end behavior demonstrated under realistic conditions. |

- Scores are **ordinal engineering judgments**, not measured percentages, reliability estimates or equal-interval quantities. No arithmetic average, aggregate “autonomy percentage,” or radar/chart is used: a strong parser cannot compensate mathematically for absent source discovery.
- Score the named workflow, not the mere presence of a package. Static term expansion is useful execution automation but not independent semantic query generation. A directory link is not discovery; a new posting URL is not a newly onboarded website.
- Source collection and user-facing evaluated opportunities are distinct scopes. A 3 for normal configured retrieval does not imply 3 for whole-system discovery or a live operational guarantee.
- **S:** source inspected now. **T4/C4:** tests/controlled checks executed in Part 4. **T2/C2, T3/C3:** prior executed evidence, attributed to its phase. **H:** recorded historical sample. **I:** reasoned impact, not a measured loss. **U:** live behavior/quality/coverage not established.
- Evidence confidence describes the cited implementation boundary, not current service availability. No dimension merits 5; absence of realistic evidence is not itself proof that every live source fails.

## 3. Autonomy scorecard

Each next-level requirement is a **minimum acceptance criterion for that dimension**, not an implementation plan or a promise that one change alone earns an upgrade.

| # / dimension | Score and current capability | Supporting evidence; why not higher | What is needed for the next level |
| --- | --- | --- | --- |
| 1. Search-query generation | **1 / 5 — Manual semantic vocabulary, automatic expansion.** Configured strings expand into provider queries without per-query clicking. | E01; S, C2, C4. `_load_searches/_load_primary` consume YAML terms/locations; profiles do not create outbound terms. Empty pages advance existing entries. Neither preferred terms nor local AI ranking supplies a retrieval planner. Score 1 assesses *deriving what to search*, not formatting a request. | **To 2:** automatically derive bounded candidate-evidence-based query candidates for existing providers; demonstrate an appropriate previously unconfigured title/skill/language variant is actually queried without user wording. Preserve explicit exclusions and show provenance; user review can still be needed. |
| 2. Independent source discovery | **0 / 5 — Absent.** Selection of seeded/registered sources is automated, discovery of new source candidates is not. | E02; S, C3. `directory()` returns search links; `register()` accepts already known kind/identifier; coordinator only visits registered rows. External human browser searching is not an implemented discovery engine. | **To 1:** an explicit human-directed discovery workflow must execute permitted lead acquisition and retain evidence-backed unregistered source candidates, not merely output a Google URL. This is still manual direction, not autonomous onboarding. |
| 3. Discovery of previously unknown websites | **0 / 5 — Absent as a website-discovery capability.** Unseen posting URLs can be returned by known boards. | E03; S, C3. Fixed Scrapling hosts/path rules and kind validation do not traverse arbitrary domains or promote job URLs into new sources. No first-party site/ATS recognition path was found. Unknown result URLs must not be counted as independently discovered websites. | **To 1:** given an operator-directed lead/search, identify and validate a previously unconfigured first-party careers site/ATS/feed and retain provenance. Merely accepting a human-supplied board ID does not establish website finding. |
| 4. Source integration and extensibility | **2 / 5 — Reusable adapters, manual onboarding.** New supported ATS IDs/feeds can use existing collectors. | E04; S, C3. New synthetic employer IDs worked for Greenhouse, Lever, Ashby and SmartRecruiters without code changes; no automatic ID resolution. Workday needs explicit tenant/board configuration; unsupported protocols/HTML need developer work. | **To 3:** normal newly identified supported ATS/feed sources can be recognized, validated and registered with little operator source-management work, with required consent/setup retained. Demonstrate discovery-to-intake for a held-out supported employer, not only a hand-entered ID. |
| 5. Search breadth across source categories | **2 / 5 — Multiple implemented families, uneven usable breadth.** General boards, ATS, remote feeds, USAJOBS, HN and scoped social APIs exist. | E05; S, T4, C3. 30 registered kinds include duplicate publisher mechanisms, not 30 independent publishers. Agency/academic/NGO/startup/niche coverage is generally indirect; social/institutional routes need setup; directory-only platforms are not adapters. Current live breadth U. | **To 3:** ordinary relevant category coverage is selected and searched with limited manual setup, with explicit unsupported/inaccessible scope. Demonstrate representative category flows and useful contribution under actual deployment constraints; adding names or adapter counts is insufficient. |
| 6. Global and multilingual discovery | **2 / 5 — Partial regional and lexical support.** Configured regions/providers and selected multilingual post rules are real. | E06; S, T4, C2. English/German query vocabulary; selected English/German/Arabic extraction; regional provider scopes do not generate native-language queries. USA defaults, remote-country restrictions and static title filtering remain. No global/language recall benchmark. | **To 3:** normal targeted locales get candidate-intent-derived local vocabulary, correct provider/country handling and evidence-backed source selection without manual translation lists; validate multiple language/region cases, including unfamiliar titles and non-worldwide remote roles. “Global” must stay bounded to supported tested locales. |
| 7. Job retrieval and normalization | **3 / 5 — Mostly automatic within known configured/approved source contracts.** Retrieval, bounded continuation, normalization, intake and completion state are implemented. | E07; S, T4, C2/C3. Many ordinary fixture paths run without per-job intervention. Missing descriptions, schema/access changes, required setup and static limits remain; no arbitrary-site extraction or current live reliability claim. This is the strongest collection capability, not end-to-end autonomy. | **To 4:** demonstrate sustained representative collection with routine transient failures and incomplete descriptions handled or explicitly escalated without routine developer intervention; maintain transactional continuation and show source changes do not silently become successful empty scans. No permission bypass. |
| 8. Cross-source deduplication | **2 / 5 — Automatic canonical-URL identity, legacy heuristics, manual aliases.** | E08; S, T4, C2, C4. Same canonical URLs merge observations; distinct syndicated URLs do not automatically resolve in SQLite. Legacy company/title/location heuristics are a separate decision path. C4 same fixture fields at two canonical URLs remained two records. No measured precision/recall for true vacancy identity. | **To 3:** demonstrate mostly automatic cross-URL vacancy resolution on labeled syndicated/reposted/distinct-location examples, preserve provenance and avoid false merges; reconcile identity semantics across stores. Human review for ambiguous cases remains appropriate. |
| 9. Identification of source-coverage gaps | **1 / 5 — Human assessment aided by local telemetry.** | E09; S, C3. Registered-source health, pending/partial state, canonical insert counts and manual priority hints exist. No comparison of candidate-required categories/locales/search space to actually searched scope; no detection of unknown missing publishers. A warning about bounded snapshots is not a gap-finding algorithm. | **To 2:** automatically compare an explicit intended search scope against observed query/category/locale/source execution; produce actionable missing/untested/blocked-scope records distinct from zero results and known-source failure. Full web recall need not be solved at this level. |
| 10. Adaptive source prioritization | **2 / 5 — State-aware scheduling, not value learning.** Approvals, readiness, due times, oldest-run order and publisher gates alter eligibility/order. | E10; S, T4, C4. Fairness/freshness-aware orchestration earns partial credit; it does not learn relevance/novelty yield. Swapping synthetic `new_unique_jobs` values did not change real `cycle()` ordering. Fixed ten-attempt budget, label tie-breaks and shared gates remain. | **To 3:** under a fixed authorized budget, automatically adjust eligible-source priority using validated contribution/relevance/freshness and uncertainty while preserving exploration/fairness and provider gates. Demonstrate value changes affect choices; synthetic metrics alone do not prove real coverage improvement. |
| 11. Detection and recovery from broken sources | **2 / 5 — Useful detection/isolation and specific recovery, not general self-repair.** | E11; S, T4, C2. Structured source health, cancellations, committed checkpoints, interrupted-run reconciliation and due Jobicy expiry restart exist. Layout failures, setup/access revocation and many resets remain manual. CLI top-level JobSpy exception accounting is weaker than source-run health. | **To 3:** routine permitted transient/cursor/runtime problems recover or escalate consistently across entry points with truthful terminal status; demonstrate one failure does not prevent others and repaired scans resume safely. Permission-denied sources still require valid reauthorization; do not “heal” by bypassing blocks. |
| 12. Reduction of unnecessary user input | **3 / 5 — Mostly automatic for the seeded known-source path.** Blank-profile collection and scheduled checks need no website list or exact query. | E12; S, T4, C2/C3. Defaults remove initial URL burden, but expanding beyond them requires board IDs, tenant endpoints, feed/channel scopes and vocabulary maintenance. Some manual inputs are genuine consent/preferences, others are search-engine source-management work. | **To 4:** normal personalization and expansion within supported source families work from legitimate candidate intent rather than website/company/query lists; automatically manage routine IDs/feed/thread resolution and setup diagnostics. Keep candidate preferences, credentials, budget and ambiguous evidence decisions explicit. |
| 13. End-to-end autonomy verification | **2 / 5 — Extensive synthetic verification plus limited historical live samples.** | E13; T2/T3/T4, C2/C3/C4, H. Real pipeline methods were traced using controlled transports; historical bounded provider samples exist. No demonstrated realistic profile-to-new-query-to-unknown-source-to-useful-evaluated-opportunity run, sustained deployment trial or multilingual/unique-opportunity recall assessment. | **To 3:** run reproducible representative ordinary workflows with real permitted collection, truthful source failures and persisted usable outcomes, minimal operator intervention and explicit setup/coverage limits. This does not yet earn 5: operational autonomy additionally requires sustained realistic new-source/query, exception and outcome verification. |

### Calibration and confidence

- **Why query generation is 1 rather than 0 or 2:** request templating/cross-products exist, so the subsystem is not absent; the substantive vocabulary is authored outside the candidate profile. Part 2's profile-change and Part 4's empty-result probes establish this boundary. Giving 2 merely for combining manual strings would overstate the named capability. E01.
- **Why scheduling is 2 but gap identification only 1:** the scheduler automatically acts on liveness/time/setup state; humans must infer strategic coverage gaps. Neither score asserts yield-learning. E09–E10.
- **Why retrieval/input reduction can be 3 while realistic verification is 2:** normal configured cases have source and executed contract evidence. Their operational live performance remains U and is explicitly not scored as demonstrated end-to-end independence. E07, E12–E13.
- **Why two dimensions are 0 despite reusable new IDs:** accepting a known identifier is integration, not finding a source or a website. They are assessed separately to avoid inflating discovery from successful intake. E02–E04.
- Confidence is high in these implementation boundaries, supported by the closed call paths and controlled checks. Exact ordinal ratings are judgments; real-world coverage/value implications are provisional. No weightings or monetary/job-count benefits are invented.

## 4. Evidence register

Each item identifies exact files, relevant symbols/keys and lines. Citations point to the inspected commit; they are source evidence, not claims of live success. Prior executed observations are explicitly attributed.

### E01 — Retrieval vocabulary has no profile-generation loop

- `scanners/jobspy_scanner.py:53–117`, `JobSpyScanner._load_searches/_load_primary`: primary literal `terms` × `locations`, provider overrides and copied explicit entries. `_do_search:173–231` formats outgoing arguments/country/template. `config/portals.yml:136–195` supplies the finite vocabulary and provider scopes. **S.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/scanners/jobspy_scanner.py#L53-L117]
- `jobhunter_app/expanded_sources.py:33–53`, `collect`: bounded raw-row pagination and modulo query rotation; no zero-yield expansion. **S/C4:** two fake empty provider pages queried AI Engineer/Oman then AI Engineer/Egypt, checkpoints 1 then 2; no new term. **C2:** changing a synthetic profile skill did not change the search registry. [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/expanded_sources.py#L23-L53]
- `jobhunter_app/store.py:149–178`, `save_profile`; `jobhunter_app/matching.py:57–118`, `match_job`; `jobhunter_app/semantic.py:153–172`, `rank`: downstream matching/reranking, not new queries. `utils/filters.py:22–56`, `TitleFilter.matches`, uses title-only literals. C2's unfamiliar skill-bearing title was rejected in JobSpy, retained in native/Scrapling SQLite paths. **S/prior C2.**

### E02 — Selection does not acquire new source leads

- `jobhunter_app/automatic.py:17–39,54–85`, `STARTERS/configure`, inserts known source records; `AutomaticDiscovery.cycle:171–195` iterates registered approved/due IDs. `jobhunter_app/sources.py:255–261`, `register`, only validates/upserts supplied kind/identifier. **S.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/automatic.py#L17-L85]
- `jobhunter_app/source_directory.py:26–34`, `directory`, constructs Google links, not network requests. **C3:** 44 directory entries, zero external requests, no new registered sources. `jobhunter_app/saved_searches.py:67–72`, `run`, searches existing stored jobs only. **S/prior C3.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/source_directory.py#L26-L34]

### E03 — Unknown-domain discovery is outside collector scope

- `jobhunter_app/scrapling_engine.py:10–38`, `SOURCES/validate_source/safe_url`, permits only Jobicy/Arbeitnow fixed hosts and paths; `selector:41–47` uses `adaptive=False`. Detail/page discovery stays within those scopes. `jobhunter_app/authorized_boards.py:14–49`, `HOSTS/safe_url`, restricts Wuzzuf/Naukrigulf listings/details. **S/T4.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/scrapling_engine.py#L10-L47]
- `jobhunter_app/sources.py:97–148`, `Source.__post_init__/url`, is a closed kind/ID-to-endpoint mapping. `fetch:156–190` dispatches known methods, not ATS recognition from arbitrary URLs. C3 rejected unknown kinds/altered fixed IDs. An external vacancy URL in a normalized record is not added to `sources`. **S/prior C3; no universal impossibility claim about unrelated code.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/sources.py#L93-L190]

### E04 — Known adapter families can be extended manually

- `jobhunter_app/sources.py:132–139,193–261`, `Source.url/normalize/register`; `jobhunter_app/collection.py:48–65`, `collect` SmartRecruiters branch. **C3:** `AuditNewEmployer` worked through real dispatch/normalization/SQLite for Greenhouse, Lever, Ashby and SmartRecruiters with fake API bodies; one valid insertion each. This is neither live employer verification nor automatic ID finding. [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/sources.py#L193-L261]
- `scanners/workday.py:64–105,256–261`, `DirectAPIScanner._load_companies/_get_search_terms`, needs tracked-company config and explicit supported Workday endpoint/base URL; default `config/portals.yml:133` is empty. Unknown company does not add a query or endpoint. Separate generic SmartRecruiters source registration is more reusable than legacy Bosch mapping. **S/prior C3.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/scanners/workday.py#L64-L105]

### E05 — Breadth exists, with gaps and shared publishers

- `jobhunter_app/sources.py:18–58`, `POLICIES`; `scanners/jobspy_registry.py:2–9`, `SITES/SCOPES`; `jobhunter_app/platform_posts.py:9–42,91–112`, `KINDS/REQUIRED/collect`. Part 3 enumerated 30 kinds and classified every required family. Social routes read explicit organization/user/subreddit/channel scopes, not platform-wide hiring search. **S/prior C3; T4 fixture contracts.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/platform_posts.py#L9-L42]
- `jobhunter_app/source_directory.py:15–23` contains manual/indirect agency, institutional, freelance/startup/Himalayas guidance, not new adapters. `jobhunter_app/source_health.py:8–14`, `provider_family`, aliases native and Scrapling Jobicy/Arbeitnow for shared gating. Categories/adapters cannot be added up as independent measured coverage. **S.**

### E06 — Regional settings and narrow language rules are not global discovery

- `config/portals.yml:136–195`, `jobspy_searches/jobspy_providers`, literal English/German terms and configured regions; `scanners/jobspy_registry.py:3–9` constrains provider geography. `scanners/jobspy_scanner.py:184–207` country inference can fall back to USA, remote flag does not establish geographic eligibility. **S.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/config/portals.yml#L136-L195]
- `jobhunter_app/posts.py:10–79`, `LABELS/HIRING/extract`, selected English/German/Arabic rules; `jobhunter_app/matching.py:115–116` explicitly bounds requirement language cues. `tests/test_discovery.py:48–61` checks selected examples, not cross-language recall. `utils/filters.py:22–56` can reject unfamiliar title text before descriptions help. **S/T4/prior C2.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/posts.py#L10-L79]

### E07 — Substantial automatic retrieval/normalization after setup

- `jobhunter_app/sources.py:156–190,193–252,309–354`, `fetch/normalize/_scan_locked`, has adapter dispatch, normalization, atomic jobs/posts/checkpoint/completion. `jobhunter_app/validation.py:33–53`, `normalize_job`, requires title/company/public canonical URL, permits absent description. `jobhunter_app/collection.py:34–118` and `jobhunter_app/scrapling_engine.py:112–167` implement bounded continuation. **S/T4/prior C2/C3.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/sources.py#L309-L354]
- `run_evaluate.py:143–215`, `evaluate_job`, may need cache/static fetch/conditional rendered text and leave failures pending. `jobhunter_app/feeds.py:32–82` and `jobhunter_app/posts.py:229–299` may need review for incomplete supplied/feed content. No generic recovery to arbitrary schema/description exists. **S/T4; real browser/model performance U.**

### E08 — Identity is not universally shared across sources/stores

- `jobhunter_app/store.py:185–229`, `Store.ingest`, hashes canonical URL unless a human-linked alias exists, updates sightings and preserves richer fields. **C4:** two identical synthetic vacancy field sets at `example.org`/`example.net` canonical URLs inserted separately; a tracking variant of the first updated it. Stored canonical rows: two. No real duplicate-rate estimate. [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/store.py#L185-L229]
- `utils/dedup.py:43–99,101–142`, `DeduplicatorStore` history/URL/company-role-location checks, applies different legacy heuristics. `jobhunter_app/posts.py:147–181,277–285` supports explicit reviewed identity/conflict decisions. Same-URL behavior is verified; semantic vacancy sameness and false-merge/missed-merge rates U. **S/T4/C4.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/utils/dedup.py#L101-L142]

### E09 — Local telemetry is not source-universe gap detection

- `jobhunter_app/source_health.py:29–51`, `health`, iterates registered sources and reports last run, gates, checkpoints, stale observations and `manual_priority_hint`. `jobhunter_app/sources.py:339–347` defines `new_unique_jobs` from inserted rows, not independently verified employer vacancies or relevance. **S.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/source_health.py#L29-L51]
- `jobhunter_app/expanded_sources.py:48–53` exposes finite query counts and `coverage_complete=False`; public-feed `coverage_complete=True:75–76,96–97` means current response only, not the broader job universe. `directory:26–34` outputs predefined categories; it does not compare them to profile-required/actually executed scope. **S.** Absence conclusion is scoped to the inspected coordinator/collector/directory feedback paths.

### E10 — Prioritization uses time/gates, not utility feedback

- `jobhunter_app/automatic.py:164–202`, `AutomaticDiscovery.cycle`, sorts `last_run`, seeded label order, ID; skips unapproved/unready/not-due sources and caps ten attempts. `status:152–156` displays `new_unique_jobs`, but `cycle` does not rank with it. **S/C4:** with two fake eligible health rows and real cycle control flow, swapping yield values 0/100 to 100/0 left older-first order unchanged; actual `scan` stubbed. [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/automatic.py#L164-L202]
- `tests/test_automatic.py:167–176` exercises fairness over extra registrations with synthetic scan updates; Part 2 R3 exercised unchanged starters over two fixture cycles. Those establish limited rotation, not starvation-free real-world scheduling or optimal source value. **T4/prior C2.**

### E11 — Recovery is policy-aware but incomplete across paths

- `jobhunter_app/sources.py:367–419`, `_scan_locked` exception handling: source isolation, structured failures, quota/access pauses and gates. `jobhunter_app/store.py:108–130`, `recover_interrupted_runs`, reconciles abandoned records under lock. `jobhunter_app/automatic.py:188–195` specifically restarts an expired due Jobicy cursor. **S/T4.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/jobhunter_app/sources.py#L367-L419]
- `jobhunter_app/source_health.py:54–60`, `reset`, clears checkpoint, not authorization/gates; `jobhunter_app/board_browser.py:13–47` requires explicit setup/transport. `run_scan.py:89–96,171–172`: C2 executed top-level JobSpy failure yielded logged error but `errors=[]`, exit 0 when no jobs. Ordinary per-query exceptions are different; do not generalize this to all source failures. **S/prior C2.**

### E12 — Starter automation is genuine; expanded scope still needs source work

- `jobhunter_app/automatic.py:54–85,119–139,164–208`, `configure/start/check/cycle`, blank-profile setup, approved due scans and conditional matching. `run_local.py:250–253` enables automatic server mode unless manual discovery selected. Custom approved sources can also join coordinator scans. **S/T4/prior C2/C3.**
- `jobhunter_app/sources.py:93–148` still needs explicit nonstarter identifiers; `jobhunter_app/platform_posts.py:17–42` requires scopes/environment access; `jobhunter_app/collection.py:92–117` needs USAJOBS query/key or HN story ID. Part 3 M01–M28 distinguish preferences/authorization from avoidable website/query maintenance. **S.**

### E13 — Validation evidence is layered, not a realistic autonomy trial

- Part 2 Sections 1/4–7 and Part 3 Section 7 document tests and controlled boundaries. Part 4 rechecks score-critical paths and reruns regression tests (Section 8). `tests/test_all_jobspy_platforms.py:39–61` replaces provider calls; `tests/test_scrapling_engine.py:17–55` uses synthetic HTML; `tests/test_platform_posts.py:39–64` uses configured test settings/fake API payloads. **S/T4, not live integration proof.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/tests/test_all_jobspy_platforms.py#L39-L61]
- `docs/JOBSPY_ALL_PLATFORMS_VERIFICATION.json:1–242`, `docs/SCRAPER_VERIFICATION.json:399–414`, `docs/SCRAPLING_PRIMARY_VERIFICATION.json:1–126` record bounded successes/failures on 2026-10-29. They neither show the missing unknown-source/query stages nor sustained operator-independent outcomes. **H; current live access U.** [^https://github.com/shd2w/Jobs_hunter/blob/fd72589708388a2dca41c499cc1adeae229fc803/docs/JOBSPY_ALL_PLATFORMS_VERIFICATION.json]

## 5. Root causes versus downstream symptoms

### 5.1 Causal analysis

| ID / direct cause | Evidence and established boundary | Downstream symptoms / affected workflows | Confidence and what is not established |
| --- | --- | --- | --- |
| **RC1 — No independent source-lead acquisition, site recognition and onboarding mechanism.** Registry selection starts after source identity is known. | E02–E04: fixed seeds, closed kind/endpoint dispatch, directory-only search links, manual IDs/URLs. This is missing functionality, not a defect in an existing crawler. | Missing agency/academic/NGO/portfolio/niche sites; user resolves ATS/feed/channel scope; unknown employers cannot join autonomously even when their ATS is already reusable. | **S/C3, high boundary confidence. I:** likely broad coverage opportunity. Number of additional reachable useful employers/jobs is U. No claim every missing platform is feasible or authorized. |
| **RC2 — Retrieval intent/vocabulary and early acceptance policy are maintained separately from candidate evidence.** No general profile-to-query/variant loop; static title/location gates. | E01/E06: literal lists, downstream-only matching, no rewrite after empty pages, title-only filtering. Native/Scrapling intake bypasses that prefilter for SQLite, so this is path-dependent. | Manual title/translation maintenance, missed unfamiliar terminology before evaluation, irrelevant searches repeated, regional country/remote assumptions. Adding an alias only to local ranking cannot recover a job never fetched/retained. | **S/C2/C4.** Concrete synthetic rejection verified; real false-negative rates U. Static exclusions may correctly express intent; not every rejected title is a bug. |
| **RC3 — No closed-loop model of intended versus observed coverage or useful source contribution.** Telemetry does not feed strategic planning. | E09/E10: counts/health over registered rows; oldest-run scheduling; yield-swap probe unchanged order; finite query rotation. No target-scope gap comparison or value-learning control in mapped paths. | No automatic response to under-covered locales/categories; weak distinction between “source ran” and “useful new opportunities found”; repeated low-yield scope, manual prioritization. | **S/C4. I:** potential wasted budget/missed novelty. No benchmark proves current fairness policy performs badly or a yield optimizer would improve recall. A simple fixed policy is not itself a defect. |
| **RC4 — Identity, acceptance, persistence and completion contracts differ across orchestration paths.** | E07/E08/E11; `run_scan.py:69–111`, `jobhunter_app/sources.py:326–365`, `run_all.py:77–104`: SQLite versus filtered legacy records, post-commit mirror, URL versus heuristic identity, evaluator/export gates. | A collected job need not be a pending/evaluated legacy job; repeated syndicated URLs can inflate canonical novelty; CLI summary may hide a scanner-wide failure; no-new legacy additions can skip pending evaluation. These obscure autonomous outcome evidence and any feedback built on raw counts. | **S/C2/C4.** Distinct populations, canonical-URL duplication and named gates verified. Actual production stale queues, mirror-failure incidence, true duplicate rates and lost opportunity volume U. Not every difference requires one universal store. |
| **RC5 — Source-specific collection and operational lifecycle remain manually qualified/maintained beyond limited supported contracts.** | E03/E04/E07/E11: fixed schemas/hosts, optional runtimes, authorized APIs/scopes, explicit browser choice, no general schema repair/fallback; specific checkpoint/Jobicy recovery exists. | New unsupported sites need adapters; layouts/schema changes need developer review; some access/setup/expired scopes need operator help; initial breadth decays if unsupported failures are not addressed. | **S/T4.** General maintenance gap verified; upstream failure frequency U. Permission/cost gates and deliberate scope limits are **not** architectural mistakes. No suggestion to bypass them. |
| **RC6 — Qualification evidence does not cover the desired autonomous outcome under representative conditions.** | E13: strong fixture suite, controlled methods and historical samples; missing realistic candidate-intent → new query/source → useful stored/evaluated outcome trial. | Documentation/adapter counts risk being mistaken for readiness; operational weak points and relevance/recall cannot be ranked empirically; score 5 cannot be justified. | **S about reviewed evidence; U about deployment.** This is an assurance gap, not proof of a hidden runtime defect. More tests alone will not supply RC1/RC2 missing implementation. |

### 5.2 Concrete causal chains (not additional independent defects)

- **RC1 → no new source identity → no reusable ATS registration → user supplies company/board/feed lists → missing source-category breadth.** Writing a new adapter for each absent category would not, by itself, solve the shared discovery cause. E02–E05.
- **RC2 → finite vocabulary/early lexical exclusion → unfamiliar role absent from retained pool → downstream matcher/AI cannot rescue it.** The candidate's local relevance intelligence does not move upstream. E01/E06/E07.
- **RC3 + RC4 → canonical-record novelty/health not equal useful vacancy coverage → scheduler lacks validated utility signal → manual strategic prioritization persists.** Repairing measurement and identity assumptions precedes credible value optimization. E08–E10.
- **RC5 → source returns blocked/changed-format/setup error → deliberate stop/health state → operator/developer review, not self-healing.** This preserves access constraints; only avoidable routine recovery should become more automatic. E11.
- **RC6 → missing realistic qualification → uncertain severity of field failures.** This does not create the absent discovery mechanism; it limits confidence about operational value of all other improvements. E13.

### 5.3 Prioritization across the requested factors

**Interpretation:** ordinal priority below is engineering judgment, not a computed economic ranking. Severity refers to the requested independent-discovery objective. Unique-job effects and expected value are hypotheses grounded in mechanisms, not measured gains. Difficulty is relative/provisional; no person-day estimate or external-service feasibility is asserted. Dependencies identify capabilities/evidence needed before benefit can be demonstrated.

| Priority / cause | Severity and affected workflows | Expected unique-job coverage impact | Manual burden imposed | Relative implementation difficulty | Dependencies and expected value |
| --- | --- | --- | --- | --- | --- |
| **1 — RC1, missing discovery/onboarding** | **Critical** for unknown sites/employers; affects ATS, feeds, agencies/institutions, communities and category expansion. | **Potentially very high, unmeasured:** increases reachable source universe rather than repeatedly scanning the same one. | **High recurring source-management effort:** find URLs/IDs/threads/scopes, classify method, register/approve. | **High:** lead quality, provenance, first-party recognition, capability/permission validation; arbitrary sites not uniformly collectible. | Reuse existing ATS/feed adapters first; combine with RC2 for relevant leads and RC5 for access/capability checks. High expected structural value; adapter expansion without discovery has weaker leverage. |
| **2 — RC2, intent/query/filter disconnect** | **Critical** for personalized and unfamiliar/multilingual opportunities on both existing and future sources. | **Potentially high, unmeasured:** can reveal/retain useful roles on already reachable sources, not necessarily new websites. | **High vocabulary maintenance**, manual overrides, translations, exclusions/query reconciliation. | **Medium–high:** evidence-grounded generation, provider syntax/geography and safe filtering validation. | Can improve existing-provider search before RC1 is complete; needs explicit candidate intent and feedback evidence. High expected early leverage without pretending AI ranking is retrieval. |
| **3 — RC3, missing coverage/value feedback** | **High**, cross-source query selection, source scheduling, gap triage and bounded budgets. | **Potentially high but conditional:** better allocation/expansion; improvement over fairness baseline not demonstrated. | **Medium–high recurring analysis** of logs/source value/unsearched scope. | **High:** define intended scope, correct novelty/relevance signals, exploration and constrained scheduling. | Depends on RC4's trustworthy identity/outcomes; RC1/RC2 provide expansion actions. Expected value grows after those exist. Do not learn from raw inserted counts as if labeled useful vacancies. |
| **4 — RC4, inconsistent identity/outcome contracts** | **High** for retained/evaluated delivery and truthful monitoring across CLI/dashboard/legacy paths. | **Indirect but consequential:** avoiding duplicate effort, hidden failures and skipped work; not automatically increasing external reach. | **Medium–high reconciliation/diagnosis**, manual linking/re-running/review. | **Medium–high**, incremental contracts and compatibility tests; wholesale replacement not required by evidence. | Important prerequisite for RC3 and RC6. Narrow error-reporting/gate checks can be addressed independently of a discovery redesign. Expected value is trustworthy outcomes and measurement. |
| **5 — RC5, limited automatic source lifecycle** | **High for affected providers**, narrower than RC1/RC2; new unsupported hosts and changing formats/runtime/access. | **Variable/unmeasured:** restores permitted accessible coverage; cannot repair unavailable rights or nonexistent APIs. | **High per affected integration**, often developer rather than candidate effort. | **Medium to high per provider**, externally constrained; no universal safe repair method established. | Explicit access/runtime capabilities, fixtures and representative validation. Existing retry gates/checkpoints/expiry handling reduce starting burden. Prefer supported-route reuse over arbitrary crawling. |
| **6 — RC6, realistic qualification gap** | **High assurance severity**, all workflows; not itself an external retrieval algorithm. | **Unknown direct gain:** enables honest measurement and prevents unsupported autonomy claims. | **Current hidden validation/triage burden**; future test-operation effort remains necessary. | **Medium–high**, representative fixtures/live scope, permissions, duration, labeled outcomes and repeatability. | Establish baseline experiments now; operationally qualify each implemented improvement. Not a reason to defer easy truthfulness checks until a large redesign. Expected value is confidence and evidence-driven prioritization, not an invented job-count uplift. |

**Priority is not a mandatory waterfall.** RC1/RC2 are the main product capability gaps. Narrow RC4 observability corrections, RC5 readiness checks and RC6 baseline qualification can be investigated in parallel in later phases, without waiting for or implementing a replacement system here.

## 6. Manual-input impact

Part 3 inventories every discovered dependency as M01–M28. This section groups their autonomy impact rather than repeating that source matrix. No measured user-time savings or workload totals are available.

| Input class | Who supplies it now / Part 3 references | Impact on autonomy | What is avoidable versus legitimately retained |
| --- | --- | --- | --- |
| Candidate skills, role intent, geography, exclusions, constraints | Candidate; M01, candidate-intent portion of M03/M04 | Determines relevance; not equivalent to a source/query list. Blank profile still allows generic seeded collection. | **Retain accurate intent and corrections.** Avoid asking the candidate to translate that intent into exhaustive board-specific strings. RC2. |
| Titles, synonyms, translations, provider-country mappings, low-yield query repair | Developer/operator, sometimes candidate; M02–M06/M12/M28 | Finite manually maintained retrieval universe; languages/terminology missing from that universe do not expand themselves. | **Avoidable source-engine work in principle**, not currently eliminated. Needs generated/validated retrieval vocabulary and feedback; preserve legitimate explicit exclusions. RC2/RC3. |
| Websites, employer/ATS identifiers, tenant endpoints, feed URLs, listing/thread IDs, source lists | Operator/developer, often displaced onto candidate; M07–M17 | No automatic lead-to-supported-collector handoff; substantial expansion work even when a reusable collector exists. | **Avoidable routine source-management input**, where discovery/recognition is feasible. Favorite employers are optional legitimate preferences, not a required exhaustive employer list. RC1/RC5. |
| Community/account/channel scopes and memberships | Operator/candidate; M18 | Timelines/channels need prior identification; not global hiring search. | Finding relevant *public permitted* candidates can be automated in principle; **do not infer membership, join rights or access**. RC1/RC5. |
| Credentials, API authorization, consent/version/cost settings, source approval | Authorized operator; M17/M19/M23 | Some sources remain unavailable until setup; flags alone do not grant remote entitlements. | **Retain genuine authorization/cost decisions.** Automate readiness/expiry diagnostics and permitted onboarding, not consent or fabricated credentials. RC5. |
| Files/copied posts/newsletters, field mapping, origin/application evidence | User/operator; M20/M21 | Intake works only after acquisition; generic content may not be a complete vacancy. | Avoid copying/mapping where authorized direct/feed retrieval exists; otherwise content rights/evidence remain necessary. **Mail ingestion is absent**, not a required route secretly configured elsewhere. RC1/RC5. |
| Ambiguous/conflicting content confirmation and reviewed alias links | Human reviewer; M22; E08 | Rules can auto-add complete source-backed posts but cannot establish every uncertain identity/role. | Reduce avoidable review with better structure/corroboration; **retain uncertainty/conflict review**. Do not invent fields or merge distinct roles for a higher autonomy score. RC4/RC5. |
| Manual scan/batch picks, runtime/browser setup, quota/access review, checkpoint/schema repair | Operator/developer; M23–M28 | Automatic coordinator already removes repeated scan selection for approved due sources. Other setup/repair remains source-specific. | Automate routine preflight/permitted recovery; **respect pauses, Retry-After, denied access and deliberate browser choice**. A blanket claim “all recovery is manual” would be false. RC5. |

**Not necessary even today for the starter path:** hundreds of website URLs, exact per-search terms, company lists, cloud-model credentials, social tokens, CV upload, or repeated scan clicks. Existing defaults already supply the finite universe. Expanding/personalizing that universe is where the system still delegates avoidable search-engine work to humans. Evidence: E01/E02/E12 and Part 3 M01–M28.

## 7. Direct answers to the requested verdict questions

### What can JobHunter autonomously discover today?

**New job records within already known and permitted source/query scope.** In automatic server mode it seeds 16 source routes, schedules approved due registrations, makes bounded JobSpy/native/feed/fixed-Scrapling requests, follows implemented checkpoints, normalizes/persists returned data, and conditionally matches meaningful profiles. It can receive unseen employers/URLs in those results without a user naming every posting. It does **not** infer independent source discovery from that fact. Actual live provider availability and relevance remain U. E01–E03/E07/E12; prior C2/C3, T4.

### What can it only search after manual configuration?

Nonstarter employer ATS boards, public Workday tenant/board endpoints, new feeds, supported authorized board listings, HN thread IDs, USAJOBS keyword/access, official organization/user/subreddit/channel scopes, optional browser/runtime and unsupported query vocabulary. After a supported source is registered/approved and setup is complete, it may join automatic scheduling; it does not require manual clicking forever. Unsupported sources need an adapter/method, not just configuration. E04–E06/E11/E12; Part 3 matrices/M07–M28.

### Can it discover a website absent from all existing configuration?

**No implemented independent website-discovery/onboarding path was found.** A known board can return a new offsite job URL/company; fixed-host crawlers discover permitted detail links. Neither case validates/classifies/registers that domain as a new searchable source. Directory links require outside human search. This verdict is scoped to the inspected JobHunter execution paths, not a claim that open-web discovery is inherently impossible. E02/E03.

### Can it actually retrieve jobs from a newly discovered source?

**Conditionally, after someone resolves and configures a supported source.** New Greenhouse/Lever/Ashby/SmartRecruiters identifiers reuse real collectors without code changes (C3 synthetic dispatch/intake evidence); a permitted RSS/Atom URL can reuse feed intake, and a supported Workday endpoint can reuse its legacy collector. But the application does not perform the preceding independent discovery-to-configuration handoff. An arbitrary unfamiliar website/new protocol does not become collectible because Scrapling is installed. Live functionality for a particular new employer remains a separate check. E03/E04/E07.

### Which manual inputs are unnecessary?

Candidates should not need to enumerate websites/companies, resolve ATS tenants, find feed/thread IDs, translate every role synonym, construct exact provider queries or repair parsers. These are **avoidable in principle**, not removed by current code. Basic seeded collection already avoids much of the initial burden. Accurate preferences, authorization/cost approval, real credentials, deliberate pauses and genuinely ambiguous evidence decisions remain legitimate human inputs. Section 6; Part 3 M01–M28.

### What are the three most consequential limitations?

1. **Missing unknown-source discovery and onboarding (RC1).**
2. **Static, profile-disconnected retrieval vocabulary and early lexical policy (RC2).**
3. **No strategic coverage/useful-opportunity feedback loop (RC3), with inconsistent outcome/identity contracts weakening measurement (RC4).**

Therefore the appropriate overall label is **“partially autonomous known-source collection, manual expansion, operational autonomy not demonstrated.”** It would be misleading to label it either wholly manual or operationally autonomous. No aggregate numerical score is used.

## 8. Verification performed in Part 4

### Additional controlled checks (C4)

External audit harness `/data/jobhunter-autonomy-part4/probe.py`, with results in `probe-results.json`, used a temporary SQLite database and the unchanged execution copy. External `network.get` was forbidden; boundaries were replaced explicitly:

- **Scheduling feedback:** real `AutomaticDiscovery.cycle()`, two fake eligible health rows and stub `scan`. Older source visited before newer source with yields 0/100, then still older first after yields swapped to 100/0. Confirms the inspected ordering ignores that metric; not a real-world optimization experiment.
- **Canonical identity:** real `Store.ingest`, same synthetic vacancy text at two different canonical URLs inserted twice; UTM tracking variant updated the first. No alias was supplied. Confirms URL identity boundary; not a measured rate of duplicate employer vacancies.
- **Empty-query behavior:** real `expanded_sources.collect` and registry, fake `_run_search` returning no jobs. Searches were AI Engineer/Oman then AI Engineer/Egypt; `search_index` advanced 1 then 2, page 0, `complete=False`. Confirms finite rotation, not query synthesis. Two requests cannot establish every failure scenario.

All final assertions passed. `AutomaticDiscovery.start()` was not invoked; no daemon/live collection or production state touched. Fake health rows isolate scheduling only; they are not claimed to represent a real registered-source run.

### Regression run (T4)

**Observed:** 1,764 tests passed, zero failures/errors/skips; pytest wall time 46.58 seconds. JUnit timestamp `2026-10-30T07:58:59.767426+00:00`, suite duration 46.516 seconds. Used pre-existing Python 3.13.15 / pytest 8.4.2 / python-jobspy 1.4.1 / Scrapling 0.5; no installation or dependency-file change. Command, from the separate execution copy:

```bash
env -i PATH="$PATH" HOME=/data PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/data/jobhunter-autonomy-part2/network-guard \
  /data/jobhunter-autonomy-part2/runtime/bin/python -m pytest -q \
  -p no:cacheprovider \
  --basetemp=/data/jobhunter-autonomy-part4/pytest-tmp \
  --junitxml=/data/jobhunter-autonomy-part4/tests.xml
```

Outside-repository artifact SHA-256 values:
- `probe.py`: `999cfa5d1d861695da76c9c366258e39ea817fbf20bf03c699162d6a7cb08837`.
- `probe-results.json`: `24d259750182b991edbfe4a4b9512ac4b6b4a5c26ece8660be85a11da1e5d1f8`.
- `tests.xml`: `eea54d30c60fd7d197b89e5f80e12895ff9623da51dec2c25da2eaf55deca87a`.

The existing Python-socket guard permits loopback and blocks other Python socket connects; it is **not an OS sandbox or a native-curl network guarantee**. Provider tests replace external boundaries. No live collection/model/browser success is inferred from test totals. Relevant executed fixtures are cited in E05–E13; Part 2/3 probes remain explicitly prior evidence, not new reruns.

### Important non-findings and deferred hypotheses

- **No live recall/availability estimate.** No new permitted real-provider trial, end-to-end unknown-source run, labeled suitability study, realistic deployment endurance test, or multilingual coverage benchmark. H samples do not fill those gaps.
- **No invented Workday client-lifetime defect.** Part 2's corrected fixture probe observed detail GET success; that earlier rejected harness expectation is not a root cause.
- **No proven starvation defect.** Shared cooldowns defer routes and bounded cycles limit throughput; tests cover fairness in selected cases. Sustained real coverage/starvation U, not asserted.
- **No measured “high duplicate rate” or false-merge rate.** C4 shows one mechanism; real vacancy equivalence needs labels and provider data.
- **No observed general mirror-loss incident.** SQLite-first/best-effort mirror is inspected; post-commit failure can leave a gap until a later sighting, but incident frequency/outcome loss U.
- **No claim all failures are silent.** Structured source errors and ordinary per-query exceptions are handled; the executed CLI gap is the specific top-level scanner branch.
- **No promise that unrestricted crawling, removing gates or more agents solves access/coverage.** Permission, cost and useful source feasibility require independent validation.

## 9. Completion and preservation

This phase adds only `docs/jobhunter_autonomy_review/04_autonomy_scorecard_and_root_causes.md`. All original baseline files and the three prior reports are hash-checked for preservation before publication. No application code, selectors, adapters, runtime configuration, repository dependencies, source approvals, existing data or CVs were modified. Audit harness/logs/temp databases stay outside Git. No application improvement or later-phase implementation was started.

**Part 4 complete:** thirteen scored dimensions with evidence/next-level gates, prioritized direct causes versus symptoms, manual-input impact and a bounded overall autonomy verdict.
