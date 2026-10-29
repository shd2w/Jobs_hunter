# Scraper restoration and additive expansion — 0.4.1

Verified 2026-10-29 against the supplied `JobHunter-main - Copy.zip` and repository baseline `0e990e06a65051ab33008e9823d2c3e0f118f891`. This report separates restoration, inherited defects, new adapters and access limitations. No private source data or collected vacancy bodies are published.

## 1. Investigation: what actually regressed

The original scraper code was **not deleted wholesale**. Before this repair, `run_scan.py`, `scanners/base.py`, `scanners/workday.py`, `scanners/bridge.py`, `utils/filters.py`, `utils/dedup.py` and `config/portals.yml` matched the supplied original byte-for-byte. The existing JobSpy wrapper had only changed broad exception handling. That does not excuse the regression: the replacement default entry point no longer executed this code.

Specific disconnected/overwritten paths:

- New `run_local.py` / `jobhunter_app.automatic` executed only the three new starter feeds. Nothing called the original JobSpy searches or original direct scanner from that coordinator.
- Codespaces installed only `requirements-local.lock`, omitting JobSpy/pandas/curl_cffi/dotenv. The old scanner remained on disk but was not runnable from the default runtime.
- Docker changed from the original scanner/full-pipeline environment to minimal local dependencies and `run_local.py init`. Compose lost the six-hour collection loop and `restart: unless-stopped`.
- Original Markdown/TSV/JSON/XLSX records were not connected to the new SQLite inbox. No automatic recovery surfaced that historical workspace.
- The source directory incorrectly described Indeed/LinkedIn as unimplemented, despite the legacy adapter, and described no Workday CXS support despite the preserved module.

**Why:** an automatic-first dashboard was introduced as a separate execution/data path rather than integrating the original registry, scanners and persistence. Dependency, startup, scheduling and migration coverage were not included in the original acceptance tests. The simplified three-feed scenario passing did not establish legacy compatibility.

Repository Git history begins with sanitized publication batches, not the original upstream development history. It cannot establish when every pre-publication change occurred. The supplied archive is the comparison baseline; no unverifiable historical commit is claimed.

Original active configuration was ten English terms × seven locations (70 query configurations), each targeting LinkedIn, Indeed and Google. The locations were Oman, Egypt, UAE, Germany, Switzerland, Austria and Remote. **`tracked_companies` was empty in both originals**: Bosch was supported in the direct scanner's code, not an actively configured original employer scan. No invented Siemens/Adidas/Puma direct integration has been claimed restored.

## 2. Original capabilities restored

- Original JobSpy scanner, compact and explicit query formats, all original terms/locations/sites retained.
- Full `python run_scan.py` scan → original title/location filtering → deduplication → `pipeline.md`, `scan-history.tsv`, `jd_cache.json` retained, now also writing accepted sightings to the SQLite inbox.
- `python run_all.py --scan-only` preserved. Paid evaluation/preparation remains a separate optional path; unrelated retired CV rewriting is not re-enabled.
- Original direct scanner retained and repaired: BoschGroup SmartRecruiters account handling, pagination/detail extraction, explicit public Workday tenant/board configuration and visible errors. Workday is not automatically configured or claimed live verified.
- Scanner runtime installed by Codespaces/Docker, with tested Python 3.13 transitive pins in `requirements-scanners.lock`.
- Compose's six-hour collection loop and restart behavior restored **for collection**. It does not silently start paid model evaluation. No backend network port is exposed by this restoration.
- Original Markdown files coexist with SQLite; neither workflow is replaced. Dashboard JobSpy/public remote results mirror into the legacy pipeline through its original filters. The public-feed inbox may contain broader results than the filtered legacy pipeline.
- One-time historical recovery backs up source bytes and SQLite before archival/import. Existing jobs, notes and current application states are not reset. Conflicting historical identities remain archived without automatic links, not overwritten.

## 3. Additions and reliability repairs

### Newly added source adapters

1. **Bayt through the original JobSpy stack**: additional MENA discovery, but currently HTTP403-blocked from this environment. Implemented is not the same as accessible.
2. **Remote OK public JSON**: publisher attribution/backlink retained, metadata row excluded, actual salary amounts preserved without guessed currency/type/location.
3. **We Work Remotely public RSS**: structured company/title, description, region, employment type and publication date; attribution/backlink retained. Not a generic HTML crawler.

Existing Jobicy, Arbeitnow, Remotive, Greenhouse, Lever, Ashby, SmartRecruiters, generic feeds, HN, USAJOBS, Wuzzuf/Naukrigulf and all five platform-post adapters remain supported; none was replaced by these additions.

### Geographic/language and collection changes

- Added German queries `Softwareentwickler`, `Datenanalyst`, `Werkstudent Informatik`, `KI Entwickler` and corresponding positive title-filter terms. All original English queries remain: now 14 × 7 = **98 configured searches** across the same seven locations, with Bayt appended to the three original sites.
- Automatic JobSpy units rotate one provider/query/page at a time, five-minute conservative local cooldown; default maximum two pages/query, configurable up to five. Full manual scans keep the original first-page-per-query behavior; the bounded adapter adds continuation without claiming exhaustive coverage.
- Provider failures in `DataFrame.attrs` now surface instead of becoming successful zero-job results. Partial provider results remain usable. Google search text is passed explicitly; its upstream outage is still reported. Failed provider units back off at least one hour; Google is checked at most daily.
- Preserve full JobSpy descriptions (remove old 5,000-character truncation), employment type, finite salary values/currency/interval and proper missing values. No guessed salary/currency or eligibility.
- Arbeitnow's actual API page has 300 records, not 100. A bounded ceiling of 1,000 per page fixes rejection of the entire live response.
- Static Greenhouse/Lever/Ashby adapters have a 32 MiB response ceiling instead of the generic 5 MiB ceiling that rejected genuine large employer boards. Arbitrary feeds retain the smaller bound; common 10,000-row intake bound remains.
- Ashby compensation summaries and Lever commitment/type preserved. Authorized board JSON-LD now preserves declared employment type and base salary.
- Canonical URL deduplication, repeat sightings and richer-field retention; same company/title in different locations no longer collapses merely because it was seen earlier in the same batch. Historical application company/title blocking remains for compatibility; fuzzy syndicated dedup is not presented as solved.
- JD cache respects the selected data directory. Shared pipeline file lock, insert-only versioned source seeding and persisted cancellation/cooldowns preserve existing state.
- Original direct scanner no longer reports non-200/query failures as clean empty results. Successful jobs survive individual SmartRecruiters detail failures; Workday summary listings survive missing detail fields.

## 4. Actual live results

These are bounded samples from this machine, not total job counts, guaranteed freshness, completeness, hiring fit or continuous availability. A fresh automatic coordinator cycle, with no profile input, inserted **620 unique jobs in 21.33 seconds**: Arbeitnow300, Jobicy100, Remotive12, RemoteOK99, WWR96, original Indeed3 and LinkedIn10. Bayt and Google failed independently; working sources continued. Original filters were applied to the JobSpy automatic results.

| Source/path | Live result | Important detail |
|---|---:|---|
| Original JobSpy Indeed | 15 valid jobs | 3 each: Egypt, Oman, UAE, Germany, Remote; Germany used `Softwareentwickler` |
| Original JobSpy LinkedIn jobs | 15 valid jobs | Same five-location sample, 3 each; separate from the authorized LinkedIn **posts** API |
| Original Google Jobs | Failed | Provider returned “no job data returned”; upstream documentation says currently unavailable |
| New Bayt | Failed | HTTP403 for all five regional samples; no proxy/challenge bypass used |
| Jobicy | 100 valid jobs | One page; further cursor available; delayed public feed |
| Arbeitnow DE | 300 valid jobs | Fixed page-size rejection and preserved one longer declared employment-type value; next page checkpoint retained |
| Remotive | 12 valid jobs | One delayed public response, attribution preserved |
| New Remote OK | 99 valid jobs | One public API response; attribution/metadata rules handled |
| New We Work Remotely | 96 valid jobs | One public RSS response; titles, companies and declared fields extracted |
| Greenhouse / Stripe | 736 valid jobs | Live large response failed before byte-limit repair, then collected successfully |
| Lever / Palantir | 302 valid jobs | Live response and complete declared commitment/type fields; no publication timestamp invented |
| Ashby / OpenAI | 813 valid jobs | Live response; 646 declared salary summaries preserved, all 813 employment types |
| Existing SmartRecruiters / BoschGroup adapter | 10 valid jobs | 11 requests: one list + ten details, continuation retained; not all 5,035 reported vacancies |
| Original `DirectAPIScanner` / Bosch | 2 valid jobs | Bounded actual original scanner run, one page/two details, correct account, descriptions/type/date, no errors |
| HN Who is hiring | 10 comments retrieved | All ten staged for review; **zero** falsely claimed job imports |
| Generic RSS/Atom | 96 WWR entries retrieved | Actual generic-feed scan staged 42 for review, skipped 54 and auto-added zero; dedicated structured WWR adapter above adds its 96 valid vacancies |
| Wuzzuf | Currently blocked | Direct HTTP and current ordinary-browser route both failed; an older four-job success is not reused as current evidence |
| Naukrigulf | 4 valid jobs via ordinary browser | Five top-level navigations; normal assets added 529 requests. Direct HTTP timed out. Committed checkpoint retains 26 pending details |
| Workday | Not live configured | No original tenant/board configuration was supplied; explicit configuration and failure handling are regression-tested, not a fabricated live pass |
| USAJOBS | Setup required | API key/agent absent; no authorized live claim |
| LinkedIn posts, X, Reddit, Telegram, Discord | Setup required | Required official access/tokens/source IDs absent; original adapters retained and fixture-tested, not live connected |

### Extracted field checks

Every imported sample passed common title/company/URL validation. Fields absent at the source are left blank, never inferred. Counts below are **nonempty fields**, not guarantees of employer truth:

| Source sample | Jobs | Location | Description | Salary | Employment type | Publication date |
|---|---:|---:|---:|---:|---:|---:|
| Arbeitnow |300|283|300|0|195|300|
| Ashby |813|813|813|646|813|813|
| Lever |302|302|302|0|302|0|
| Remote OK |99|43|99|23|0|99|
| We Work Remotely |96|96|96|0|96|96|
| Remotive |12|12|12|7|12|12|
| Original direct Bosch sample |2|2|2|0|2|2|

Live payloads already fetched were reprocessed after metadata fixes to validate final normalization and repeat-ingest dedup, without claiming another independent provider response. Greenhouse does not provide a confirmed publication date in the sampled payload; updated time is not relabeled as publication. Lever's internal creation time is likewise not asserted as a publication date. JobSpy source field counts for each region are in [aggregate machine-readable evidence](SCRAPER_VERIFICATION.json).

The actual original CLI was also run, not just individual adapters:

```sh
python run_scan.py --site indeed --location Egypt --term 'Software Engineer' --limit 5 --data-dir /PRIVATE/workflow-data
```

It collected five genuine listings, retained one through the **original** configured filters and wrote that job to the legacy pipeline/cache/history **and** the SQLite inbox. The four title-filter rejections are not a network failure.

## 5. Preservation and regression tests

On a private copy of the supplied data, recovery inserted **1,107 unambiguous jobs**, archived **6,208 historical records**, identified **22 conflicting rows across 20 canonical job URLs**, and preserved 220 historical recommendations without inventing missing job links. No file parse errors or invalid normalized candidate records. Conflicts require identity review; those records remain in the archive and original files, not lost. Repeating recovery inserted zero jobs. Original source file hashes remained unchanged. The two dated XLSX backups remain untouched and are not redundantly imported.

- Full local regression suite: **1,692 tests passed** after the final structured-board-field test.
- Existing integrated synthetic smoke: **47 HTTP operations passed**, including private export boundaries and separate database/pack backup checks; unchanged source CV hash.
- Automatic UI smoke: six desktop/mobile/light/dark states, progressive results, failure isolation, persistent pause, draft preservation, no overflow/JS errors/external browser requests. Synthetic UI traffic is not live scraping evidence.
- New regression contracts cover original registry preservation, German additions, JobSpy fields/provider errors/offsets, provider/query/page checkpoint rotation, seed upgrades without state reset, legacy-to-SQLite and dashboard-to-legacy persistence, migration bytes/idempotency, canonical/location-aware dedup, Arbeitnow page sizing, scoped ATS byte limit, SmartRecruiters account/detail handling, salary/type extraction and honest errors.

## 6. Architecture and modified files

This is an additive bridge, not a replacement framework. Legacy scanners remain `BaseScanner`/`JobPosting`/`ScanResult`; `PipelineBridge` still owns original Markdown/filter/dedup/cache output. `scanners.compat` connects that output and historical records to SQLite. `jobhunter_app.expanded_sources` adapts the original JobSpy scanner plus two fixed-host public feeds into existing `Collection` checkpoints and common intake. Original public ATS/social adapters remain in place.

Modified/added files in this repair:

- `.devcontainer/devcontainer.json`
- `.github/workflows/tests.yml`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `config/portals.yml`
- `docker-compose.yml`
- `docs/AUTOMATIC_DISCOVERY.md`
- `docs/GITHUB_HOSTING.md`
- `docs/RELEASE_POLICY.md`
- `docs/SCRAPER_RESTORATION.md`
- `docs/SCRAPER_VERIFICATION.json`
- `jobhunter_app/authorized_boards.py`
- `jobhunter_app/automatic.py`
- `jobhunter_app/collection.py`
- `jobhunter_app/expanded_sources.py`
- `jobhunter_app/source_directory.py`
- `jobhunter_app/sources.py`
- `jobhunter_app/static/automatic.js`
- `jobhunter_app/static/index.html`
- `jobhunter_app/validation.py`
- `jobhunter_app/workflow.py`
- `qa/automatic_browser.py`
- `qa/scraper_live.py`
- `requirements-scanners.lock`
- `requirements-scanners.txt`
- `requirements.txt`
- `run_all.py`
- `run_scan.py`
- `scanners/base.py`
- `scanners/bridge.py`
- `scanners/compat.py`
- `scanners/jobspy_scanner.py`
- `scanners/workday.py`
- `site/index.html`
- `tests/test_automatic.py`
- `tests/test_phase3_sources.py`
- `tests/test_scraper_restoration.py`
- `utils/dedup.py`

No personal profiles, CVs, collected jobs, databases, logs, tokens or private recovery archives are committed. `requirements.txt` retains the full optional legacy dependency route; the pinned scanner runtime avoids requiring cloud packages just to collect jobs. `run_all.py` lazily imports evaluation so scan-only works with scanner dependencies.

## 7. Run the repaired project

In an existing Codespace, preserve local changes first:

```sh
git pull --ff-only
python -m pip install -r requirements-scanners.lock
bash .devcontainer/start.sh --restart
```

Open **Ports →8765 →Open in Browser**, visibility **Private**. No profile/source input is required for the preconfigured searches/feeds. The code and dependencies both need updating; a browser refresh alone does not update Python. Pages is a static launcher, not the Python backend.

Original full scanner:

```sh
python run_scan.py
python run_all.py --scan-only
```

Bounded opt-in live verification, with private output only:

```sh
python qa/scraper_live.py --source arbeitnow:de --source remoteok:remote --output /PRIVATE/verification
python qa/scraper_live.py --jobspy-site indeed --location Egypt --output /PRIVATE/regional
```

Do not run the full Compose scanner and bounded dashboard scheduler simultaneously against the same workspace: they are alternative scheduling modes, and legacy JobSpy calls do not share the dashboard provider quota ledger. Concurrent file/SQLite writes are protected, but that does not establish shared provider-request accounting. The Compose service restores collection every six hours with no exposed backend port; the full optional cloud-evaluation chain requires separate dependency/key configuration and is not silently activated.

## Remaining limits — not hidden

Bayt/Google/Wuzzuf remain inaccessible through the tested routes; Naukrigulf needs the optional dedicated ordinary-browser setup. Missing authorized social/USAJOBS configuration is not guessed. No proxy rotation, stealth or access-challenge bypass was added. The registry covers the requested countries, but every combination of 98 queries × 4 sites was **not** exhaustively executed; regional live samples plus pagination fixtures are not proof of full coverage. Some source fields are absent, and descriptions/dates can be stale. Cross-platform fuzzy matching is not a safe dedup identity, so syndicated jobs with different canonical URLs may still need review. Historical conflicts are archived and require review before linking. Codespaces remote startup, Windows and Docker daemon execution were not verified here; local Python collection, browser transport samples and synthetic UI were verified. No billable infrastructure or automatic application submission was initiated.
