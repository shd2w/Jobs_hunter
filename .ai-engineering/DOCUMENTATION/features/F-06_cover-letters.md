# F-06 - Cover letter generation

## Purpose and scope
Write a targeted cover letter for one job with the AI router and render it to PDF.

## Users and triggers
The owner, per job, via Write cover letter in the app.

## Normal workflow
Job description + CV facts -> AI router -> cover letter text -> PDF (README AI Routing Strategy: OpenRouter multi-key rotation).

## Alternate and failure workflows
Provider exhaustion or an AI error results in no letter; exact handling not verified here.

## Requirements and acceptance criteria
Must remain functional (docs/PROMPT.md section 2). The AI never invents experience or levels.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads `cv.md` and job data; writes a letter file and PDF under `output/`.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `agents/cover_letter.py`

Work packages that mention these files: none found by name mention. Decisions: DEC-019. Gates: G5.

## Security and privacy
Letter content is S3. Contact data must not go to the AI.

## Tests and evidence
- `tests/test_ui_integration.py`
- `tests/test_ui_service.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- Covered only through the app integration test with a faked AI call.
- Same automatic-path caveat as F-04 until WP-01-01 is merged.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
