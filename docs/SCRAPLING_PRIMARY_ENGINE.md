# Scrapling as a primary JobHunter scraping engine

This is the first primary-engine rollout, not a claim of universal site support. Scrapling now performs **HTTP fetching, listing discovery, structured detail extraction and resumable crawling**, using the existing source approval, scheduler, health, SQLite intake and legacy pipeline. It is no longer limited to the earlier optional HTML parser.

## Primary engines coexist

| Engine | Role |
|---|---|
| Scrapling HTTP + Selector | Fixed public Jobicy and Arbeitnow HTML listings and publisher JobPosting details |
| JobSpy | All eight requested job boards plus the preserved Google route, with provider-specific scopes |
| Native public APIs / feeds / direct scanners | Existing adapters, regional/browser workflows and supported ATS integrations remain available |

No prior engine, source configuration or stored vacancy was removed. Wuzzuf/Naukrigulf's separate optional Scrapling parser setting remains available and is not needed for the primary engine. A blocked JobSpy provider is not automatically retried through Scrapling.

## Default entry points

Standard `requirements-scanners.lock` now includes the pinned `scrapling[fetchers]==0.5` runtime and its Python dependencies. Codespaces, Docker and CI already install this lock. No browser binaries, browser process, MCP service or extra LLM agent are automatically installed/launched.

On normal dashboard startup, the insert-only revision-3 source upgrade adds:

- `scrapling_jobicy:remote` — `https://jobicy.com/jobs`
- `scrapling_arbeitnow:de` — `https://www.arbeitnow.com`

Their labels begin with **Scrapling** and engine identity/provider family are exposed in health and automatic status. They join oldest-due scheduling, progressive job intake and pause/resume. Existing approvals, blocked/paused sources, profiles, application states, checkpoints, provider gates and other settings are retained. If a publisher's native route ran recently, its Scrapling route correctly waits for the same publisher cooldown.

The original full `python run_scan.py` includes a `BaseScanner` bridge to the same engine. It uses the same `data/jobhunter.sqlite3` ledger/checkpoints rather than a separate scraping database. The bridge suppresses the immediate legacy mirror so the master scan's existing merge writes the pipeline once. The dashboard/source-scan path retains its immediate legacy mirror. Original title/location filtering and historical company/title blocking remain unchanged.

For a bounded Scrapling-only run:

```sh
python run_scan.py --engine scrapling --data-dir data
```

Do not run this alongside the dashboard against the same workspace. Existing locks and publisher gates apply; this is not a way to bypass a cooldown. The full Compose loop remains the alternative six-hour collection mode. `--dry-run` explicitly skips stateful Scrapling fetching and persistence, instead of writing records under a misleading dry-run label; original scanner dry-run behavior remains.

## Crawl and extraction contract

- Fixed source registry and canonical HTTPS URL/path patterns; no arbitrary user URL, remote code, account page or source-generated adapter.
- One scan performs at most five HTTP requests: crawler rules, one listing if needed, and at most three detail pages. A pending-detail continuation usually uses only rules plus those details.
- Crawler rules are fetched and checked every scan with Protego. At least one-second spacing and declared crawl-delay/request-rate are respected; unsupported slow policies fail closed rather than being ignored.
- Scrapling Selector discovers public detail links and explicit next links. A checkpoint records pending details, listing URL, visited pages and page index. At most 200 pending details and 20 listing pages. No AJAX/private endpoint is reverse-engineered as pagination.
- Publisher `JobPosting` JSON-LD supplies title, organization, description, salary when declared, employment type, posting date, original URL and applicant-location restrictions. Missing fields are not invented. Remote labels retain declared applicant countries; they are not represented as global eligibility.
- Changed/unstructured layouts, ambiguous/unsafe pagination, denied crawler rules and challenges stop collection. They are not successful empty coverage.
- SQLite job writes, source metrics and checkpoints commit together through existing intake. Failure/cancellation cannot advance a checkpoint or remove existing jobs. Repeat canonical URLs update sightings instead of duplicating jobs.

Native and Scrapling Jobicy paths share the `jobicy` provider family; native and Scrapling Arbeitnow paths share `arbeitnow`. The same one-hour family cooldown applies in either direction. A 429 applies Retry-After and pauses the family; checkpoint reset/reapproval does not clear its gate. A 403/challenge pauses the blocked Scrapling source. There is no automatic alternate-transport fallback, proxy rotation or challenge-solving step.

## Scrapling fetching safety

`jobhunter_app/scrapling_transport.py` calls actual Scrapling `FetcherSession`, not the old stdlib fetcher under a new name. It uses verified TLS, public-address validation and DNS-pinned libcurl connections, disables environment proxies and browser impersonation/stealth headers, follows no redirects, performs one attempt and discards cookies.

Responses have a five-MiB byte cap (crawler rules: 256 KiB), a 20-second request/read budget and cancellation checks, including streaming callbacks. Browser/dynamic/stealth modes are not enabled in this rollout. Fetcher dependencies include browser client Python packages, but no browser binaries are downloaded or launched by JobHunter.

Scrapling 0.5 does not expose DNS pinning as a public FetcherSession constructor option. The adapter uses one isolated, guarded, version-pinned `_curl_session` hook to configure libcurl's public `curl_options`/`trust_env` fields. If that hook changes, fetching fails closed before the request. This seam requires retesting before a Scrapling version upgrade; it is not claimed to be version-independent.

## Actual live production-path verification

Both samples ran through `qa/scraper_live.py` → `sources.scan` → Scrapling FetcherSession → discovery/detail parsing → SQLite intake, source health and committed checkpoints, not only parser fixtures. Aggregate evidence is in [SCRAPLING_PRIMARY_VERIFICATION.json](SCRAPLING_PRIMARY_VERIFICATION.json).

| Source | Requests | Received / valid | New SQLite jobs | Saved continuation |
|---|---:|---:|---:|---|
| Jobicy HTML | 5 | 3 / 3 | 3 | 7 pending detail pages |
| Arbeitnow HTML | 5 | 3 / 3 | 3 | 47 pending detail pages |

All six samples had title, company, original URL, location, description, employment type and publication date. Declared salary availability is recorded in the machine-readable field counts; missing source salary remains blank. Re-ingesting each same three-row sample inserted **zero** new jobs and updated three existing sightings/records. This repeat-intake check reused downloaded rows; it was not another network scrape.

The original title filters rejected the first three records from each sample for legacy Markdown intake. The broader SQLite inbox retained the valid source-backed vacancies. Six collected records are not a claim of six personally suitable opportunities. No current vacancy body or private workspace is committed.

This sample validates one listing and three details per publisher, not every detail or a complete site. Continuation/pagination, rollback, source-family gates, cancellation and no-fallback behavior are fixture-tested. A live multi-hour continuation was not performed by resetting cooldowns.

## Regression and deployment verification

**Full local regression suite: 1,764 tests passed** in 58.47 seconds. Tests exercise actual Scrapling parsing with fixture HTTP responses, Fetcher request configuration, DNS/TLS controls, proxy/redirect/retry restrictions, byte limits, crawler rules, scope violations, changed layouts, structured fields, checkpoints, cancellation, rollback, canonical deduplication, default scheduler wiring, insert-only upgrade, shared publisher cooldowns/429 gates and the master CLI bridge. The integrated 47-operation synthetic HTTP smoke and dependency checks are also rerun; synthetic smoke is not live source evidence.

Local Linux/Python 3.13 collection and dependencies were verified. Remote Codespaces startup, Docker daemon execution, Windows and JavaScript/browser crawling were not newly verified. Existing Bayt/Glassdoor/ZipRecruiter/Google/Wuzzuf access limitations and authorized API setup requirements remain; Scrapling does not make them silently accessible.

## Update and verify

Preserve local changes first:

```sh
git pull --ff-only
python -m pip install -r requirements-scanners.lock
bash .devcontainer/start.sh --restart
```

No parser environment toggle is needed. Open the dashboard's source status; the new Scrapling sources should be queued, running, in a shared cooldown or reporting an explicit error.

Optional live verification against a separate private test workspace:

```sh
python qa/scraper_live.py --source scrapling_jobicy:remote --source scrapling_arbeitnow:de --output /PRIVATE/scrapling-verification
```

Do not run this concurrently with production collection or repeatedly create fresh workspaces to bypass publisher cooldowns. Source approval and robots compliance are not blanket permission for unrelated uses; review the publisher's terms for deployment and retain attribution/backlinks.

## Files changed

- `jobhunter_app/scrapling_transport.py`: real bounded Scrapling HTTP fetching.
- `jobhunter_app/scrapling_engine.py`: fixed source registry, discovery, JSON-LD extraction, robots and resumable crawl.
- `jobhunter_app/sources.py`: engine registration, production dispatch/intake, runtime errors and family gates.
- `jobhunter_app/source_health.py`: shared publisher identity, due times and engine visibility.
- `jobhunter_app/automatic.py`: default source seeding, version-3 insert-only migration and engine labels/status.
- `jobhunter_app/source_directory.py`: current engine metadata and corrected JobSpy coverage description.
- `scanners/scrapling_scanner.py`, `run_scan.py`: existing BaseScanner/master-scan bridge and Scrapling-only mode.
- `requirements-scanners.txt`, `requirements-scanners.lock`, `requirements-scrapling.txt`, `requirements.txt`: standard fetching runtime and pins.
- `.github/workflows/tests.yml`: primary fetching import/dependency/engine contracts.
- `tests/test_scrapling_engine.py`, `tests/test_scrapling_transport.py`, `tests/test_scraper_restoration.py`: engine and compatibility contracts.
- `README.md`, `docs/AUTOMATIC_DISCOVERY.md`, `docs/JOBSPY_ALL_PLATFORMS.md`, this report and aggregate evidence: current behavior, migration, usage and limitations.
