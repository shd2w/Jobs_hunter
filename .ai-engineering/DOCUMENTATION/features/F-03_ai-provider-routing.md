# F-03 - Multi-provider AI routing and key rotation

## Purpose and scope
Route AI calls across Google AI Studio and OpenRouter and rotate keys when one is rate-limited.

## Users and triggers
Internal: used by the evaluator, CV tailor and cover-letter writer; configured through `.env` keys (up to 4 OpenRouter and 2 Google).

## Normal workflow
A caller asks the router for a completion; the router picks the primary provider for the task, falls back through the configured chain and rotates keys when one hits a limit (README AI Routing Strategy).

## Alternate and failure workflows
When every key and provider is exhausted the call fails. The required end state is an explicit failure with no score (DEC-034); actual behaviour is not verified here.

## Requirements and acceptance criteria
Up to four OpenRouter and two Google keys supported; key rotation never removed (docs/PROMPT.md). MUST-KEEP.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Reads credentials from `.env`; sends prompts to external providers over the network.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `agents/smart_router.py`
- `agents/google_client.py`
- `agents/openrouter_client.py`

Work packages that mention these files: none found by name mention. Decisions: DEC-034. Gates: G16.

## Security and privacy
Keys are S4: never logged, printed, committed or put in evidence (GOV-03 section 4). Prompts may contain S3 data.

## Tests and evidence
- none linked

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- No dedicated tests exist for routing or key rotation (docs/PROMPT.md section 2 says 'add tests, never remove keys support'). UI tests fake the router.
- Provider limits and the terms for multi-key rotation are unverified (PCD-010, PCD-028).

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
