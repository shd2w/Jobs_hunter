# F-02 - AI scoring and evaluation

## Purpose and scope
Score each posting 1-5 on five weighted dimensions (30/20/20/20/10) against the candidate CV, apply the German-language policy, and persist the evaluation.

## Users and triggers
The owner via `python run_evaluate.py --next | --batch N | --all | --url`, `run_all.py`, or the Find & score tab.

## Normal workflow
`run_evaluate.py` takes pending jobs, fetches the job description (cache first), asks the evaluator for a JSON score, clamps and applies the German policy and threshold, then appends the result to `data/evaluations.json` through `utils/evaluation_store.py` (README Pipeline Step 3; tests/test_evaluation_store.py).

## Alternate and failure workflows
AI errors and provider limits are handled by the router's key rotation (F-03). Four German policies exist: reject_b1_plus, reject_b2_plus_only, reject_unless_bilingual, accept_all (README German Filter Policies). Target behaviour for an exhausted AI call is `failed` with no score (DEC-034, G16); whether current code does this is not verified here.

## Requirements and acceptance criteria
Five dimensions weighted 30/20/20/20/10; original CLI flags unchanged; AI never invents experience, dates, employers, skills or language levels (docs/PROMPT.md section 3). MUST-KEEP.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads `cv.md`, `config/profile.yml`, the job description; writes `data/evaluations.json`. Sends the CV text and job description to the configured AI provider (S3 data leaves the machine; consent model is defined by the suite for later phases).

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `run_evaluate.py`
- `agents/evaluator.py`
- `utils/evaluation_store.py`
- `utils/json_extract.py`
- `utils/jd_fetcher.py`

Work packages that mention these files: WP-01-01, WP-01-02, WP-02-03. Decisions: DEC-034. Gates: G1, G16.

## Security and privacy
The CV and profile are S3/S4 personal data. Profile contact data must not be sent to AI providers (GOV-03 section 2). Job text is untrusted prompt input.

## Tests and evidence
- `tests/test_german_policy.py`
- `tests/test_evaluation_store.py`
- `tests/test_jd_fetcher.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- tests/test_german_policy.py replicates the policy logic instead of importing it (KI-005), so it does not guard run_evaluate.py.
- agents/evaluator.py hard-codes the candidate's language levels (docs/PROMPT.md section 4; scheduled for change in WP-01-02, PCD-006).
- README names reject_b1_plus as the German default but run_evaluate.py falls back to accept_all if the profile has no key (KI-006, to verify).

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
