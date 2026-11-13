# F-08 - UniversalAutoApplier queue export

## Purpose and scope
Write `data/application_queue.jsonl` with only eligible jobs, deterministically and atomically, with identity hashes that match UniversalAutoApplier.

## Users and triggers
`python run_export_queue.py`, the end of `run_all.py`, or the Export application queue button.

## Normal workflow
Load evaluations, keep jobs that pass the eligibility rules, compute `application_id`, write the JSONL to a temp file and swap it in atomically (README, Application Queue Export).

## Alternate and failure workflows
Each excluded job is counted with a structured skip reason (evaluation_failed, missing_url, invalid_url, below_threshold, missing_documents and others, see README). A failed export keeps the previous queue and fails the pipeline.

## Requirements and acceptance criteria
Identical input gives byte-identical output; `application_id` = sha256(platform:external_id) or sha256(canonical URL) matching UAA identity rules; never fabricate candidate facts. MUST-KEEP; CLI flags unchanged.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads `data/evaluations.json`, `config/profile.yml`, referenced PDFs; writes `data/application_queue.jsonl`.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `utils/queue_exporter.py`
- `run_export_queue.py`

Work packages that mention these files: WP-02-03, WP-03-03. Decisions: DEC-035, DEC-046. Gates: G6.

## Security and privacy
The queue carries S3 profile snapshot fields and document paths; it stays local. Only truthful candidate facts are exported (tests/test_candidate_profile_truthful.py).

## Tests and evidence
- `tests/test_queue_exporter.py`
- `tests/test_identity_golden_contract.py`
- `tests/test_export_queue_wq2.py`
- `tests/test_uaa_contract.py`
- `tests/test_candidate_profile_truthful.py`
- `tests/test_evaluation_store.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- The suite keeps the hand-off to the separate auto-applier under PCD-007 (interim default: keep the explicit export, never submit).
- Byte-identical golden file check (G6) is built by WP-01-03; existing tests are the interim guard.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
