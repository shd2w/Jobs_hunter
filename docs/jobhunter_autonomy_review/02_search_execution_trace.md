# Part 2 — Actual search execution trace

**Scope:** follow the existing implementation from the user's action to collected/stored jobs. This extends [Part 1](01_repository_map.md) with executed behavioral evidence; it is not a second repository inventory, a replacement design, or an implementation change.

**Audit date:** 2026-10-30 UTC. **Inspected repository snapshot:** `shd2w/Jobs_hunter@2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e` (the Part 1 documentation commit; application baseline remains the one mapped there). Source references below use this immutable snapshot. First references link each repository file; later references retain its exact path/line range. Functions named in prose belong to the cited file.

## 1. What was actually verified

Read Part 1, then re-inspected the implementation and installed JobSpy provider code. The old `/data/jobhunter-regression/current` checkout and scanner venv recorded in Part 1 were unavailable in this session. Instead, downloaded the exact published snapshot into `/data/jobhunter-autonomy-part2/snapshot`, hashed its 246 files, and created a separate `execution` copy. Application/configuration/dependency files in the snapshot were not edited. Declared test dependencies were installed only in a new disposable audit venv; no target deployment or existing user environment was reconfigured.

### Evidence labels

- **S — inspected:** direct code/config evidence, not a live result.
- **T — executed test:** an existing repository test passed in this audit, with fixtures/mocks where the test uses them.
- **C — controlled execution:** ran real orchestration/parsing/store methods against synthetic data; external transports or cloud stages were explicitly replaced. Not a live-board success claim.
- **U — unverified:** real provider availability, current publisher layouts, credentialed access, cloud inference, deployment uptime, or full production coverage not established.

### Execution ledger

| Run | Exact scope | Observed result |
| --- | --- | --- |
| R1 — existing regression suite | Python 3.13.15; `pytest 8.4.2`; repository `tests`; command below, with disposable temp/data paths | **1,764 passed, 0 failed, 0 errors, 0 skipped**, pytest elapsed **48.33 s**. JUnit records 1,764 cases. **T** |
| R2 — controlled search/failure probe | Actual `sources.scan`, `JobSpyScanner` normalization/query loop, native Jobicy collector, primary Scrapling parser/store/mirror, `run_scan.main`, real `httpx.AsyncClient` with `MockTransport` for Workday, and `run_all._run_pipeline` with fake scan/evaluator/export stages where specified | Ten recorded case groups; final assertions passed. Detailed observations in Sections 4–7. **C** |
| R3 — unchanged starter registry | Actual 16-source setup and two `AutomaticDiscovery.cycle()` calls; fake JobSpy frames, synthetic fixed-source HTML, synthetic native public responses; blank profile | 10 runs in cycle 1, 4 in cycle 2; two native publisher aliases deferred by shared cooldowns; two synthetic jobs stored, zero matches. **C** |

Reproduction command for R1, from the disposable execution copy:

```bash
env -i PATH="$PATH" HOME=/data PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/data/jobhunter-autonomy-part2/network-guard \
  /data/jobhunter-autonomy-part2/runtime/bin/python -m pytest -q \
  -p no:cacheprovider \
  --basetemp=/data/jobhunter-autonomy-part2/pytest-tmp \
  --junitxml=/data/jobhunter-autonomy-part2/tests.xml
```

The external audit `sitecustomize` permits loopback and blocks non-loopback Python socket connections; it does not modify repository code and is not claimed to sandbox native libcurl. Controlled probes replace outbound transports explicitly. No live job-board probe, paid API, cloud inference, browser crawl, application submission, or private user database was used. Tests exercising local HTTP servers were allowed loopback access. Evidence logs/JSON and harnesses remain in the disposable audit area; only this Markdown report is published.

Runtime versions used: `python-jobspy 1.4.1`, `scrapling 0.5`, `httpx 0.28.1`, `pandas 3.1.0`, `curl_cffi 0.17.0`. Dependency installation completed successfully. Existing regression results do not establish that all installed optional integrations work live. One initial Workday probe assertion was incorrect: execution showed the detail request succeeds; the harness expectation was corrected, not the application. No Workday client-lifetime defect is asserted.

## 2. Start with the user's actual action

There is no single operation called “search” with one downstream path.

| User action | Actual execution | Evidence / verification |
| --- | --- | --- |
| Type a keyword in the inbox / apply a saved search | Frontend requests `/api/jobs?q=...`; `Store.jobs` searches already-stored title/company/description. Saved searches call the same local query. No outbound scraping is initiated by this action. | [`jobhunter_app/static/app.js:24–28`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/static/app.js#L24-L28), [`jobhunter_app/store.py:231–246`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/store.py#L231-L246), [`jobhunter_app/saved_searches.py:67–72`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/saved_searches.py#L67-L72); **S, T** `tests/test_saved_searches.py::test_saved_run_equals_inbox` |
| Launch `python run_local.py serve` | Constructs a store and server with `automatic=not --manual-discovery`; coordinator initializes seeds/profile, then a background loop scans due sources. `web.make_server` itself defaults automatic off for other callers. | [`run_local.py:250–253`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/run_local.py#L250-L253), [`jobhunter_app/web.py:32–34`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/web.py#L32-L34), `jobhunter_app/web.py:334–350`, [`jobhunter_app/automatic.py:54–85`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/automatic.py#L54-L85); **S, T, C(R3)** |
| Click automatic “check” | POST `/api/automatic-check` -> `coordinator.check()` sets a wake event. No force-rescan, search options, new terms, or cooldown override is accepted. | [`jobhunter_app/static/automatic.js:46–46`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/static/automatic.js#L46-L46), `jobhunter_app/web.py:234–241`, `jobhunter_app/automatic.py:128–139`; **S, T** automatic HTTP controls |
| Change the candidate profile | Saves SQLite profile, invalidates its derived matches, and wakes coordinator if present. Does not rewrite `portals.yml` or construct new retrieval terms. | `jobhunter_app/web.py:222–232`, `jobhunter_app/store.py:149–178`; **S, C(R2)** registry unchanged after new skills |
| Click source “Scan now” / submit a batch | POST `/api/scan` or `/api/scan-batch`; server starts a task thread, checks local task concurrency, invokes explicit source scan/batch and records task result/error. | `jobhunter_app/static/app.js:55–55`, `jobhunter_app/web.py:292–327`, [`jobhunter_app/source_health.py:62–73`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/source_health.py#L62-L73); **S, T** source/web tests |
| Run `run_local.py scan SOURCE_ID` | Calls `sources.scan` for that existing approved source. It is not “scan every source” and ordinary job-row scans do not themselves call the profile matcher. Post/feed processing can match within its own intake path. | `run_local.py:213–215`, [`jobhunter_app/sources.py:273–365`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/sources.py#L273-L365), [`jobhunter_app/posts.py:229–254`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/posts.py#L229-L254); **S, C(R2)** ordinary scan left matches at zero |
| Run `run_scan.py` / `run_all.py` | Scanner-family route, not iteration of the dashboard registry. `run_scan` executes Scrapling -> direct employer APIs -> JobSpy -> Markdown bridge -> inbox mirror. `run_all` adds conditional cloud evaluation/export. | [`run_scan.py:57–111`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/run_scan.py#L57-L111), [`run_all.py:65–100`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/run_all.py#L65-L100); **S, T, C(R2)** |
| Run scanner CLI `--site`, `--term`, `--location` | Builds a bounded override, removes provider additions from that in-memory config and runs only JobSpy. `--engine scrapling` rejects JobSpy query/site/location options. Registry file is not rewritten. | `run_scan.py:142–172`, [`scanners/jobspy_scanner.py:295–308`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/scanners/jobspy_scanner.py#L295-L308); **S, T** registry/CLI contracts |

### End-to-end call flow

```text
Inbox keyword/saved-search ----------------------> existing SQLite rows only

Automatic-enabled server
  -> fixed seeds + blank/existing SQLite profile
  -> cycle: approved + configured + due sources, oldest first, <=10 attempts
  -> sources.scan: lock -> approval/gates -> checkpoint -> fetch dispatcher
     -> JobSpy query/page OR fixed HTML links OR native API/feed/post source
     -> provider parse -> common normalization -> validation/URL identity
     -> SQLite transaction: jobs + sightings + checkpoint + completed run
     -> selected families: separate post-commit legacy mirror
  -> if meaningful profile + missing matches: evaluate stored jobs locally
  -> status/health/inbox, not cloud run_all evaluation

run_scan CLI
  -> Scrapling source scans (SQLite first; no per-source legacy mirror)
  -> configured direct employer APIs
  -> sequential configured JobSpy query loop (library may parallelize sites)
  -> PipelineBridge: filter -> historical/in-batch dedup -> pending Markdown/cache
  -> passed scanner sightings -> SQLite mirror, including repeated observations
run_all
  -> if legacy new_added == 0: STOP, even if pending items already exist
  -> otherwise evaluate ALL pending Markdown jobs
     -> description/cache/fetch -> cloud evaluator -> durable JSON -> checked item
  -> queue export after evaluator coroutine returns (not after every job succeeds)
```

Call evidence: `jobhunter_app/automatic.py:164–222`, `jobhunter_app/sources.py:273–365`, `run_scan.py:57–111`, `run_all.py:77–104`, `run_evaluate.py:143–215,348–415`. The state/count differences in this flow were exercised below rather than inferred from names.

## 3. All 13 stages: behavior and autonomy classification

“Automatic” here means no per-job intervention **after** the required setup and invocation; it does not mean the system discovers its own search space. Categories overlap deliberately.

| Stage | Actual implementation and data dependency | Classification | Evidence / verification |
| --- | --- | --- | --- |
| 1. Initialization | Server startup may enable a persistent coordinator; check merely wakes it. Manual scan needs a source ID; scanner CLI runs once. Seeding is insert-only/versioned, so existing pauses are not blindly undone. | **Fully automatic within configured startup; partially automatic overall; manual invocation/host dependency.** | `run_local.py:250–253`; `jobhunter_app/automatic.py:54–85,119–139`; **S, T, C(R3)** |
| 2. Preferences/config | SQLite profile holds skills/facts/exclusions/matching preferences. Legacy YAML profile supplies cloud evaluation preferences. Retrieval registry and legacy filters live separately in `portals.yml`. Blank profile is allowed for collection. | **Static configuration + manual preferences; profile-to-retrieval linkage missing in these paths.** | `jobhunter_app/store.py:149–178`; [`jobhunter_app/match_config.py:4–19`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/match_config.py#L4-L19); [`config/portals.yml:133–195`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/config/portals.yml#L133-L195); [`agents/evaluator.py:149–164`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/agents/evaluator.py#L149-L164); **S, T, C(R2/R3)** |
| 3. Query construction | Expands literal terms × locations or copies explicit query entries; adds fixed provider-specific configs; explicit CLI overrides possible. No candidate-derived term synthesis, translation or zero-yield rewrite was found. | **Automatic deterministic expansion driven by static config; manual maintenance; dynamic generator missing.** | `scanners/jobspy_scanner.py:53–117`, `run_scan.py:158–168`; **S, T, C(R2)** |
| 4. Source selection | Automatic coordinator selects approved due records, including custom registered sources; full CLI selects only its three scanner families. Fixed seed list is not every policy/adapter. No source-ranking optimizer or domain/company discovery call occurs. | **Automatic gated selection over static/manual registrations; new unsupported platforms need developer intervention.** | `jobhunter_app/automatic.py:17–39`, `jobhunter_app/automatic.py:164–200`; `jobhunter_app/sources.py:93–148`; **S, T, C(R3)** |
| 5. Source retrieval | Known API endpoints, JobSpy provider implementations, fixed Scrapling hosts, explicitly supplied ATS IDs/feeds/authorized listing URLs/social scopes. Credentials/permissions required for some routes. | **Automatic once configured; static endpoints; manual setup for non-seeds; implemented but live-unverified.** | `jobhunter_app/sources.py:156–190`, [`jobhunter_app/platform_posts.py:17–42`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/platform_posts.py#L17-L42), [`jobhunter_app/authorized_boards.py:31–49`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/authorized_boards.py#L31-L49); **S, T, C** fixtures; **U** live |
| 6. Pagination/limits | Dashboard JobSpy advances one provider/query/page per scan; native/HTML collectors use committed checkpoints and finite bounds. Full JobSpy CLI runs every configured query once, with library-managed pagination inside calls. | **Fully automatic bounded continuation driven by static limits; some reset/recovery manual.** | [`jobhunter_app/expanded_sources.py:23–53`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/expanded_sources.py#L23-L53), [`jobhunter_app/collection.py:34–118`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/collection.py#L34-L118), [`jobhunter_app/scrapling_engine.py:112–167`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/scrapling_engine.py#L112-L167); **S, T, C** |
| 7. Parsing/normalization | Provider frames/API fields/JSON-LD -> normalized rows -> `normalize_job`. Requires title/company/valid canonical URL for SQLite; malformed rows counted or provider parsing may skip them. No arbitrary prose-to-job LLM in board collectors. | **Fully automatic rule-based parsing; static schemas; changed layouts can need developer review; live compatibility U.** | `jobhunter_app/sources.py:193–252`; `scanners/jobspy_scanner.py:247–292`; `jobhunter_app/scrapling_engine.py:67–109`; [`jobhunter_app/validation.py:33–53`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/validation.py#L33-L53); **S, T, C** |
| 8. Filtering/exclusion | JobSpy dashboard branch filters before SQLite; scanner bridge filters all scanner rows; ordinary native/primary Scrapling SQLite intake is broader. Profile hard exclusions annotate matching, not universal pre-retrieval filtering/deletion. | **Automatic static lexical filters + manual preference settings; no general semantic retrieval rescue.** | [`utils/filters.py:17–141`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/utils/filters.py#L17-L141), `jobhunter_app/expanded_sources.py:42–45`; [`jobhunter_app/matching.py:57–116`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/matching.py#L57-L116); **S, T, C(R2)** |
| 9. Dedup/history | Legacy pipeline/history/application checks differ from SQLite canonical URL/alias identity. Repeated observations may update a single stored job. Company-title-location heuristics are not a universal syndicated-identity resolver. | **Fully automatic rules over existing history; alias creation/history inputs can be manual.** | [`utils/dedup.py:43–142`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/utils/dedup.py#L43-L142), `jobhunter_app/store.py:185–229`; **S, T, C(R2)** |
| 10. Description retrieval | JobSpy requests descriptions; direct APIs fetch details; primary Scrapling fetches structured detail pages. Legacy evaluation tries existing text -> usable cache -> static fetch -> conditional browser rendering; failure can leave item pending. | **Partially automatic, source/runtime/access dependent; implemented but live-unverified.** | `scanners/jobspy_scanner.py:225–227`; [`scanners/workday.py:153–214`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/scanners/workday.py#L153-L214); [`run_evaluate.py:143–211`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/run_evaluate.py#L143-L211); [`utils/jd_cache.py:37–53`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/utils/jd_cache.py#L37-L53); **S, T, C Workday/Scrapling**; cloud/browser **U** |
| 11. Evaluation | Coordinator optionally runs deterministic contextual lexical matching over SQLite; ordinary manual job scans do not do that automatically. Post intake can match inline. `run_all` uses a distinct cloud evaluator over pending Markdown. Semantic reranking is explicit/local and not retrieval. | **Partial automatic; manual profile/cloud setup; separate evaluation paths, not one mandatory scan stage.** | `jobhunter_app/automatic.py:204–208`; `jobhunter_app/store.py:272–286`; `jobhunter_app/posts.py:250–254,296`; `run_evaluate.py:364–415`; [`jobhunter_app/semantic.py:153–172`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/semantic.py#L153-L172); **S, T, C** gates; cloud/model **U** |
| 12. Persistence/reporting | Atomic SQLite collection completion, separate best-effort legacy mirror; Markdown/history/cache bridge; cloud JSON append before processed checkbox; queue export downstream. Summary units differ. | **Automatic after acceptance; partial cross-store atomicity; reporting gap verified.** | `jobhunter_app/sources.py:326–365`; [`scanners/bridge.py:74–147`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/scanners/bridge.py#L74-L147); `run_evaluate.py:348–359`; [`utils/evaluation_store.py:47–69`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/utils/evaluation_store.py#L47-L69); **S, T, C(R2)** |
| 13. Failure/recovery | Per-source isolation, cancellations, cooldowns/retry gates, access revocation, persisted checkpoints and interrupted-run recovery exist. Paused/blocked or malformed-layout sources do not heal themselves through alternate engines or query invention. | **Partially automatic recovery; manual permission/config/reset and sometimes developer intervention; specific gaps verified.** | `jobhunter_app/sources.py:367–419`, `jobhunter_app/store.py:108–130`, `jobhunter_app/source_health.py:17–73`; **S, T, C(R2/R3)** |

## 4. Query construction: concrete behavior, not inferred intelligence

### 4.1 The actual request chosen without user-supplied terms

The shipped registry contains 14 terms and seven locations. `_load_primary` loops **terms first, locations second**. The first dashboard Indeed search in a fresh checkpoint therefore submitted the following arguments to the intercepted `jobspy.scrape_jobs` boundary:

```json
{"site_name":["indeed"],"search_term":"AI Engineer","location":"Oman","offset":0}
```

After that short page, checkpoint became `{"search_index":1,"page":0,"complete":false}`. After a synthetic profile change and explicitly aging only that disposable source's `last_run` to allow another scan, the next request was **AI Engineer / Egypt / offset 0**, not a term derived from the new skill. The configured 210-query registry remained unchanged. These are **C(R2)** observations, consistent with `scanners/jobspy_scanner.py:53–117`, `jobhunter_app/expanded_sources.py:26–47` and `jobhunter_app/store.py:149–178`.

The 210 entries are **query configurations**, not 210 HTTP requests or equal regional coverage: 98 configurations target the original four sites together, plus 56 Glassdoor and 14 each for ZipRecruiter/Naukri/BDJobs/HelloWork. Automatic collection splits this into single-provider selections. `tests/test_all_jobspy_platforms.py:24–36` passed these registry assertions in R1. A site's count of configured selections is not its unique-job contribution.

Country/remote handling is also deterministic: `_do_search` prefers explicit `country_indeed`, else global config, else substring inference from location; remote/worldwide/unknown defaults to USA for that field. A remote location can set `is_remote=True`; provider-declared remote information preserves the location/country when normalizing. No legal-eligibility inference follows. Evidence: `scanners/jobspy_scanner.py:184–217,255–259` (**S, T**).

### 4.2 Requested edge cases

| Situation | What actually happens | Evidence / qualification |
| --- | --- | --- |
| Relevant new title absent from configured query terms | No new query is created. It may still arrive because a provider matches description/synonyms, an existing broad term returns it, or an unqueried feed/HTML listing includes it. If it arrives through the JobSpy/legacy path, title positives/negatives are a separate acceptance gate. Absence from the query list alone does **not** prove it can never be discovered. | `scanners/jobspy_scanner.py:93–115`; `utils/filters.py:22–56`; **S, C(R2)** synthetic unfamiliar title rejected in JobSpy but stored via native/Scrapling |
| Unfamiliar terminology | No vocabulary-learning, synonym discovery, or relevance-feedback loop in the inspected retrieval functions. Lexical title filter can reject a role even when its description mentions a profile skill. Local matching cannot recover a row rejected before SQLite. | `jobhunter_app/expanded_sources.py:42–45`; `jobhunter_app/matching.py:57–116`; **S, C(R2)** `Quantum Wizard` + “Python required” |
| Source-specific search syntax | Repository supplies a common term/location/country/remote API, plus a Google-specific query string. Provider syntax translation lives largely inside installed JobSpy; it exists but is not learned from result quality. Direct employer scanners use fixed Workday `searchText` or SmartRecruiters `q`. | `scanners/jobspy_scanner.py:209–236`; `scanners/workday.py:158–175,218–230`; dependency inspection below; **S, C** wrapper arguments/Workday request |
| Another language | Literal English/German queries exist. Matching includes narrow English/German/Arabic evidence/aliases; that is downstream, not outbound translation. No automatic query translation or general cross-language title acceptance was found. An unfamiliar-language title may enter unfiltered native/HTML intake, but can fail the lexical title gate elsewhere. | `config/portals.yml:138–151`; `jobhunter_app/matching.py:7–26,116`; **S, C** default filter accepted `Softwareentwickler`, rejected `مهندس برمجيات` and `Développeur logiciel` in these specific probes; not a language-wide recall claim |
| Useful candidate skill never converted into a query | Saving skills invalidates local match cache and can wake the coordinator; configured retrieval terms are unchanged. Profile preferred title/location terms and weighted skill aliases influence already-collected-job ranking only. | `jobhunter_app/web.py:222–232`; `jobhunter_app/match_config.py:4–19`; `jobhunter_app/matching.py:85–105`; **S, C(R2)** |
| Few or zero relevant results | Short/empty **raw** JobSpy page advances to the next preconfigured query. A full raw page can advance to the next bounded offset even if all rows fail relevance filters. No expansion/translation/new-source request is triggered by low accepted yield. Future cycles repeat the same finite registry; cooldowns/gates still apply. | `jobhunter_app/expanded_sources.py:38–53`; **S, C(R2)** empty frame returned zero rows, `search_index=1`, `coverage_complete=false` |

### 4.3 What source-specific delegation really means

The installed package was inspected directly at `runtime/lib/python3.13/site-packages/jobspy` (same files resolve through `lib64`). These are **dependency paths**, not files asserted to exist in the repository. Version is `python-jobspy==1.4.1`; SHA-256 of its `jobspy/__init__.py` is `85038be03d6a2bcd798f9d2af9c0bb688eebdc982e9e4edb768b4d148945b376`.

- `jobspy/__init__.py:37–46,115–147`: maps all nine sites, uses `ThreadPoolExecutor` across selected sites within one call, merges rows and attaches per-provider errors/warnings to the frame. **S dependency inspection**, not a live concurrency benchmark. In contrast, repository `JobSpyScanner.scan:119–148` uses a single worker across query configurations.
- LinkedIn `jobspy/linkedin/__init__.py:62–120`: start/offset paging and a `keywords` parameter. Indeed `jobspy/indeed/__init__.py:60–122`: cursor-based API search, offset skipping and formatted `what` term. Glassdoor `jobspy/glassdoor/__init__.py:64–86,135–150`: keyword variables plus page/cursor GraphQL retrieval. **S**.
- Google `jobspy/google/__init__.py:53–70,75–110`: cursor collection/offset slice; a supplied `google_search_term` overrides its generated query. JobHunter supplies `"{term} jobs in {location}"`; this can bypass the library's composed additions rather than constitute a semantic query planner. **S**. No live assertion about Google availability is made.
- ZipRecruiter `jobspy/ziprecruiter/__init__.py:45–103`: offset-to-page translation, `search` term and remote filter. Bayt `jobspy/bayt/__init__.py:45–112`: location decomposition/slug and page/offset handling. Naukri `jobspy/naukri/__init__.py:47–64,108–121`: `keyword`, location, `pageNo`, remote `wfhType`. BDJobs `jobspy/bdjobs/__init__.py:43–99`: keyword API, `pg` pages and skip/offset. HelloWork `jobspy/hellowork/__init__.py:57–109`: HTML search, `k` term and `p` page. **S**; provider syntax/live compatibility **U**.

This establishes that provider adapters do more than share a filename. It does not establish working access, complete pagination, correct regional results, or actual job delivery from any of the nine sites today.

## 5. Selection, limits and retrieval: what a scan really covers

### 5.1 Controlled first-run scheduling with all 16 defaults unchanged

R3 used the real `STARTERS` and `LABELS`, not the three-source fixture subset in `tests/test_automatic.py`. Blank profile remained `{"name":"","skills":[],"facts":[]}`.

1. Cycle 1 completed **10 source runs**, in order: primary Scrapling Jobicy, primary Scrapling Arbeitnow, Remotive, RemoteOK, WeWorkRemotely, JobSpy Indeed, LinkedIn, Bayt, Google, Glassdoor.
2. Native `jobicy:remote` and `arbeitnow:de` were registered/approved but **not fetched**: the first Scrapling scans had consumed their shared publisher-family cooldowns. “16 sources configured” therefore did not mean 16 independent retrievals on one click.
3. Cycle 2, immediately afterward, ran the remaining four JobSpy sources: ZipRecruiter, Naukri, BDJobs, HelloWork. Other due checks prevented repeats. Two native aliases still had no `last_run`.
4. Two synthetic HTML jobs existed in SQLite; profile matching count remained **zero**, as expected for the blank profile. Empty fixture JobSpy pages were reported `partial` because coverage is bounded, not as proof of global zero jobs.

**C(R3)** establishes this controlled ordering, limit and gate interaction, not long-run production fairness. Code: `jobhunter_app/automatic.py:164–208`; `jobhunter_app/source_health.py:8–14,40–48`; `jobhunter_app/sources.py:285–294`. The existing fairness/cooldown tests also passed (**T**, `tests/test_automatic.py:167–178`, `tests/test_scrapling_engine.py:119–136`). When a later family cooldown expires, older never-run native records can sort ahead of recently run HTML sources; these two cycles do not prove permanent native starvation.

### 5.2 Source families and finite units of work

| Route | Selection/input dependency | Actual retrieval/pagination unit | Evidence / status |
| --- | --- | --- | --- |
| Automatic JobSpy | Provider must be registered as `configured`; terms/regions from YAML | One provider/query/page; size 1–50, default 30; offset `page*size`; continue only if raw normalized rows fill the size and page bound permits. Default two pages, cap five; otherwise rotate query modulo configured count. Description requests are additional. | `jobhunter_app/expanded_sources.py:26–53`; **S, T, C(R2)** |
| Full JobSpy CLI | All 210 default query configurations, or explicit in-memory override | One executor worker iterates configurations, two-second inter-query delay; each library call may request multiple sites concurrently and fetch multiple provider pages/details. No dashboard checkpoint rotation/gate call in this direct JobSpy scanner loop. | `scanners/jobspy_scanner.py:119–148`; `run_scan.py:89–111`; **S, T, C** query-error isolation, not a 210-query live run |
| Primary Scrapling | Fixed Jobicy/Arbeitnow definitions; no user URL needed for these two | Robots + listing + at most three detail pages, at most five requests/call; pending details resume. Up to 20 listing pages/pass, 200 pending URLs; `coverage_complete=false` even when listing pass finishes. Empty unrecognized listing/detail is an error, not successful empty coverage. | `jobhunter_app/scrapling_engine.py:10–20,51–64,107–167`; **S, T, C** three-request sample |
| Direct employer scanner | `tracked_companies` + enabled/scan-method + supported endpoint; default list is empty | Workday/SmartRecruiters up to five list pages × 20, plus details. Workday listing retained if detail fails; SmartRecruiters failed detail skipped with error, other items retained. Company terms manual/default `working student`. | `config/portals.yml:133`; `scanners/workday.py:64–105,124–261`; **S, T, C** Workday POST + detail GET |
| Native Greenhouse/Lever/Ashby | Explicit employer board ID; not auto-enumerated | One configured endpoint response; ATS response bound 32 MiB, normalized list bound 10,000; unlisted Ashby rows excluded. No universal multi-page ATS crawler added here. | `jobhunter_app/sources.py:129–148,178–218`; **S, T** |
| Native Jobicy / Arbeitnow | Fixed remote or DE/UK identifier | Jobicy 100/job response cap with cursor and 24-hour cursor-age check; Arbeitnow one page, at most 1,000 rows, increasing numeric next page from fixed host. Separate from primary HTML, shared family cooldown. | `jobhunter_app/collection.py:66–91`; **S, T, C** native unfamiliar-title intake |
| Native SmartRecruiters | Registered company/account ID | List up to 100, fetch at most 10 pending details/scan, commit remainder and list offset; at most 11 reads, spaced 0.6 seconds. | `jobhunter_app/collection.py:48–65`; **S, T** `test_smart_resume_without_refetching_first_details` |
| Remotive / RemoteOK / WWR | Fixed public endpoints | Current public response/feed, not an all-vacancies crawl. RemoteOK/WWR have no ongoing next-page search plan in their branches. | `jobhunter_app/sources.py:138–148,221–226`; `jobhunter_app/expanded_sources.py:54–98`; **S, T, C(R3)** empty responses |
| USAJOBS | Supplied keyword + API key/user-agent | One public-search page of 50; count-based continuation; not seeded and no automatic keyword generation. | `jobhunter_app/collection.py:92–100`; **S, T**, real configured access **U** |
| HN | Explicit Who Is Hiring story ID | Story + at most 10 unseen top-level comments; no discovery of newest hiring thread or profile traversal; comment IDs checkpointed. | `jobhunter_app/collection.py:101–117`; **S, T** |
| Generic approved feed | Supplied permitted feed URL | RSS/Atom parsing up to 300 entries and 5 MiB; no page-following plan; content goes through post extraction/review/auto-add rules. | [`jobhunter_app/feeds.py:32–82`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/jobhunter_app/feeds.py#L32-L82); **S, T** |
| Wuzzuf/Naukrigulf | Explicit authorized listing URL, approval and selected HTTP/browser transport | Listing plus up to four details, optional robots, max six calls/scan; pending continuation, 50-page route cap; publisher JSON-LD required. Default robots mode is `skip` for these two authorized-board routes, unlike primary Scrapling's mandatory check. | `jobhunter_app/authorized_boards.py:19–23,158–220`; **S, T**, live access/layout/browser **U** |
| Official social posts | Explicit authorized organization/user/subreddit/channel scope and API setup | One page, at most 50 posts, provider cursor monotonicity checks; non-Telegram page-index bound 100. Not whole-platform job search; LinkedIn post API differs from JobSpy LinkedIn jobs. | `jobhunter_app/platform_posts.py:17–42,78–118,119–201`; **S, T**, access **U** |

No route above discovers new ATS employer identifiers or external domains merely because results are sparse. The directory only returns links (`jobhunter_app/source_directory.py:26–34`); it is not a web-search executor. Unsupported endpoints/layouts can require developer work; ordinary configuration changes/registration for supported types need not.

## 6. Parsing, filters, identity, descriptions and evaluation: observed transformations

### 6.1 One provider response followed all the way into SQLite

R2 replaced **only** `jobspy.scrape_jobs` for this path, returning a real pandas frame to the actual wrapper/collector/SQLite pipeline. Six rows were supplied:

| Row | Synthetic source content | Actual disposition |
| --- | --- | --- |
| A | `Software Engineer`, Example, Berlin/Germany, URL `/jobs/one?utm_source=fixture`, description “Python required” | Passed filters, canonicalized, inserted. |
| B | Same title/company/location, canonical `/jobs/one` | Passed, mapped to same SQLite URL identity, counted as updated sighting. |
| C | `Quantum Wizard`, same profile-skill description, Berlin/Germany | Rejected by title before SQLite. |
| D | `Senior Software Engineer`, Berlin/Germany | Rejected by negative title rule despite positive terms. |
| E | `Software Engineer`, Antarctica | Rejected by configured location allow list. |
| F | `Software Engineer`, Berlin/Germany, missing company | Passed lexical filters, failed common SQLite validation. |

Observed metrics:

```json
{
  "raw_received": 6,
  "rejected_title": 2,
  "rejected_location": 1,
  "received_by_intake": 3,
  "invalid": 1,
  "inserted": 1,
  "updated": 1,
  "distinct_stored_jobs": 1,
  "matched_jobs_immediately_after_manual_scan": 0
}
```

Immediate repeated scan raised **“Per-source cooldown: wait at least 300 seconds between scans”** without a second provider call. After aging only the disposable source timestamp, repeated same fixture produced **0 inserted, 2 updates**, still **one distinct job**. Therefore `updated`, raw provider rows, filtered rows, and distinct jobs are different units; adding these metrics naively overstates coverage. **C(R2)**; implementation: `jobhunter_app/expanded_sources.py:38–53`, `jobhunter_app/validation.py:33–53`, `jobhunter_app/store.py:185–226`.

Canonical identity uses SHA-256 of normalized URL, with explicit alias lookup. It is not a semantic comparison of every job. Legacy bridge identity instead checks canonical URLs in pipeline/history/applications plus company-role/location keys (`utils/dedup.py:43–142`). Skipped-history statuses are deliberately not permanent duplicate barriers, allowing changed filters to reconsider future sightings. Broader cross-board syndication with different URLs is not automatically resolved by the SQLite ingest path (**S, T**).

### 6.2 The same unfamiliar title has different path outcomes

- JobSpy route: `Quantum Wizard` + Python description was rejected before SQLite.
- Native Jobicy route with the same unfamiliar title: **one job inserted**, title preserved.
- Primary Scrapling route: mocked robots/listing/detail bytes were fetched, real Selector/JSON-LD normalization ran, **one job inserted into SQLite**, but post-commit legacy mirror recorded **one title rejection, zero new Markdown additions**. Requests were exactly robots, listing and one detail URL.

These are **C(R2)** outcomes. They establish the path-dependent filter boundary, not that “Quantum Wizard” is genuinely relevant to a real candidate. Local matching cannot rank a JobSpy row that was never ingested, while a native/Scrapling row can remain in the inbox even if absent from the legacy evaluation queue. Evidence: `jobhunter_app/sources.py:193–199,330–365`, `jobhunter_app/expanded_sources.py:42–45`, [`scanners/compat.py:12–27`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/scanners/compat.py#L12-L27), `utils/filters.py:22–56`.

Primary Scrapling details require structured organization/title/description and retain publisher-declared locations, applicant-country restrictions, employment, salary and attribution (`jobhunter_app/scrapling_engine.py:67–109`). Ordinary API normalizers map provider fields and skip unlisted/inactive items where coded (`jobhunter_app/sources.py:193–252`). Post/feed handling is different: `posts.process` stages evidence, classifies complete source-backed vacancies, auto-adds eligible records or leaves ambiguity for human review; it does not manufacture employers/roles from arbitrary text. See `jobhunter_app/posts.py:229–299` (**S, T**).

### 6.3 Description enrichment is not guaranteed by “job collected”

- Wrapper requests JobSpy descriptions and LinkedIn descriptions by default; provider/library behavior determines success. Missing descriptions do not automatically disqualify a normalized SQLite row. `normalize_job` permits empty description. **S, T** `scanners/jobspy_scanner.py:225–227`, `jobhunter_app/validation.py:38–53`.
- Workday controlled probe used a real `httpx.AsyncClient` with `MockTransport`, not a custom fake client: observed **POST listing + GET detail**, one retained job with “Full detail text,” no query errors. This confirms that branch's listing/detail relationship under fixture responses, not a live tenant. **C(R2)** `scanners/workday.py:153–209`.
- Bridge writes descriptions for **new legacy additions**, capped to 15,000 characters by `JDCache.put`. Cache retrieval requires **more than 50 characters**; short text can be stored yet not be a usable cache hit. Duplicate legacy sightings do not refresh this new-additions cache loop, even though SQLite mirror can update sightings. **S** `scanners/bridge.py:107–122`, `utils/jd_cache.py:37–53`.
- During legacy evaluation, existing nonempty job description is used; else usable cache, else static `fetch_jd`, then optional rendering only when not expired and error is not exact HTTP 401/403/429. A 404/recognized expiry checks the item off; access/content failure leaves it pending, with no invented evaluation. Static extraction rejects PDF/image and fewer than 300 characters. Rendering code lacks the same short-text check before its success return; live rendered content quality remains **U**. Evidence: `run_evaluate.py:160–208`, [`utils/jd_fetcher.py:140–198`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/utils/jd_fetcher.py#L140-L198), `utils/jd_fetcher.py:214–254` (**S, T** access-denial and expiry contracts).

### 6.4 Evaluation and persistence are separate, conditional paths

**Local application:** `Store.evaluate` matches all stored jobs for a profile. Skills/preferences/exclusions create deterministic lexical/contextual results, not outbound queries or legal-eligibility proof. Saving a profile invalidates matches; coordinator recomputes only when meaningful profile content exists and matched count is below total jobs. Blank profile in R3 collected two jobs without matching them. Ordinary manual JobSpy scan in R2 likewise did not call `Store.evaluate`; post intake can match inline. **S, T, C** `jobhunter_app/automatic.py:204–208`, `jobhunter_app/store.py:149–178,272–286`, `jobhunter_app/posts.py:250–254,296`.

**Legacy/cloud:** `run_all` only enters evaluation if bridge `new_added > 0`; `run_evaluate(mode='all')` then selects **all pending Markdown items**, not just the new batch. AI evaluator builds a profile/CV/description prompt, uses configured cloud routing, validates model output, recomputes weighted 1–5 score and writes a report. Optional German policy can change the later recommendation/score. No cloud inference or credential validation was executed here. **S, T** `run_all.py:77–90`, `run_evaluate.py:237–280,373–415`, `agents/evaluator.py:149–209`.

**Refinement of Part 1's “evaluation succeeded” wording:** there is no all-jobs-success check before queue export. R2 made the evaluator coroutine return `[{"success":false,...}]`; **export was still called**. A raised evaluator exception prevents export (existing tests passed); an unsuccessful per-job return is not the same condition. R2 also returned `new_added=0`: evaluator/export were both skipped, regardless of the independent pending-work concept. **C**, `run_all.py:77–104`; **T** [`tests/test_run_all_export_integration.py:61–99`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_run_all_export_integration.py#L61-L99).

For successful processed evaluations, durable `append_evaluation` precedes tracker/checkbox completion. Failed model results remain pending; persistence exceptions propagate without marking processed. Reports/documents may already have been attempted before JSON append—this is not one transaction covering all output files. **S, T** `run_evaluate.py:211–221,348–359`, `utils/evaluation_store.py:47–69`, [`tests/test_policy_regressions.py:61–101`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_policy_regressions.py#L61-L101).

## 7. Failure handling and recovery: verified cases versus unknowns

| Failure / boundary | Observed or executed contract | Evidence and scope |
| --- | --- | --- |
| One automatic source fails | Coordinator catches source-level `ValueError`, continues other due sources, preserves structured health/error information. | `jobhunter_app/automatic.py:195–202`; **T** [`tests/test_automatic.py:76–95`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_automatic.py#L76-L95) `test_one_failed_feed_does_not_block_others`, rate-limit case |
| One configured JobSpy query fails | R2 raised on query `first`, returned one job on `second`: **both attempted, one job and one error returned**. | `scanners/jobspy_scanner.py:130–146`; **C**, plus provider metadata tests **T** |
| Top-level JobSpy scanner fails | R2 raised from `JobSpyScanner.scan` while other scanner stubs returned empty: error logged, but returned summary had `total_found=0`, `errors=[]`; actual `run_scan.main()` exited **0**. The handler does not append a failure result. Equivalent direct-engine handler structure is inspected, not separately injected here. | `run_scan.py:80–96,171–172`; `scanners/bridge.py:142–145`; **C** for JobSpy, **S** direct handler. This is a real reporting blind spot, not evidence a provider works. |
| Partial JobSpy provider metadata | Wrapper keeps frame error/warning metadata; errors with empty frame raise `ProviderFailure`; nonempty partial results can survive with errors. Full query loop adds errors; automatic path records metadata in bounded metrics. | `scanners/jobspy_scanner.py:223–241`; `jobhunter_app/expanded_sources.py:48–53`; **T** [`tests/test_scraper_restoration.py:44–68`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_scraper_restoration.py#L44-L68) |
| 429 quota / retry gate | Source is paused/unapproved; family gate persisted, minimum cooldown extended by Retry-After. Reapproval/checkpoint reset does not bypass gate; native/Scrapling publisher aliases share it. | `jobhunter_app/sources.py:374–418`; `jobhunter_app/source_health.py:17–27,54–60`; **T** [`tests/test_scrapling_engine.py:119–144`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_scrapling_engine.py#L119-L144), [`tests/test_phase3_sources.py:188–224`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_phase3_sources.py#L188-L224) |
| 401/403/robots disallow on relevant HTML/post adapters | Access-block handling unapproves affected adapter sources; checkpoint not advanced, existing jobs preserved. No automatic alternate-transport/bypass recovery. | `jobhunter_app/sources.py:375–410`; **T** `tests/test_scrapling_engine.py::test_atomic_failure_retains_existing_jobs_and_checkpoint` at 103–116 |
| Missing runtime / API setup | Explicit missing-runtime/setup errors; social setup may fail before a run is created. No dependency auto-install in scanner, no invented successful empty result. | `jobhunter_app/sources.py:281–284,386–397`; **T** runtime/setup tests; target deployment setup **U** |
| Cancelled/in-flight paused scan | Cancel checks prevent committing returned data, retain checkpoint; cross-server pause is re-read through `_Cancellation`. | `jobhunter_app/automatic.py:88–96`; `jobhunter_app/sources.py:309–313,369–373`; **T** `tests/test_automatic.py:104–114`, `tests/test_scrapling_engine.py:139–144` |
| Completion DB write fails | Synthetic trigger causes rollback of jobs/posts/checkpoint together, not a partly advanced continuation. | `jobhunter_app/sources.py:316–354`; **T** `tests/test_phase3_sources.py:171–179` parametrized four-adapter rollback test, feed rollback test |
| Malformed payload / changed layout / ambiguous next page | Fails rather than declaring successful empty coverage; checkpoint remains available for explicit review/reset. This can require configuration/developer intervention; no layout self-repair is implemented in these collectors. | `jobhunter_app/scrapling_engine.py:51–64,107–131`; `jobhunter_app/authorized_boards.py:188–213`; **T** malformed/cursor/bounds tests |
| Legacy mirror fails after SQLite success | Exception is caught, returned result gains `legacy_mirror_error`, an audit event is written; committed SQLite data is not rolled back. It is not a cross-store transaction or guaranteed background repair queue. | `jobhunter_app/sources.py:356–365`; **S** inspected. No explicit post-commit mirror-failure injection in R2; distinction retained as code-only evidence. |
| Worker ends leaving running run | Store construction recovers abandoned running records only if it can own scan lock; marks interrupted, does not fake success. Resume still respects approvals/gates and last-run timing. | `jobhunter_app/store.py:108–130`; **T** [`tests/test_phase1_foundations.py:66–98`](https://github.com/shd2w/Jobs_hunter/blob/2b10a9f8ea7e5a1d2cb3164db7a09bb8ca45fb6e/tests/test_phase1_foundations.py#L66-L98) |
| Jobicy cursor expires | Manual collector rejects >24-hour cursor. Automatic special case resets the due starter pass while preserving jobs/gates, then retrieves again. This is specific recovery, not a generic “retry any source” policy. | `jobhunter_app/collection.py:66–77`; `jobhunter_app/automatic.py:188–195`; **T** `tests/test_automatic.py:160–165` |
| Description access denied / model fails / output cannot persist | 403 does not trigger browser fallback or fabricated evaluation; failed eval remains pending; persistence failure does not mark processed. | `run_evaluate.py:175–215,348–359`; **T** `tests/test_policy_regressions.py:61–101` |
| Full evaluation loop encounters thrown error | There is no per-job try/except around `await evaluate_job` in its main pending loop; returned failure allows later iteration, a thrown exception can abort remaining items and `run_all` export. | `run_evaluate.py:407–415`; **S**, with propagation test coverage **T**; no live cloud outage injected |

The pipeline is therefore resilient to **many ordinary source/query failures**, but not uniformly observable or transactional at every boundary. An exception outside ordinary per-query handling, a store/legacy bridge failure, or a thrown evaluation error is different from a provider returning zero jobs. The top-level scanner summary gap is executed evidence of that distinction.

## 8. Static/manual dependencies and principal autonomy bottlenecks

These are conclusions about the observed implementation, not proposed fixes.

1. **The search space is maintained outside the candidate profile.** The query builder consumes `portals.yml` and explicit overrides, not skills/facts/preferred terms. New useful skills change ranking inputs, not outbound searches. **S + C(R2)** `scanners/jobspy_scanner.py:53–117`, `jobhunter_app/store.py:149–178`. General profile-to-retrieval query generation is missing in these paths.
2. **Unknown terminology can be lost before evaluation.** Static positive/negative title filters do not inspect the description for relevance rescue. R2's profile-skill-bearing unfamiliar role was dropped in JobSpy, but preserved in native/HTML intake. **C**, `jobhunter_app/expanded_sources.py:42–45`, `utils/filters.py:22–56`. Absence from a term list does not preclude upstream discovery, but the downstream lexical gate still matters.
3. **Registered sources are not automatically discovered sources.** Zero-input seeds work without user URLs because developers supplied fixed choices. ATS company IDs, new feeds, HN story IDs, authorized board listings and social scopes remain manual inputs; unsupported kinds/new parsers need developer work. **S**, `jobhunter_app/sources.py:93–148`, `jobhunter_app/collection.py:92–117`, `jobhunter_app/platform_posts.py:17–42`. Source-directory Google links are not executed discovery.
4. **Configured breadth does not equal simultaneous/complete retrieval.** R3's 16 seeds produced 10 then 4 runs, not 16 independent fetches. Shared publisher gates, provider-specific cooldowns, single scan lock, query/page caps and synchronous sequential coordinator calls bound coverage. Full CLI traverses a different search space and bypasses the dashboard JobSpy checkpoint scheduler. **S + C**, `jobhunter_app/automatic.py:171–200`, `jobhunter_app/sources.py:264–294`, `jobhunter_app/expanded_sources.py:33–53`. Sustained real coverage/latency remains **U**; no wall-clock completeness estimate is claimed.
5. **Few accepted results do not cause strategy adaptation.** Empty pages rotate through a finite static registry; rejected rows do not teach new words, language variants, companies or sources. A full raw page can consume another page budget even if accepted relevance is zero. **S + C(R2)** `jobhunter_app/expanded_sources.py:38–53`.
6. **Source access and layout failures have deliberate stopping points.** Pauses, approval requirements, parser constraints and missing setup are surfaced rather than bypassed. They can require human access review or developer/schema maintenance. No generic automatic transport fallback between native API, Scrapling, browser, and JobSpy exists in the inspected dispatcher. **S + T**, `jobhunter_app/sources.py:156–190,367–419`, `jobhunter_app/scrapling_engine.py:107–131`. Current provider failure rates are **U**.
7. **Collection, local relevance, and legacy evaluation are different populations.** A SQLite row may have no match yet or no pending Markdown counterpart; `new_added==0` can skip legacy evaluation despite other stored/pending work. Descriptions may be absent/short and cache hits have their own threshold. **S + C**, Sections 6.1–6.4. Therefore collected counts alone do not establish autonomous delivery of evaluated opportunities.
8. **Failure observability is uneven.** Normal per-query/provider health is structured, but a top-level JobSpy exception can yield an apparently error-free, exit-0 empty CLI summary. A returned per-job evaluation failure still permits queue export, unlike an exception. **C(R2)**, `run_scan.py:89–96,171–172`, `run_all.py:84–104`. These are important when interpreting unattended runs, even though many regression cases pass.
9. **Semantic/AI components do not fill the retrieval gap.** Explicit local semantic reranking uses a bounded existing inbox slice and local model; contextual aliases and cloud evaluation act after retrieval. No evidenced path connects them to outbound query/source invention here. **S + T**, `jobhunter_app/semantic.py:153–172`, `jobhunter_app/matching.py:57–118`, `agents/evaluator.py:149–164`.

## 9. Remaining unverified behavior and completion boundary

- **Live service coverage:** no fresh successful search is claimed for LinkedIn, Indeed, Glassdoor, ZipRecruiter, Bayt, Naukri, BDJobs, HelloWork, Google, either HTML publisher, or any other source. Adapter registration, synthetic “success/partial,” installed package version and passing tests are not live verification.
- **Production conditions:** actual approvals, paused state, profile, user source list, credentials, proxies/browser setup, database size, deployment uptime and sustained cooldown scheduling were not inspected or changed. A new audit venv is not proof the user's deployment has that runtime.
- **AI/model quality:** cloud model responses, token/provider limits, legal eligibility, relevance recall, cross-language recall, and real local embedding model execution were not benchmarked.
- **Unexecuted paths:** no full live 210-configuration CLI run, credentialed social/USAJOBS search, real browser fallback, production migration, container build, or long-running scheduler trial. Several branches above are S-only even though related fixture tests passed; those distinctions are explicit.
- **Preservation:** this phase creates only `docs/jobhunter_autonomy_review/02_search_execution_trace.md` in the reviewed snapshot/publication. Baseline source hashes are checked before publication; no application implementation, runtime configuration, repository dependency file or existing data is changed.

**Part 2 complete:** actual initialization, configuration/query construction, source selection/retrieval, bounds, parsing/filtering/identity, description enrichment, evaluation, persistence/reporting and recovery have been traced with source-level evidence and controlled execution. Stop here; no solutions or subsequent-phase implementation were started.
