# All JobSpy platforms and optional Scrapling worker

Follow-up to the scraper restoration. Verified against installed `python-jobspy==1.4.1` and `scrapling==0.5`. The JobSpy runtime's actual `Site` enum includes all eight requested platforms plus Google Jobs. No original provider, query, feed, import path or private data was removed.

## Implementation

- `scanners/jobspy_registry.py` declares all nine exact identifiers, including `zip_recruiter` (not `ziprecruiter`).
- Original 98 English/German × regional configurations and their original four providers are untouched. `jobspy_providers` adds 112 provider-specific query configurations: Glassdoor 56, ZipRecruiter/Naukri/BDJobs/HelloWork 14 each. Total: 210 configurations, not 210 confirmed successful network queries.
- All nine providers are registered with the existing `Collection` adapter, provider cooldowns, source health and default automatic scheduler. Existing user approvals, pause state, checkpoints and provider gates survive the revision-1 → revision-2 insert-only seed upgrade.
- Each automatic unit runs one provider/query/page and rotates through its configured scope, with default maximum two pages, existing five-minute local cooldowns, and failure backoff. Google retains the daily gate. This conservative scheduler does not start all providers simultaneously or silently reset access failures.
- The original JobSpy multi-site manual call retains JobSpy's concurrent provider behavior. `qa/jobspy_platforms_live.py` tests all nine with at most three independent provider subprocesses concurrently and a 150-second wall deadline per provider. It is not an automatic retry mechanism and does not touch production data.
- `run_scan.py --site` and `qa/scraper_live.py --jobspy-site` accept every provider. Their provider-aware default scopes prevent a bare BDJobs/Naukri/HelloWork invocation from accidentally using Germany. A single-site CLI override does not also execute the supplementary registry.
- Provider-declared remote flags are retained in location text alongside the original location. Missing salary/currency/date values are not invented. A source's remote flag is never evidence of worldwide eligibility.

## Provider-specific geography

| Provider | Added default scope | Constraint |
|---|---|---|
| Glassdoor | Germany, Austria, Switzerland, Remote | Country support is restricted; the remote fallback is US-scoped, not worldwide |
| ZipRecruiter | USA, remote only | US/Canada focus; not an Egypt/Oman/UAE local adapter |
| Naukri | India, remote only | India focus; this is **not** Naukrigulf |
| BDJobs | Bangladesh, work-from-home only | Local eligibility can still apply; JobSpy supplies the Bangladesh country internally |
| HelloWork | France, full remote only | France focus; no worldwide eligibility assumption |

All original country and title filters still apply at intake. Provider-native results can be rejected as irrelevant, and an empty accepted inbox is not automatically a scraping failure. Existing English/German terms remain; a term in German does not prove the returned listing's language.

## Actual live verification

One live `Software Engineer` query per provider, maximum three results requested; at most three providers active concurrently. The evidence is aggregate-only in [JOBSPY_ALL_PLATFORMS_VERIFICATION.json](JOBSPY_ALL_PLATFORMS_VERIFICATION.json). It records extraction/normalization, not production insertion, exhaustive coverage or hiring eligibility.

| Provider | Query scope | Outcome |
|---|---|---|
| LinkedIn | Germany | 3 received, 3 valid |
| Indeed | Germany | 3 received, 3 valid |
| Google Jobs | Germany | Provider returned no job data; failure, not a successful empty scan |
| Bayt | Oman | HTTP 403; no bypass attempted |
| Glassdoor | Germany | HTTP 403; no bypass attempted |
| ZipRecruiter | USA remote | HTTP 403; no bypass attempted |
| Naukri | India remote | 3 received, 3 valid |
| BDJobs | Bangladesh work-from-home | 3 received, 3 valid |
| HelloWork | France full remote | 3 received, 3 valid |

All 15 valid rows had nonempty title, company, location, description, source URL and publication date. Employment type was present on 14; one Naukri row declared salary. Other missing salary values remain blank. Source field presence is not independent confirmation of employer truth.

The five added adapters were also tested through the production `sources.scan` intake with injected results/checkpoints; these wiring tests are not presented as additional live collection. No additional live Scrapling vacancies are claimed.

## Scrapling integration

**Superseded in part:** Scrapling now also has a default first-class HTTP/crawl engine. See [primary engine implementation](SCRAPLING_PRIMARY_ENGINE.md). The optional Wuzzuf/Naukrigulf parser described below remains available; it is no longer the only Scrapling integration.

Scrapling is a library, not by itself an autonomous AI agent. It is implemented here as a reusable **optional extraction worker** on existing authorized Wuzzuf/Naukrigulf HTML paths, not another LLM, a replacement JobSpy scanner or a Notion custom agent.

```sh
python -m pip install -r requirements-scrapling.txt
export JOBHUNTER_AUTHORIZED_BOARD_PARSER=scrapling
bash .devcontainer/start.sh --restart
```

PowerShell: `$env:JOBHUNTER_AUTHORIZED_BOARD_PARSER='scrapling'`; restart the Python process using the existing local launcher. Revert with `JOBHUNTER_AUTHORIZED_BOARD_PARSER=stdlib`. Default remains `stdlib`, so core deployments do not acquire a new required dependency.

The worker uses Scrapling `Selector` with `adaptive=False` on HTML already fetched through the existing bounded, validated transport. It extracts publisher JSON-LD and listing/pagination links, then reuses existing structured-job normalization, safe URLs, source approval, checkpoints, cancellation, deduplication and intake. It does not execute remote instructions, create another scraper registry, use fetcher/browser extras, rotate proxies, solve challenges, collect account credentials or automatically switch transports. Existing explicit ordinary-browser support remains separate. The selected parser is visible in the source catalog.

Fixture tests exercise actual Scrapling parsing, equality with stdlib fields (including salary/type/date), unsafe next-page rejection, challenge handling and explicit missing-runtime errors. This does not establish live layout compatibility on currently blocked pages, and no claim is made that enabling the parser will make a 403 source accessible.

## Verification and usage

```sh
# After preserving local edits:
git pull --ff-only
python -m pip install -r requirements-scanners.lock
bash .devcontainer/start.sh --restart

# Single provider, native configured scope:
python run_scan.py --site naukri --term 'Software Engineer' --limit 3 --data-dir /PRIVATE/test-data

# Opt-in bounded live verification; expect a nonzero exit for blocked sources:
python qa/jobspy_platforms_live.py --output /PRIVATE/provider-verification

# Offline regression suite:
python -m pytest -q
```

The independent live verifier has no shared production provider ledger: do not run it alongside production scheduling or use repeated runs as a cooldown workaround. It performs one sample/provider and never retries through a different route. Re-running a sample does not prove complete pagination.

Full local regression suite: **1721 tests passed** in 63.42s (0:01:03). Integrated synthetic smoke: **47 HTTP operations passed**, with unchanged source CV hash and no external requests. Optional Scrapling contracts are also included as a dedicated CI step; base runtime remains able to test without Scrapling. Dependency validation (`pip check`) passed locally. Docker, Windows execution and remote Codespaces startup were not newly verified in this follow-up. Existing restoration limitations and historical conflicts remain documented in [SCRAPER_RESTORATION.md](SCRAPER_RESTORATION.md).

## Modified files in this follow-up

- `.github/workflows/tests.yml`
- `README.md`
- `config/portals.yml`
- `docs/JOBSPY_ALL_PLATFORMS.md`
- `docs/JOBSPY_ALL_PLATFORMS_VERIFICATION.json`
- `jobhunter_app/authorized_boards.py`
- `jobhunter_app/automatic.py`
- `jobhunter_app/expanded_sources.py`
- `jobhunter_app/scrapling_parser.py`
- `jobhunter_app/sources.py`
- `qa/jobspy_platforms_live.py`
- `qa/scraper_live.py`
- `requirements-scrapling.txt`
- `run_scan.py`
- `scanners/jobspy_registry.py`
- `scanners/jobspy_scanner.py`
- `tests/test_all_jobspy_platforms.py`
- `tests/test_scraper_restoration.py`
