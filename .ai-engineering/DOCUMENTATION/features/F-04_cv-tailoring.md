# F-04 - CV tailoring (JSON patch)

## Purpose and scope
Adapt the base CV to a job by applying AI-proposed structured edits (subtitle, objective keywords, skills order, bullet rephrasing, project selection) with code, never touching dates, education, languages or contact data.

## Users and triggers
The owner, per job, by an explicit action in the app (Create tailored CV) or `run_evaluate.py --url ... --create-cv` style flags.

## Normal workflow
`cv.md` (base) -> AI proposes a JSON patch -> code applies it -> tailored markdown -> PDF (F-05). The base `cv.md` is never modified (README).

## Alternate and failure workflows
If the AI patch is invalid or the provider fails, no tailored CV is produced. The exact error handling was not verified here.

## Requirements and acceptance criteria
Dates, education, languages, header and company names are never changed by the AI. Creation only by explicit per-job user action (DEC-019, G5). MUST-KEEP and must remain functional.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads `cv.md` and the job description; writes tailored markdown and PDF paths under `output/` and records paths in `data/evaluations.json`.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `agents/cv_tailor.py`

Work packages that mention these files: WP-09-01. Decisions: DEC-019. Gates: G5.

## Security and privacy
CV content is S3, contact data S4; contact data must not go to the AI. AI output is untrusted until applied as a bounded patch.

## Tests and evidence
- `tests/test_ui_integration.py`
- `tests/test_ui_service.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- Only covered through the app's integration test with a faked AI call; no direct unit tests of the patch logic were found.
- Current code still has an opt-in automatic path (`create_cv` / `evaluation.auto_cv_threshold`) in run_evaluate.py; DEC-019 requires no automatic creation and WP-01-01 removes it. README still describes automatic tailoring above the threshold.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
