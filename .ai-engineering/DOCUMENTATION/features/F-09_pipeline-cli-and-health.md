# F-09 - Pipeline CLI orchestration, health and source check

## Purpose and scope
Run the full scan -> evaluate -> generate cycle, check system health, and try each enabled extra source once.

## Users and triggers
The owner from the command line, or the buttons of the Find & score tab.

## Normal workflow
`run_all.py` runs scan, evaluate and queue export in order; `run_health.py` reports environment and config status; `run_check_sources.py` queries each enabled extra source once and reports (README).

## Alternate and failure workflows
A failed queue export fails the pipeline instead of shipping a stale queue (README).

## Requirements and acceptance criteria
Original CLI flags unchanged (docs/PROMPT.md section 2, G14). MUST-KEEP for run_all.py and run_health.py.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads configuration and `data/`; the source check makes live network calls.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `run_all.py`
- `run_health.py`
- `run_check_sources.py`
- `utils/utf8_logging.py`

Work packages that mention these files: WP-00-04, WP-02-03. Decisions: none linked. Gates: G14, G20.

## Security and privacy
Logs must not contain secrets or personal data (G12); UTF-8 safe logging avoids encoding crashes on Windows.

## Tests and evidence
- `tests/test_run_all_export_integration.py`
- `tests/test_utf8_logging.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- run_health.py and run_check_sources.py have no tests; run_check_sources.py needs the owner's network and its output feeds the live-verification record (G20).
- tests/test_run_all_export_integration.py could not be collected in the review container (httpx missing, KI-001).

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
