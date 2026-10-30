# Part 1 — Repository discovery and search-pipeline map

**Scope:** audit-only repository map, not a replacement architecture or implementation plan. Part 1 ends here; execution tracing belongs to the next phase.

**Inspection date:** 2026-10-30 UTC. **Source snapshot:** `shd2w/Jobs_hunter`, published commit `a840a08093a5f64b2827f3dffe77de9abb3a9942`. The first reference to each source file links to that commit, not a moving branch; subsequent references retain exact paths and line ranges.

## 1. Evidence standard and headline findings

- **Verified (static):** directly read implementation, configuration, test definition, or inspected environment fact. This does **not** mean the code was executed successfully.
- **Inferred:** a conclusion from named implementation relationships, not a measured runtime result.
- **Unknown:** requires runtime tracing, provider access, private deployment state, or additional evidence.

**Finding A — There are two orchestration paths, not one universal scanner pipeline.** The dashboard/CLI-source path schedules approved sources through `sources.scan`; the full scanner CLI runs Scrapling, direct employer APIs, and JobSpy, then uses a Markdown bridge. Their source sets, filtering points, persistence order, and evaluation steps differ. **Verified (static)** at [`jobhunter_app/automatic.py:164–208`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/automatic.py#L164-L208), [`jobhunter_app/sources.py:264–365`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/sources.py#L264-L365), and [`run_scan.py:57–111`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/run_scan.py#L57-L111).

**Finding B — Zero-input collection is implemented for a predefined universe.** Automatic setup seeds 16 source records, including two fixed-source Scrapling routes and all nine configured JobSpy identifiers. It can start with a blank profile; scheduling uses approval, due times, and checkpoints rather than asking for a URL every time. **Verified (static)** at `jobhunter_app/automatic.py:17–25`, `jobhunter_app/automatic.py:54–85`, and `jobhunter_app/automatic.py:164–208`. **Unknown:** which sources currently deliver valid live jobs in the target deployment.

**Finding C — This is not evidence of open-ended autonomous search discovery.** The inspected paths expand literal configured terms/locations, crawl two fixed HTML source definitions, or retrieve explicitly registered identifiers. The source directory constructs Google links but does not execute searches; saved searches query existing SQLite jobs. **Inferred within the inspected retrieval paths**, supported by [`scanners/jobspy_scanner.py:53–117`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/jobspy_scanner.py#L53-L117), [`jobhunter_app/scrapling_engine.py:10–38`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/scrapling_engine.py#L10-L38), [`jobhunter_app/source_directory.py:26–34`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/source_directory.py#L26-L34), and [`jobhunter_app/saved_searches.py:67–72`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/saved_searches.py#L67-L72). No claim is made that arbitrary code outside these paths could never perform a search.

**Finding D — Adapter presence and test names do not establish live coverage.** JobSpy tests replace `scrape_jobs`; automatic tests replace network transport and narrow the starter set; primary Scrapling tests use synthetic pages. **Verified (static)** at [`tests/test_all_jobspy_platforms.py:39–61`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_all_jobspy_platforms.py#L39-L61), [`tests/test_automatic.py:16–45`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_automatic.py#L16-L45), and [`tests/test_scrapling_engine.py:17–55`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_scrapling_engine.py#L17-L55). Provider availability remains **unknown in this audit**, including any statuses asserted in older documentation or source notices.

## 2. Repository and environment summary

### 2.1 Observed checkout and preservation boundary

| Item | Observation | Evidence / status |
| --- | --- | --- |
| Working directory / repository root | `/data/jobhunter-regression/current` | `pwd`, Git root inspection; **verified environment** |
| Remote / branch | `https://github.com/shd2w/Jobs_hunter.git`; local branch `main` | `git remote -v`, `git branch --show-current`; **verified environment** |
| Local HEAD | `31e610b059bc22596ab7081bb9d596b36e766eb4` | `git rev-parse HEAD`; **verified environment** |
| Published source baseline | `a840a08093a5f64b2827f3dffe77de9abb3a9942` | Downloaded the exact published archive and compared all 245 archive files against the working tree: zero mismatches; **verified file comparison**, not a test result |
| Dirty state at audit start | 14 modified paths and 7 nonignored untracked paths, listed below | Git porcelain snapshot taken before audit; **verified environment** |
| Contributor instructions | `AGENTS.md` points to `docs/RELEASE_POLICY.md`, requires disposable inputs, unchanged original CVs, honest deferred checks, and regression testing for changes | [`AGENTS.md:1–5`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/AGENTS.md#L1-L5); **verified static** |
| Runtime available | Python 3.13.15; existing scanner venv `/data/jobhunter-regression/scanenv` | Interpreter and installed-distribution metadata; **verified environment** |
| Runtime packages in that venv | `python-jobspy 1.4.1`, `scrapling 0.5`, `curl_cffi 0.17.0`, `protego 0.7.0`, `httpx 0.28.1`, `PyYAML 6.0.3`, `filelock 4.2.4`, `pytest 8.4.2`; corresponding module specs found | Read-only metadata/spec lookup; **verified environment**, not import/execution compatibility |
| Optional packages absent in that venv | `sentence-transformers`, `torch`, `google-genai` | Distribution metadata/module-spec lookup; **verified environment**. This does not prove all cloud evaluation paths are unavailable: OpenRouter is a separate path. |
| Container environment | No `docker` executable found | `command -v docker`; **verified environment**; no container build attempted |

The local dirty state predates this audit. Its contents match the published baseline; it must not be mistaken for changes introduced by the audit or reset to local HEAD. No existing application, configuration, dependency, or data file is part of this audit's intended change set.

Pre-existing modified paths:

```text
.github/workflows/tests.yml
README.md
docs/AUTOMATIC_DISCOVERY.md
docs/JOBSPY_ALL_PLATFORMS.md
jobhunter_app/automatic.py
jobhunter_app/source_directory.py
jobhunter_app/source_health.py
jobhunter_app/sources.py
requirements-scanners.lock
requirements-scanners.txt
requirements-scrapling.txt
requirements.txt
run_scan.py
tests/test_scraper_restoration.py
```

Pre-existing untracked paths, all present in the published source snapshot:

```text
docs/SCRAPLING_PRIMARY_ENGINE.md
docs/SCRAPLING_PRIMARY_VERIFICATION.json
jobhunter_app/scrapling_engine.py
jobhunter_app/scrapling_transport.py
scanners/scrapling_scanner.py
tests/test_scrapling_engine.py
tests/test_scrapling_transport.py
```

### 2.2 Structure relevant to this investigation

```text
run_local.py             local workflow CLI and dashboard startup
run_scan.py              scanner-family orchestration and legacy merge
run_all.py               scan -> cloud evaluation -> queue export
run_evaluate.py          pending Markdown jobs / explicit-URL evaluation
run_export_queue.py      explicit legacy evaluation-to-queue export
scanners/                BaseScanner, JobSpy, direct APIs, Scrapling, bridge/compat
jobhunter_app/           automatic coordinator, registered sources, bounded collectors,
                        network/transports, SQLite store, matching, web UI, imports
utils/                   legacy filtering/dedup, JD fetch/cache, evaluation store/export
agents/                  cloud evaluator, model routing, document-related consumers
config/portals.yml       search terms/locations/providers, filters, tracked companies
config/profile.yml       legacy profile/evaluation/model configuration consumer input
tests/                   48 test_*.py modules
qa/                      fixture/smoke/browser scripts and explicit live probes
.devcontainer/           development-host bootstrap
Dockerfile / compose    collection-only container entry path
.github/workflows/      regression and deployment configuration
docs/                    usage, release policy, prior verification artifacts
```

**Verified inventory**, not functionality inferred from names. The relationships of the search-critical files are substantiated below. The documented `run_scan.py`, `run_all.py`, `config/portals.yml`, and scanner modules all exist; no central file among these examples is missing.

### 2.3 Inspection actions and limits

Read code/config/test definitions; inspected Git state and package metadata; compared the source archive; parsed Python ASTs in `jobhunter_app`, `scanners`, `utils`, `agents`, `tests`, and `qa` with no syntax errors found. AST parsing does not verify imports, provider compatibility, or runtime behavior. No scanner, coordinator, evaluator, browser collection, pytest suite, container, or live probe was executed for Part 1. Historical passing-test counts and prior live reports are not presented as new verification. No private database, credential values, CV contents, or candidate profile values were used in this report.

## 3. Current execution entry points

| Entry point | Implemented dispatch and significance | Evidence / status |
| --- | --- | --- |
| `run_local.py main()` -> `serve` | `--manual-discovery` opts out; CLI passes `automatic=not args.manual_discovery`. This is the normal auto-enabled server launch, not a property of all web-server callers. | [`run_local.py:13–90`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/run_local.py#L13-L90), `run_local.py:250–253`; **verified static** |
| `web.make_server()` / `web.serve()` | Both function defaults are `automatic=False`; when enabled the server creates and starts `AutomaticDiscovery`, and stops it on close. Server binds loopback. `serve` creates a blank profile if needed. | [`jobhunter_app/web.py:32–34`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/web.py#L32-L34), `jobhunter_app/web.py:334–350`; **verified static** |
| `run_local.py` source commands | `source`, `scan`, `scan-batch`, `source-health`, and checkpoint reset expose registration and explicit source execution. `match` calls `Store.evaluate`. | `run_local.py:53–66`, `run_local.py:105–106`, `run_local.py:172–189`, `run_local.py:213–215`; **verified static** |
| Web manual-scan routes | Work is submitted to background task workers calling `sources.scan` or `source_health.batch`; automatic settings/check routes wake/control the coordinator rather than providing a second discovery algorithm. | `jobhunter_app/web.py:234–241`, `jobhunter_app/web.py:292–312`; **verified static** |
| `run_scan.py run_scan()` / `main()` | Default runs Scrapling, direct APIs, JobSpy in that order, then bridge + SQLite mirror. CLI supports fixed-source `--engine scrapling` and JobSpy site/term/location overrides. Does not iterate all `sources.POLICIES` adapters. | `run_scan.py:57–111`, `run_scan.py:142–172`; **verified static** |
| `run_all.py _run_pipeline()` | Calls scan; exits for dry-run, scan-only, or `new_added == 0`; otherwise calls `run_evaluate(mode='all')`, then `export_queue`. Thus its evaluation gate is legacy bridge additions, not every new SQLite row. | [`run_all.py:47–100`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/run_all.py#L47-L100); **verified static** |
| `run_evaluate.py run_evaluate()` | Reads unchecked Markdown jobs, or accepts an explicit URL; uses JD cache/fetching and the cloud evaluator. It is not a job-source discovery engine. | [`run_evaluate.py:59–97`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/run_evaluate.py#L59-L97), `run_evaluate.py:143–215`, `run_evaluate.py:364–415`; **verified static** |
| `run_export_queue.py main()` | Separate explicit export command downstream of evaluated records; exporter implementation is in `utils.queue_exporter`. | [`run_export_queue.py:35–86`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/run_export_queue.py#L35-L86), [`utils/queue_exporter.py:752–800`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/queue_exporter.py#L752-L800); **verified static** |
| `.devcontainer/start.sh` | Starts `python run_local.py serve --port 8765`; requires the host process to remain alive for automatic collection. | [`.devcontainer/start.sh:1–4`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/.devcontainer/start.sh#L1-L4), `.devcontainer/start.sh:31–37`; **verified static**; deployment uptime **unknown** |
| Container path | Dockerfile defaults to `python run_scan.py`; Compose loops that command with a 21,600-second sleep, not `run_all` or the dashboard scheduler. | [`Dockerfile:1–11`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/Dockerfile#L1-L11), [`docker-compose.yml:1–13`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/docker-compose.yml#L1-L13); **verified static**, not container-tested |

**Operational observation, not an execution recommendation:** importing `run_scan` creates `logs/scan.log`; scanner construction, store construction, and startup may create or update state. They were read rather than imported/run in this checkout. See `run_scan.py:39–44`, [`jobhunter_app/store.py:83–106`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/store.py#L83-L106), and [`scanners/bridge.py:28–46`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/bridge.py#L28-L46). **Verified static**.

## 4. High-level search-flow diagram

```text
A. Persistent local application path

run_local.py serve (auto by default at CLI)
  -> web.make_server(automatic=True)
     -> AutomaticDiscovery.configure: fixed starter registration + blank profile
     -> AutomaticDiscovery.loop / cycle
        -> approved sources, oldest-run-first, due/gate checks, <=10 attempts/cycle
        -> sources.scan [SQLite-associated scan lock]
           -> registered Source(kind, identifier) + checkpoint
           -> fetch dispatcher
              |-- JobSpy: configured query/page -> JobSpyScanner._run_search
              |              -> upstream scrape_jobs -> legacy title/location filter
              |-- Scrapling: fixed listing -> links -> <=3 JSON-LD detail pages
              |-- Native ATS/public APIs: fixed endpoint / registered board ID
              |-- RSS/HN/official platform posts: registered URL/ID + setup as needed
              `-- Wuzzuf/Naukrigulf: explicitly authorized listing + selected transport
           -> normalize / posts.process / feeds.ingest
           -> Store.ingest: canonical URL identity, sightings, invalid rows
           -> transactional checkpoint + run/source health
           -> selected families only: post-commit legacy Markdown/cache mirror
        -> optional deterministic Store.evaluate(profile)
        -> SQLite jobs/matches exposed through dashboard / local saved searches

B. Scanner-family CLI path

run_scan.py  <------------------- run_all.py
  -> ScraplingScanner (SQLite source path first; mirror_legacy=False)
  -> DirectAPIScanner (configured employers; none in current defaults)
  -> JobSpyScanner.scan (configured query loop)
  -> PipelineBridge.process [pipeline lock]
       -> title/location filtering -> legacy dedup -> pending pipeline.md + JD cache
  -> accepted sightings mirrored to SQLite (even repeated legacy observations)
                                    |
run_all.py: if legacy new_added > 0 --+
  -> run_evaluate(mode='all'): all pending Markdown items, not only current new rows
     -> cached JD / HTTP / permitted optional rendering
     -> agents.Evaluator -> SmartRouter -> configured cloud provider
     -> reports + durable evaluations.json -> tracker -> checked Markdown item
  -> utils.queue_exporter.export_queue -> application_queue.jsonl

Separate local/import path:
  files/feeds/posts -> import_records or staging -> SQLite
  saved_searches.run -> Store.jobs (local filtering only)
  semantic.rank -> bounded existing SQLite slice (local reranking only)
```

Diagram edges are **verified static call relationships** in the entry-point references above, `jobhunter_app/sources.py:156–254`, `jobhunter_app/sources.py:273–365`, [`scanners/scrapling_scanner.py:12–42`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/scrapling_scanner.py#L12-L42), `scanners/bridge.py:62–147`, [`scanners/compat.py:12–27`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/compat.py#L12-L27), `run_evaluate.py:348–359`, [`jobhunter_app/pipeline.py:11–75`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/pipeline.py#L11-L75), `jobhunter_app/saved_searches.py:67–72`, and [`jobhunter_app/semantic.py:153–172`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/semantic.py#L153-L172). End-to-end execution of these paths is **not verified by this audit**.

## 5. Search-related module inventory and implementation evidence

### 5.1 Orchestration, source identity, retrieval and normalization

| File / symbol | What implementation demonstrates | Status |
| --- | --- | --- |
| [`scanners/base.py:17–80`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/base.py#L17-L80) — `JobPosting`, `ScanResult`, `BaseScanner` | Shared scanner-family record/result contract; not the complete SQLite source orchestration API. | **Verified static** |
| `jobhunter_app/automatic.py:54–85` — `configure` | Creates a blank profile as needed; seeds predefined approved sources insert-only with revision tracking; preserves existing configuration rather than generating companies/queries. | **Verified static** |
| `jobhunter_app/automatic.py:99–126` — coordinator initialization/start | Configures seeds and performs legacy recovery; starts a daemon worker. `jobhunter_app/automatic.py:210–222` `_loop` owns the automatic lock and waits between cycles. | **Verified static** |
| `jobhunter_app/automatic.py:164–208` — `cycle`, `_match_if_needed` | Oldest-run ordering, approval/setup/due checks, 10-attempt bound, isolated `ValueError`, optional downstream matching. Profile skills/facts affect matching here, not outbound term generation. | **Verified static** |
| `jobhunter_app/sources.py:18–58` — `POLICIES` | Registry includes ATS/public/feed, nine prefixed JobSpy adapters, two Scrapling adapters, Wuzzuf/Naukrigulf, and official social-post adapters. Policy notices describe intended limits; they are not independent live evidence. | **Verified static** |
| `jobhunter_app/sources.py:93–148` — `Source` | Validates kind-specific identifiers and builds known endpoint URLs; employer ATS routes need a board/company identifier; feeds need a supplied permitted URL. | **Verified static** |
| `jobhunter_app/sources.py:156–190` — `fetch` | Dispatches to Scrapling, expanded JobSpy/public collectors, social APIs, authorized HTML collectors, bounded paged APIs, or ordinary network/API/feed fetches. | **Verified static** |
| `jobhunter_app/sources.py:193–254` — `normalize` | Converts provider-specific API payloads to common job dictionaries, or accepts already-normalized rows for relevant expanded/HTML adapters. [`jobhunter_app/source_rows.py:5–29`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/source_rows.py#L5-L29) `normalize_new` handles Jobicy/Arbeitnow/USAJOBS payload fields. | **Verified static** |
| `jobhunter_app/sources.py:255–270` — `register`, `scan` | Registration persists an explicit source and approval; scan holds a store-specific file lock. Neither function searches for new employers. | **Verified static** |
| `jobhunter_app/sources.py:278–354` — `_scan_locked` | Approval, family retry gate and cooldown precede fetch. Checkpoint is read before collection; jobs/checkpoint/completion are committed together for the ordinary collection branch. | **Verified static** |
| `jobhunter_app/sources.py:356–365` — legacy mirroring | Only JobSpy, expanded public, and Scrapling source families mirror to Markdown by this branch. Mirror failure is recorded after SQLite commit, not rolled back as if collection failed. | **Verified static** |
| `jobhunter_app/sources.py:367–411` — exception handling | Records cancellation, provider failures, missing runtimes/setup, access blocks and HTTP failures. This makes source health part of interpreting apparent empty/partial discovery. | **Verified static** |
| [`jobhunter_app/source_health.py:8–52`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/source_health.py#L8-L52) — `provider_family`, `retry_gate`, `health` | Maps Scrapling/native Jobicy and Arbeitnow to common provider families; computes effective next-allowed times and engine identity. | **Verified static** |
| `jobhunter_app/source_health.py:54–73` — `reset`, `batch` | Explicit reset affects checkpoints, not existing jobs/retry gates; batch is a bounded explicit source list, executed sequentially. | **Verified static** |
| [`jobhunter_app/network.py:32–100`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/network.py#L32-L100) — `public_addresses`, `PinnedHTTPS`, `get` | Shared bounded HTTP transport used by native collectors; this is transport, not source selection or search planning. | **Verified static** |

### 5.2 Scanner engines and source adapters

| File / symbol | Actual behavior and autonomy boundary | Status |
| --- | --- | --- |
| [`scanners/jobspy_registry.py:1–9`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/jobspy_registry.py#L1-L9) — `SITES`, `SCOPES` | The nine identifiers are `linkedin`, `indeed`, `google`, `bayt`, `glassdoor`, `zip_recruiter`, `naukri`, `bdjobs`, `hellowork`. All eight platforms named in the user context are represented; Google is additional. | **Verified static** registration/configuration; live operation **unknown** |
| `scanners/jobspy_scanner.py:53–117` — `_load_searches`, `_load_primary` | Supports explicit lists or deterministic terms × locations. Provider-specific configurations inherit configured primary terms. No profile/CV/LLM query generation in these functions. | **Verified static** |
| `scanners/jobspy_scanner.py:119–148` — `scan` | Loops configured searches with one executor worker and a two-second inter-search delay. Passing multiple `site_name` values delegates provider behavior to JobSpy; it is not repository-level parallel query orchestration. | **Verified static**; upstream concurrency **not independently established** |
| `scanners/jobspy_scanner.py:164–241` — `_do_search` | Imports actual `jobspy.scrape_jobs`; sets site/query/location/country, offsets, description options, remote flag, and Google query template. Captures provider metadata and treats errors plus an empty frame as failure. | **Verified static**; provider/API correctness at runtime **unknown** |
| [`jobhunter_app/expanded_sources.py:23–53`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/expanded_sources.py#L23-L53) — `collect` JobSpy branch | Selects one provider/query/page from checkpoint, caps page size, applies title/location filters before ingestion, rotates bounded pages/queries, reports `coverage_complete=False`. `request_unit` explicitly includes provider-managed detail requests. | **Verified static** |
| `jobhunter_app/scrapling_engine.py:10–38` — `SOURCES`, URL validation | Primary Scrapling engine has exactly two fixed publisher scopes: Jobicy `/jobs` and Arbeitnow home/listing path. It is not arbitrary-site crawling or an autonomous agent discovering new domains. | **Verified static** |
| `jobhunter_app/scrapling_engine.py:51–109` — `listing`, `postings` | Follows permitted listing/detail links and normalizes publisher JSON-LD `JobPosting`; unstructured job prose is not converted by a generative extractor here. | **Verified static**; current HTML compatibility **unknown** |
| `jobhunter_app/scrapling_engine.py:112–167` — `collect` | Robots retrieval/checking, at most five requests per call, three detail pages, 20-page/pass and 200-pending bounds, committed continuation state. Listing completion is distinct from `coverage_complete`, which remains false. | **Verified static** |
| [`jobhunter_app/scrapling_transport.py:24–75`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/scrapling_transport.py#L24-L75) — `get` | Uses actual Scrapling `FetcherSession` and version-sensitive `_curl_session` controls; no browser/stealth/proxy fallback is launched in this implementation. | **Verified static**, not a live transport test |
| `scanners/scrapling_scanner.py:12–42` — `ScraplingScanner` | Bridges the primary collector into scanner CLI; invokes SQLite source scan first with `mirror_legacy=False`, then maps sightings back into scanner results. Dry-run skips this crawl. | **Verified static** |
| [`scanners/workday.py:29–35`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/scanners/workday.py#L29-L35), `scanners/workday.py:64–122` — `KNOWN_ENDPOINTS`, `_load_companies`, `scan` | Direct engine is driven by explicit `tracked_companies`; current known fallback map contains Bosch/SmartRecruiters, while configured Workday entries require tenant details. Current `tracked_companies: []` means no default employer requests from this scanner. | **Verified static**, including config [`config/portals.yml:133–133`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/config/portals.yml#L133-L133) |
| `scanners/workday.py:124–164`, `scanners/workday.py:218–261` — `_scan_company`, provider methods, `_get_search_terms` | Explicit employer endpoint + configured company search terms; fallback term `working student`. A comment suggesting unknown employers are covered by JobSpy does not establish employer-specific coverage: no employer search constraint is added here. | **Verified static** implementation; employer coverage outside it **unknown** |
| [`jobhunter_app/collection.py:34–118`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/collection.py#L34-L118) — `collect` | Resumable SmartRecruiters details, Jobicy cursor feed, Arbeitnow page feed, USAJOBS keyword query with environment setup, and explicit HN hiring-thread comments. These are bounded retrievals, not discovery of new boards/threads. | **Verified static** |
| `jobhunter_app/expanded_sources.py:54–98` — public branches | RemoteOK API and WeWorkRemotely RSS are fixed public retrieval routes; separate from JobSpy and primary Scrapling. | **Verified static** |
| [`jobhunter_app/authorized_boards.py:14–49`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/authorized_boards.py#L14-L49), `jobhunter_app/authorized_boards.py:100–180` — `HOSTS`, `safe_url`, `parse`, `collect` | Wuzzuf/Naukrigulf require explicit permitted listing URLs; bounded details use publisher structured data. Authorization/robots/transport choices are configuration, not autonomous discovery. | **Verified static**, live access **unknown** |
| [`jobhunter_app/board_browser.py:29–62`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/board_browser.py#L29-L62), [`jobhunter_app/scrapling_parser.py:10–31`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/scrapling_parser.py#L10-L31) — transport/parser selection | Dedicated-browser transport and optional Scrapling parsing of already-fetched authorized-board HTML are separate from the primary Scrapling HTTP engine. Default authorized-board parser is `stdlib`. | **Verified static** |
| [`jobhunter_app/platform_posts.py:9–42`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/platform_posts.py#L9-L42), `jobhunter_app/platform_posts.py:78–118` — `KINDS`, `REQUIRED`, `collect` | LinkedIn organization, X user, subreddit, Telegram allowlist/bot, Discord channel scope require explicit identifiers and configured access. These are not platform-wide job-board search engines; LinkedIn post API is distinct from `jobspy_linkedin`. | **Verified static**, configured access/live validity **unknown** |
| [`jobhunter_app/feeds.py:32–82`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/feeds.py#L32-L82), [`jobhunter_app/posts.py:23–83`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/posts.py#L23-L83), `jobhunter_app/posts.py:229–274` — `parse`, `ingest`, `extract`, `process` | Feed/post content is classified; sufficiently complete source-backed vacancies may be auto-added and locally matched; ambiguous records remain review items. These consume supplied/registered content rather than finding new sources. | **Verified static** |
| `jobhunter_app/source_directory.py:26–34`, `jobhunter_app/saved_searches.py:67–72` | Directory returns metadata/search-link strings; saved searches execute `store.jobs` against existing records. Neither implements external web-search execution. | **Verified static** |

### 5.3 Filtering, deduplication, evaluation and persistence

| File / symbol | What implementation demonstrates | Status |
| --- | --- | --- |
| [`utils/filters.py:22–56`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/filters.py#L22-L56) — `TitleFilter.matches` | Negative terms take precedence, short positive terms use word boundaries, longer terms use substring matching, empty titles fail. This is deterministic configured matching, not semantic query expansion. | **Verified static** |
| `utils/filters.py:76–141` — `LocationFilter.matches`, `filter_jobs` | Substring allow/block lists; absent location/config can pass. Remote/location labels do not establish work eligibility. | **Verified static** |
| [`utils/dedup.py:21–24`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/dedup.py#L21-L24), `utils/dedup.py:28–142` — `DeduplicatorStore` | Canonical URL, historical pipeline/scan/application inputs, historical company-title and in-batch company-title-location rules. Not universal fuzzy cross-provider identity resolution. | **Verified static** |
| `scanners/bridge.py:62–147` — `PipelineBridge.process` | Flattens scanner results, filters, deduplicates, sorts posting-date strings, appends pending Markdown, caches descriptions, records history. `new_added` is this bridge's accepted additions. | **Verified static** |
| `scanners/compat.py:12–53` — mirror/recovery helpers | Bridges both stores and restores legacy records on first recovery. SQLite sightings and Markdown pending items are not interchangeable states. | **Verified static** |
| [`jobhunter_app/validation.py:33–53`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/validation.py#L33-L53), `utils/queue_exporter.py:240–296` — `normalize_job`, `canonicalize_url` | Required title/company, bounded strings, syntactic URL validation, shared URL canonicalization before local identity. | **Verified static** |
| `jobhunter_app/store.py:185–229` — `Store.ingest` | Identity is SHA-256 of canonical URL unless a known human-linked alias exists; repeat sightings update jobs/provenance, preserve richer descriptions, invalidate derived matches. Different URLs can remain separate despite similar titles. | **Verified static** |
| `jobhunter_app/store.py:20–23`, `jobhunter_app/store.py:46–70`, `jobhunter_app/store.py:83–106` | SQLite schemas hold sources/runs/audit/jobs/sightings/matches and checkpoints/provider gates; opening a Store can migrate schema and invalidate derived match caches. | **Verified static** |
| `jobhunter_app/store.py:231–246`, `jobhunter_app/saved_searches.py:67–72` — inbox query | Local text query/status filter over existing stored jobs; this “search” is not outbound retrieval. | **Verified static** |
| `jobhunter_app/store.py:272–286`, [`jobhunter_app/matching.py:37–73`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/jobhunter_app/matching.py#L37-L73) — `evaluate`, `match_job` | Evaluates all stored jobs for the profile using deterministic contextual lexical matching, exclusions and evidence-oriented rules. Separate from legacy cloud scores and outbound discovery. | **Verified static** |
| `jobhunter_app/semantic.py:119–129`, `jobhunter_app/semantic.py:153–172` — `load_encoder`, `rank` | Optional CPU-local, existing-model-only reranking of at most 200 stored jobs. Profile-derived semantic text ranks a bounded inbox slice; it does not submit search queries. | **Verified static**; optional runtime absent here |
| `jobhunter_app/pipeline.py:11–75`, `jobhunter_app/pipeline.py:92–167` — `import_records`, `export_uaa` | This similarly named “pipeline” implements file import/state reconciliation and historical evaluation export, not scanner orchestration or new cloud evaluation. | **Verified static** |
| [`utils/jd_cache.py:15–61`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/jd_cache.py#L15-L61), [`utils/jd_fetcher.py:109–240`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/jd_fetcher.py#L109-L240), `run_evaluate.py:143–211` | Legacy evaluation uses cached descriptions or fetches a known posting URL, with optional permitted rendering; this enriches an already-selected job, not source discovery. | **Verified static** |
| [`agents/evaluator.py:76–94`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/agents/evaluator.py#L76-L94), `agents/evaluator.py:131–209`, [`agents/smart_router.py:103–137`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/agents/smart_router.py#L103-L137) | Legacy `Evaluator` loads profile/CV inputs and routes model evaluation through Google then OpenRouter fallback; it saves reports, recalculates weighted scores and returns an evaluation. Credentials/provider success not checked. | **Verified static**, cloud execution **unknown** |
| `run_evaluate.py:348–359`, [`utils/evaluation_store.py:47–69`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/utils/evaluation_store.py#L47-L69) | Durable JSON evaluation append/update is lock-protected and atomically replaced before tracker update and Markdown checkbox completion. Report/evaluation storage is distinct from SQLite matches. | **Verified static** |
| `utils/queue_exporter.py:366–410`, `utils/queue_exporter.py:752–800` | Downstream evaluated-record queue projection; not an additional discovery source. | **Verified static** |

**Important cross-path distinctions (verified static, implications inferred):**

1. JobSpy's dashboard collector applies legacy filters **before** SQLite ingestion; ordinary normalized native API rows do not pass through that same filter call. Primary Scrapling scans store their normalized rows first; selected legacy mirrors filter afterward. Therefore inbox and Markdown populations need not match. Evidence: `jobhunter_app/expanded_sources.py:38–53`, `jobhunter_app/sources.py:330–365`, `scanners/compat.py:12–27`.
2. The scanner CLI filters accepted results for its inbox mirror, but its Scrapling stage has already used the SQLite source path. A later bridge rejection is not proof that no SQLite observation exists. Evidence: `scanners/scrapling_scanner.py:19–42`, `run_scan.py:98–111`.
3. SQLite transaction success does not guarantee legacy mirror success; the mirror is post-commit. Conversely legacy `new_added` is not SQLite `inserted`. Evidence: `jobhunter_app/sources.py:326–365`, `scanners/bridge.py:130–147`.
4. `run_all` skips evaluation when no new legacy additions are reported, and when it does evaluate it requests **all pending** Markdown items. It is not a per-current-scan SQLite evaluation loop. Evidence: `run_all.py:77–90`, `run_evaluate.py:392–405`.

## 6. Relevant configuration and source-input requirements

| Configuration / input | Verified implementation and scope |
| --- | --- |
| `config/portals.yml:title_filter`, `location_filter` | Positive/negative title terms and location allow/block lists. `config/portals.yml:1–66`, `config/portals.yml:66–131`, interpreted by `utils/filters.py:22–141`. **Verified static**. |
| `tracked_companies` | Empty list in the inspected defaults; no direct-employer scan population is supplied by default. `config/portals.yml:133–133`, `scanners/workday.py:64–105`. **Verified static**. |
| `jobspy_searches` | 14 literal terms × 7 locations = 98 query configurations, each selecting LinkedIn, Indeed, Google, Bayt; `results_wanted: 30`, `distance_km: 100`. `config/portals.yml:136–162`, `scanners/jobspy_scanner.py:93–115`. **Verified static/derived count**. |
| `jobspy_providers` | Glassdoor: 14 × 4 = 56 additional configs. ZipRecruiter, Naukri, BDJobs, HelloWork: 14 each, total 56. Combined registry: **210 query configurations**, not 210 HTTP requests; original four providers each participate in 98 configurations. `config/portals.yml:168–195`, `scanners/jobspy_scanner.py:53–65`. Test expectation independently encoded at `tests/test_all_jobspy_platforms.py:24–36`; **verified static**, test not run. |
| Remote/country scope | Added providers use configured native-country/remote scopes. A remote flag is not worldwide eligibility; actual provider interpretation remains **unknown**. `config/portals.yml:169–195`, `scanners/jobspy_scanner.py:184–217`. |
| Config resolution | Scanner CLI loads `config/portals.yml` relative to current directory; expanded source collector uses a module-relative `CONFIG` path. Launch directory therefore matters for the CLI path. `run_scan.py:47–54`, `jobhunter_app/expanded_sources.py:13–20`. **Verified static**. |
| Automatic state | SQLite `workflow_settings` namespace, `sources`, `source_checkpoints`, `provider_gates`; seed revision 3. Active persisted approvals, pauses, cooldowns and profiles were not opened. `jobhunter_app/automatic.py:24–85`, `jobhunter_app/store.py:11–23`. **Verified static** schema; actual user state **unknown**. |
| Fixed Scrapling seeds | Jobicy remote and Arbeitnow DE fixed definitions; optional scanner config `scrapling_sources` selects registry members rather than arbitrary websites. `jobhunter_app/scrapling_engine.py:10–25`, `scanners/scrapling_scanner.py:23–34`. **Verified static**. |
| ATS / HN / feed / USAJOBS | ATS board/company IDs, HN hiring story ID, permitted feed URL, or USAJOBS keyword + explicit key/user-agent are still needed outside seeded routes. `jobhunter_app/sources.py:97–148`, `jobhunter_app/collection.py:92–117`. **Verified static**; not automatically enumerated by these implementations. |
| Authorized HTML / social | Wuzzuf/Naukrigulf listing URLs + approvals and configured transport; social identifiers + authorized API setup. Separate from automatic starter list. `jobhunter_app/authorized_boards.py:31–49`, `jobhunter_app/platform_posts.py:17–42`, `jobhunter_app/automatic.py:17–23`. **Verified static**. |
| Legacy profile consumers | `config/profile.yml` evaluation threshold/German policy, model routing, CV/profile consumers are downstream inputs. The SQLite profile used by `Store.evaluate` is a different persistence interface; synchronization must not be assumed. `run_all.py:52–58`, `run_evaluate.py:373–385`, `agents/evaluator.py:76–94`, `jobhunter_app/store.py:272–283`. **Verified static** interfaces; effective private values **unknown**. |
| Dependency/deployment files | Scanner lock and Scrapling requirements exist; CI installs dev + scanner lock on Python 3.13. Docker declares Python 3.12 and scanner lock. This audit does not establish the container's compatibility. [`.github/workflows/tests.yml:9–25`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/.github/workflows/tests.yml#L9-L25), `Dockerfile:1–11`. **Verified static**. |

**Autonomy interpretation — inferred, bounded:** a new user need not provide URLs or exact queries for the existing starter universe because developers have already provided those choices. Configured query expansion and bounded within-site link discovery are real implementation mechanisms. They do not demonstrate autonomous employer enumeration, new-domain discovery, profile-to-retrieval-query synthesis, or adaptive query selection from search outcomes. The relevant evidence is the fixed starter registry, literal cross-product loader, fixed Scrapling registry, explicit `Source` identifiers, and local-only saved searches cited above. This is a map of the present boundary, not a proposal to replace it.

## 7. Relevant tests and verification scope

The repository contains **48 `tests/test_*.py` modules**. The following tests were located and their definitions inspected; **none were executed in this audit**. Counts are not passing-test claims. Fixture assertions demonstrate intended contracts only; successful current production access cannot be inferred from them.

| Concern | Exact tests / locations | What the test definition covers and does not prove |
| --- | --- | --- |
| Zero-input bootstrap / scheduling | `tests/test_automatic.py:16–45` `original_starter_scope`, `test_first_run_no_input_fetches_jobs`; `tests/test_automatic.py:76–122` failure isolation, cooldown, optional profile; `tests/test_automatic.py:167–178` fairness | Replaces network transport and restricts starters to the original three feeds. Not an all-16-provider live acceptance test. |
| Query registry / all platform identifiers | `tests/test_all_jobspy_platforms.py:24–61` `test_all_platforms_registered_without_removing_original_queries`, `test_every_platform_calls_actual_jobspy_identifier`, `test_added_provider_checkpoint_and_source_ingest` | Static registry assertions, fake `jobspy` module, fake collector search. Verifies intended IDs/rotation, not live jobs from each provider. |
| Original query preservation / offsets / errors | [`tests/test_scraper_restoration.py:33–95`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_scraper_restoration.py#L33-L95) query, metadata, failure, bootstrap and checkpoint tests | Config and mocked JobSpy behavior; useful for query expansion/rotation regression. |
| Primary Scrapling listing/detail discovery | `tests/test_scrapling_engine.py:28–55` getter fixture and `test_actual_scrapling_discovery_fields_and_three_step_continuation`; `tests/test_scrapling_engine.py:67–110` bounds, robots, malformed state, intake/mirror | Real parsing code over synthetic HTML with replaced transport. Not current publisher HTML availability. |
| Primary transport controls | [`tests/test_scrapling_transport.py:26–64`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_scrapling_transport.py#L26-L64) `test_fetcher_real_controls_pin_dns_disable_stealth_redirects_proxy_and_retries`, redirect/error/byte/cancel/DNS tests | Controlled session/DNS dependencies. “Real controls” in a name is not proof of successful external HTTP. |
| Registered sources / approval / persistence | [`tests/test_sources_local.py:13–60`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_sources_local.py#L13-L60) registry, unapproved no-network, normalization/health, cancellation/overlap | Local synthetic source execution contracts. |
| Native-source pagination / continuation | [`tests/test_phase3_sources.py:39–105`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_phase3_sources.py#L39-L105) configuration, directory, Jobicy cursor, Arbeitnow page tests | Fixture source shapes/checkpoints, not upstream schema stability. |
| Authorized boards / social posts | [`tests/test_authorized_boards.py:39–95`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_authorized_boards.py#L39-L95), [`tests/test_platform_posts.py:39–85`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_platform_posts.py#L39-L85) | Structured ingestion/resume, unsafe config, setup, approval and API/checkpoint behavior. Requires real permitted access for live conclusions. |
| Legacy filtering | [`tests/test_filters.py:28–56`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_filters.py#L28-L56) positive/negative/case tests; implementation at `utils/filters.py:22–141` | Deterministic filters; location/short-term cases elsewhere in same test module. Not a measured relevance/recall benchmark. |
| Legacy dedup + merge | [`tests/test_dedup.py:36–80`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_dedup.py#L36-L80), [`tests/test_bridge.py:72–125`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_bridge.py#L72-L125) | Repeated URLs/company-title rules, filtering, dry run, history and scanner errors. Separate from SQLite identity. |
| SQLite ingestion / identity | [`tests/test_local_store.py:26–65`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_local_store.py#L26-L65), [`tests/test_identity_golden_contract.py:107–127`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_identity_golden_contract.py#L107-L127), [`tests/test_phase2_pipeline.py:36–87`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_phase2_pipeline.py#L36-L87) | Canonical identity, repeated/partial import behavior, same-title/different-location handling, migration/state boundaries. |
| Local matching / local search | [`tests/test_phase4_matching.py:26–58`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_phase4_matching.py#L26-L58), [`tests/test_saved_searches.py:17–33`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_saved_searches.py#L17-L33), [`tests/test_semantic_local.py:33–62`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_semantic_local.py#L33-L62) | Evidence/context rules, saved query equivalence to inbox, bounded semantic reranking with controlled dependencies. Not external query generation. |
| Full-pipeline export dispatch | [`tests/test_run_all_export_integration.py:61–99`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/tests/test_run_all_export_integration.py#L61-L99) | Success/failure/no-new/dry/scan-only export contracts with mocked pipeline stages; not a real scan -> cloud -> export acceptance run. |
| CI and disposable smoke | `.github/workflows/tests.yml:17–25`, [`qa/phase6h_smoke.py:1–11`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/qa/phase6h_smoke.py#L1-L11), [`qa/source_fixture_coverage.py:1–13`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/qa/source_fixture_coverage.py#L1-L13) | CI declares pytest, smoke and Scrapling-runtime checks. Fixture smoke scripts exist; workflow declaration alone is not evidence a particular run passed. |
| Explicit live probes | [`qa/scraper_live.py:23–68`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/qa/scraper_live.py#L23-L68), [`qa/jobspy_platforms_live.py:38–71`](https://github.com/shd2w/Jobs_hunter/blob/a840a08093a5f64b2827f3dffe77de9abb3a9942/qa/jobspy_platforms_live.py#L38-L71) | Runnable collectors with explicit output/options. Not invoked here; their presence and historical artifacts cannot establish current live support. |

**Query-generation test gap, carefully scoped:** tests exist for configured terms/locations, Google query formatting, offsets, scopes and checkpoints. The mapped generation code is deterministic; no profile-to-outbound-query generator was found in these paths to test. That is not a claim that model-assisted local ranking is absent: it is a different subsystem with separate tests.

## 8. Important unknowns and constraints on conclusions

1. **Live provider availability and completeness — unknown.** No new external collection was performed. JobSpy's installed package and nine adapters do not prove nine working platforms. Notice strings such as Google's unavailability or historical board verification are implementation/documentation claims, not fresh observations. Relevant code: `scanners/jobspy_scanner.py:223–241`, `jobhunter_app/sources.py:37–48`, `jobhunter_app/source_directory.py:26–34`.
2. **Effective production state — unknown.** Private SQLite approvals, automatic enablement, source checkpoints, family gates, profile configuration, host uptime and configured credentials were deliberately not read. These determine whether statically available paths actually run. Relevant readers: `jobhunter_app/automatic.py:164–208`, `jobhunter_app/sources.py:278–305`.
3. **Import/runtime compatibility — partially constrained.** Metadata and AST checks succeeded; these do not exercise native curl, upstream JobSpy behavior, browser binaries, model assets, or system libraries. Primary transport relies on a pinned private session hook. Optional local semantic packages and Google SDK are absent in the inspected venv; other provider paths may remain available. Relevant boundaries: `jobhunter_app/scrapling_transport.py:32–60`, `jobhunter_app/semantic.py:119–129`, `agents/smart_router.py:42–55`.
4. **Deployment compatibility — unknown.** Docker is unavailable here and no image was built. Python 3.12 Docker declaration differs from this Python 3.13 audit/CI environment. No conclusion of success or failure is drawn without an actual build/run. `Dockerfile:1–11`, `.github/workflows/tests.yml:13–18`.
5. **Coverage under scheduling budgets — unknown in practice.** Ten attempts/cycle, per-provider gates, bounded JobSpy pages, rotating configured queries and pending Scrapling details constrain throughput. File inspection establishes the algorithms, not elapsed full-pass coverage or starvation-free behavior in a real deployment. `jobhunter_app/automatic.py:171–200`, `jobhunter_app/expanded_sources.py:33–53`, `jobhunter_app/scrapling_engine.py:152–167`.
6. **Cross-store population/identity differences — inferred risk requiring trace.** Prefiltering, SQLite URL/alias identity, legacy heuristic identity, post-commit mirrors and `new_added` evaluation gating are observably different. Their actual effect on missed/duplicate/pending jobs has not been quantified. Evidence: Section 5.3 and its four cross-path distinctions.
7. **Error/summary boundaries — static observation, runtime consequence unknown.** `run_scan` appends a failure `ScanResult` for a top-level Scrapling exception; top-level direct/JobSpy exceptions are logged without adding equivalent failure results in those handlers. Bridge summary and CLI exit status should therefore be traced against actual failure branches before treating summaries as exhaustive health evidence. `run_scan.py:69–96`, `run_scan.py:130–172`.
8. **Description completeness / source schema freshness — unknown.** JSON-LD availability, provider description fetches, native API payloads and JD-fetch fallback behavior were not exercised. A saved listing URL or accepted schema fixture is not proof of a complete evaluable job description. `jobhunter_app/scrapling_engine.py:67–109`, `jobhunter_app/collection.py:66–100`, `run_evaluate.py:163–211`.
9. **No central documented file missing; optional access remains conditional.** The named entry points/configuration and actual `jobspy`/`scrapling` packages are present. Missing optional packages, unverified API credentials, absent Docker, unprovisioned/uninspected model/browser assets and intentionally unopened private data limit runtime claims, not the static repository map. No dependencies or configuration were installed/changed to remove those limits.
10. **Test coverage is not an autonomy benchmark.** Offline fixtures cover many intended paths but do not measure source discovery, new-employer reach, real query quality, global recall, or sustained provider availability. This audit did not perform such a benchmark or reuse prior test totals as current evidence.

## 9. Files to examine most closely in the next phase

Priority is for tracing existing execution, not proposing replacements:

| Priority | Exact files / symbols | Question the next-phase trace should resolve |
| --- | --- | --- |
| 1 | `run_local.py:250–253`, `jobhunter_app/web.py:32–34`, `jobhunter_app/automatic.py:54–85`, `jobhunter_app/automatic.py:164–222` | Which startup path enables automatic mode, which persisted state is consulted, and which sources are due/attempted? |
| 2 | `jobhunter_app/sources.py:264–365`, `jobhunter_app/source_health.py:8–73` | Trace one scan through approval, shared gate, checkpoint, fetch, ingestion, completion and mirror without conflating their outcomes. |
| 3 | `config/portals.yml:136–195`, `scanners/jobspy_scanner.py:53–148`, `scanners/jobspy_scanner.py:164–241`, `jobhunter_app/expanded_sources.py:23–53` | Trace one selected provider/query/page and compare full CLI expansion against automatic rotation/error accounting. |
| 4 | `jobhunter_app/scrapling_engine.py:112–167`, `jobhunter_app/scrapling_transport.py:24–75`, `scanners/scrapling_scanner.py:19–42` | Trace fixed listing discovery, pending details, bounds, committed state and CLI re-emission; distinguish parser success from live transport success. |
| 5 | `run_scan.py:57–111`, `scanners/bridge.py:62–147`, `scanners/compat.py:12–53`, `utils/filters.py:22–141`, `utils/dedup.py:101–142` | Where are candidates filtered/deduplicated and what populations/summary counts reach each persistence path? |
| 6 | `jobhunter_app/store.py:185–246`, `jobhunter_app/validation.py:33–53`, `utils/queue_exporter.py:240–296` | Follow URL normalization, aliases, update identity, provenance, invalid rows and match invalidation. |
| 7 | `run_all.py:65–100`, `run_evaluate.py:143–215`, `run_evaluate.py:348–415`, `agents/evaluator.py:131–209` | Follow the legacy `new_added` gate, pending selection, description requirements, evaluation persistence and queue dispatch. |
| 8 | `jobhunter_app/collection.py:34–118`, `jobhunter_app/platform_posts.py:78–118`, `jobhunter_app/posts.py:229–274`, `jobhunter_app/feeds.py:78–82` | Trace explicit source inputs and structured-post intake separately from job-board queries. |
| 9 | `jobhunter_app/store.py:272–286`, `jobhunter_app/matching.py:57–73`, `jobhunter_app/semantic.py:153–172`, `jobhunter_app/saved_searches.py:67–72` | Confirm the downstream matching/local-search boundary; do not mistake local ranking text for outbound retrieval queries. |

## 10. Part 1 completion boundary

Repository discovery and the static search-pipeline map are complete. This report is the only intended repository addition for this phase. No replacement design, application implementation, runtime configuration change, dependency installation, private-data update, or live-provider claim is included. Dynamic execution tracing and any implementation work are explicitly deferred.
