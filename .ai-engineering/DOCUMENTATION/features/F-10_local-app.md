# F-10 - Local JobHunter app (ranked jobs, per-job actions)

## Purpose and scope
Provide a local web app for ranked jobs, per-job creation of documents by click, running the original scripts, and setup.

## Users and triggers
The owner, via `python run_app.py` (opens http://127.0.0.1:8765).

## Normal workflow
Jobs tab: ranked evaluations (best score first, ties by skills match then newest) with re-weighting of the five dimensions; per job: Create tailored CV, Use my CV as is, Write cover letter, Create both, download, open posting, Telegram, status tracking. Find & score tab: buttons running the original scripts with live output. Setup tab: paste CV, details, threshold and AI keys (README easy mode).

## Alternate and failure workflows
Missing PDF support is shown in Setup. The server rejects foreign Host/Origin headers and cross-site POSTs (server.py docstring). Error and empty states of the pages were not inspected in this draft.

## Requirements and acceptance criteria
Ranking required (docs/PROMPT.md section 3). Documents only by explicit per-job action. Binds 127.0.0.1 only, no accounts. Original CLI keeps working.

## UI states
Three tabs: Jobs, Find & score, Setup (README). Loading, empty, partial and error states of each tab were not inspected in this draft; viewport sizes are undefined (GAP-4). Screenshot evidence: none.

## Data contracts and side effects
HTTP API under `/api/` (jobs, pending, run, setup, setup/cv, setup/keys, setup/profile). Reads and writes `data/`, `output/`, `cv.md` (backup `cv.md.bak` on edit) and `.env` keys (write-only).

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `run_app.py`
- `jobhunter_ui/__init__.py`
- `jobhunter_ui/server.py`
- `jobhunter_ui/service.py`
- `jobhunter_ui/runner.py`
- `jobhunter_ui/ranking.py`
- `jobhunter_ui/static/index.html`
- `jobhunter_ui/static/app.js`
- `jobhunter_ui/static/style.css`
- `jobhunter_ui/static/cv.example.md`

Work packages that mention these files: WP-02-04. Decisions: DEC-019. Gates: G5, G15.

## Security and privacy
Local-only server; per-session CSRF is a suite requirement (GOV-03 section 3), not verified here. All dynamic text uses textContent (app.js). Keys are never shown again after saving.

## Tests and evidence
- `tests/test_ui_ranking.py`
- `tests/test_ui_server.py`
- `tests/test_ui_service.py`
- `tests/test_ui_integration.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- No browser-level or responsive tests exist; viewports and UI workflows are not defined (contract map GAP-4). UI tests use real HTTP round-trips with fake AI and PDF.
- The suite plans a shared service layer so CLI and UI use one code path (WP-02-04, G15); today the service wraps the original modules.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
