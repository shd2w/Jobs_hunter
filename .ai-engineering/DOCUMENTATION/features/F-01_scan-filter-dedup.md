# F-01 - Job scanning, filtering and de-duplication

## Purpose and scope
Find postings from JobSpy providers, Workday-style APIs, public ATS boards and remote feeds, keep those matching the configured title and location filters, and skip jobs already seen.

## Users and triggers
The owner, by running `python run_scan.py`, `python run_all.py`, or the Find & score tab of the local app.

## Normal workflow
`run_scan.py` reads `config/portals.yml`, runs the enabled scanners, applies title and location filters and the dedup history, caches descriptions in `data/jd_cache.json` and writes `data/pipeline.md` (README, Pipeline Steps 1-2).

## Alternate and failure workflows
A source that fails or is blocked is logged and skipped; the project rule is to log a blocking site and move on, never to bypass it (docs/PROMPT.md section 3, DEC-033). Extra providers are off by default (README, extra sources).

## Requirements and acceptance criteria
Filters and dedup behave as in the guard tests. All sources enabled only through configuration. No stealth or bypass techniques. MUST-KEEP (docs/PROMPT.md section 2).

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads `config/portals.yml`; reads and writes files under `data/` (pipeline.md, jd_cache.json). Network calls to job sites and feeds. Job text is S0 public data but untrusted input.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `run_scan.py`
- `scanners/__init__.py`
- `scanners/base.py`
- `scanners/bridge.py`
- `scanners/jobspy_scanner.py`
- `scanners/jobspy_registry.py`
- `scanners/workday.py`
- `scanners/ats.py`
- `scanners/feeds.py`
- `scanners/net.py`
- `utils/filters.py`
- `utils/dedup.py`
- `utils/jd_cache.py`
- `config/portals.yml`

Work packages that mention these files: WP-01-07, WP-02-03, WP-04-03, WP-05-03, WP-06-01, WP-10-03. Decisions: DEC-033. Gates: G8, G17.

## Security and privacy
Job text and feed content are untrusted input. No credentials are needed for scanning. Blocked sources must not be circumvented (DEC-033, G17).

## Tests and evidence
- `tests/test_filters.py`
- `tests/test_dedup.py`
- `tests/test_bridge.py`
- `tests/test_extra_sources.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- Extra sources (ATS boards, feeds, extra JobSpy providers) are tested with mocked responses only; no live verification record exists (G20, PCD-002/PCD-028).
- Tests/test_extra_sources.py could not be collected in the review container (httpx missing, KI-001).

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
