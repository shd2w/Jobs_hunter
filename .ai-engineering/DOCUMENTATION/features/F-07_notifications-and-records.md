# F-07 - Telegram notifications, Excel database and description cache

## Purpose and scope
Notify the owner of evaluations, keep a colour-coded Excel database of evaluated jobs and cache job descriptions.

## Users and triggers
Automatic after each evaluation in the CLI flow; Send to Telegram action in the app.

## Normal workflow
After an evaluation the bot message is sent (with PDFs for high scores) and the row is added to `data/jobs_database.xlsx`, deduplicated by URL (README Pipeline Steps 6-7, Excel Database).

## Alternate and failure workflows
Missing bot token or chat id means no notification. Excel write errors are not documented here.

## Requirements and acceptance criteria
MUST-KEEP (docs/PROMPT.md section 2). Colour bands green >= 4.0, yellow >= 3.5, orange >= 3.0, red below.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Writes `data/jobs_database.xlsx` and `data/jd_cache.json`; network call to Telegram with the bot token from `.env`.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `utils/telegram.py`
- `utils/excel_export.py`
- `utils/jd_cache.py`

Work packages that mention these files: WP-03-02, WP-05-04, WP-10-03. Decisions: none linked. Gates: G12.

## Security and privacy
Bot token and chat id are S4 credentials. Notification payloads must not contain personal data (G12).

## Tests and evidence
- `tests/test_ui_service.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- No dedicated tests for Telegram or Excel export; the UI service test fakes them.
- Telegram sends title, company, score and link only under the suite's rules for S2 (GOV-03); the current code was not checked against that.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
