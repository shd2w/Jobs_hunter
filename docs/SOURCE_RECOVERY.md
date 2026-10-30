# Source recovery and honest scan outcomes

Build: `source-recovery-1`. This is an additive repair, not a claim that every
provider is accessible. Installed engines and source registrations do not prove
live access. No source, original search query, historical record or adapter was
removed. No transport fallback, proxy, login/challenge bypass, paid service,
cooldown override or public backend access was introduced.

## What the reported states actually mean

| Reported case | Finding / behavior |
| --- | --- |
| Arbeitnow / Jobicy: inserts, additional pages confirmed, waiting | Successful bounded page, not a failure. Their validated next link/cursor is committed with intake and resumed when due. Native/HTML paths share publisher gates. |
| Bayt / Glassdoor / ZipRecruiter: HTTP 403 | Real provider access denial, never a successful empty response. A denial in one environment does not prove the provider is universally unavailable. |
| Google Jobs upstream failure | Installed upstream integration unavailable. Retained and reported honestly; not replaced with fake empty results. |
| BDJobs / HelloWork / Naukri: zero inserts | Distinguish empty response, duplicates refreshed, filter rejection and invalid records using stored counts. Zero inserts alone is not failure. |
| Indeed / LinkedIn: result limit, offset recipe | Local budget and offset are not proof of additional results. Existing evidence-based receipt remains authoritative. |
| Remote OK / Remotive / WWR | Validated current API/RSS snapshot, not a resumable listing-page sequence. Say the response was processed without claiming whole-site coverage or source exhaustion. |
| Scrapling Arbeitnow not yet run | Shared publisher cooldown can defer HTML after a native request. Explain this wait; do not imply the HTML adapter failed. |
| Scrapling Jobicy: bounded details / unknown continuation | An observed detail batch is not evidence of another listing page. Existing checkpoint and gates retained. |
| Wuzzuf / Naukrigulf / social | Existing explicit access/setup requirements remain. Not verified by the feed/provider checks below. |

## Implementation ownership

- `jobhunter_app/provider_recovery.py`: shared conservative JobSpy error categories
  and capped backoff calculation. Access 401/403: 6h, 12h, then 24h. Rate-limit or
  unclassified provider failure: 1h, 2h, 4h, 8h, then 16h. Google upstream: daily.
- `jobhunter_app/sources.py`: bounded scans persist recovery category, error,
  consecutive-failure count and retry delay. Existing longer provider gates and
  available retry-after values win. Progress is not advanced on failure; approval
  is not silently revoked for a JobSpy error. Existing direct-HTTP quota/access
  pause rules remain unchanged. A successful later scan clears the current error.
- `scanners/jobspy_scanner.py`: the legacy full pass stops dispatching further
  queries to a provider that already denied/rate-limited access or failed Google
  upstream. Healthy co-providers continue. Each skipped provider is explicitly
  recorded; all-denied queries are deferred, not empty successes. This suppression
  lasts for that finite invocation, not across independent legacy CLI invocations.
- `jobhunter_app/source_outcomes.py`: one backend classification for response
  counts, reused by stored run receipts and source health / automatic API.
  Unknown historical counts remain unknown.
- `jobhunter_app/pagination.py`: optional snapshot response mode. Next-page and
  exhaustion fields remain unknown, not fabricated false/true. Snapshot completion
  only describes the current response. Malformed responses still fail validation.
- `jobhunter_app/source_health.py`: distinguishes source refresh wait, shared
  publisher wait and provider backoff. No reset or UI action bypasses gates.
- `jobhunter_app/static/automatic.js`: renders backend response classification,
  pagination receipt and wait/recovery reason; no frontend inference from zero.
- Partial provider/detail errors now keep source/run status partial even when
  valid rows were returned and the scan was not otherwise budget-limited.

No database schema migration or profile/configuration edit is required. Run
metrics are additive JSON fields; current snapshot labels apply only to receipts
from validated collectors, not arbitrary old/injected collections.

## Verification and its limits

Before edits, the guarded offline baseline passed **1,850 tests**.
`tests/test_source_recovery.py` adds failure classification, growing backoff,
retained gates/progress/approval, exact empty/duplicate/filter outcomes, snapshot
receipts, partial provider errors, shared publisher waits, legacy per-provider
failure isolation, and real CLI/loopback-HTTP scan equivalence with deterministic
source fixtures. Browser verification uses the actual dashboard with a disposable
SQLite database and deterministic records/errors, at desktop and mobile widths;
it does not demonstrate provider access.

One bounded public request per feed in the agent environment found:

- Arbeitnow: valid JSON, 300 records and an explicit next-page link.
- Jobicy: valid JSON, 100 records, `hasMore=true` and a next cursor.
- Remotive: valid JSON, 12 records.
- Remote OK: JSON list, 100 entries including feed metadata (not 100 proven jobs).
- WWR: RSS XML response; the metadata probe did not ingest/count jobs.

One query/provider, at most three returned records requested, using installed
JobSpy 1.4.1 and no new transport, found:

| Provider | Observed bounded result |
| --- | --- |
| LinkedIn | 3 listings |
| Indeed | 3 listings |
| Glassdoor (Germany) | 3 listings |
| Naukri (India remote) | 3 listings |
| BDJobs (Bangladesh remote) | 3 listings |
| HelloWork (France remote) | 3 listings |
| Bayt | HTTP 403 ProviderFailure |
| ZipRecruiter | HTTP 403 ProviderFailure |
| Google Jobs | ProviderFailure, no usable response |

These are availability samples, not verified unique relevant/open jobs, full
pagination verification, tests of every configured region, or proof of access
from the user's Codespace. No repeated probes of denied providers were made.
Persistent Bayt/ZipRecruiter denials and Google upstream availability remain
external limitations; code cannot honestly label them repaired. Glassdoor's
success here does not invalidate a genuine Codespace 403.

## Updating an existing private Codespace

Pull merged `main`, then gracefully stop the existing JobHunter server in its
own terminal (Ctrl+C) and start it again with `python run_local.py serve --port
8765`. Do not launch a second server on the occupied port. Verify
`/api/runtime` reports `source-recovery-1`. Keep the Codespaces forward private.
Existing gates remain in force and historical receipts are not rewritten to
claim newer observations. Ordinary cooldowns are intentional, not broken scans.

Release verification: **1,882 tests passed** in the final full suite with the
Python external-network guard; **32** new source-recovery tests passed separately.
Desktop (1280px) and mobile (390px) loopback browser checks passed with no page
errors or horizontal overflow. Python AST, frontend JavaScript syntax and diff
whitespace checks passed. The full suite includes original scanner restoration,
JobSpy registry, Scrapling, source gates, persistence, evaluation and interface
regressions. These deterministic tests do not override the live limitations above.
