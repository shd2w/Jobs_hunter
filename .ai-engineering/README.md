# AI Engineering Framework - installation for JobHunter

Repository-resident operating rules for AI-assisted work on this project (spec: `AI_ENGINEERING_FRAMEWORK_SPEC_v0.1.md`). Chat history is not authoritative; these files are.

## Start here (any agent, any model)

0. Kiro, Gemini CLI and OpenCode enter through the repository-root `AGENTS.md` (Gemini CLI through `GEMINI.md`, which only imports it). Both are thin loaders that point to the files below and contain no policy. Per-CLI loading facts: `AGENTS/adapters/`.
1. `CORE/engineering_constitution.md` - non-negotiable rules. Then the other three `CORE/` files.
2. `CONFIG/project_profile.yml`, `CONFIG/project_contract_map.yml`, `CONFIG/framework.yml`.
3. `AGENTS/UNIVERSAL_AGENT.md`, then your role: `AGENTS/IMPLEMENTER.md` or `AGENTS/REVIEWER.md`.
4. Resuming? `AGENTS/HANDOFF_AND_RESUME.md`.
5. The JobHunter suite itself lives in `docs/governance/` (GOV-00..GOV-07) and `docs/PROMPT.md`. It is unchanged and remains the authority for decisions, scope, work packages and gates. This framework never edits it.

## Status of this installation

| Roadmap phase (spec section 17) | State |
|---|---|
| A Contract and configuration | delivered, pending owner review |
| B Memory and handoff (`MEMORY/` records, `WORKFLOW/handoff_*`, `QUALITY/checkpoint_schema.yml`, `SCRIPTS/memory/check_memory.py`) | delivered, pending owner review; real two-CLI switch test still to do |
| C Documentation registry (`DOCUMENTATION/` registries and 10 feature docs, `QUALITY/registry_schema.yml`, `SCRIPTS/documentation/check_registry.py`) | delivered, pending owner review; all 136 file entries and 10 feature docs are `generated-unreviewed` drafts (spot-checked, not reviewed) |
| D Quality gates (`SCRIPTS/validation/run_gates.py`, `QUALITY/quality_gates.md`, `WORKFLOW/defect_repair.md`, `WORKFLOW/browser_ux_workflow.md`) | delivered, pending owner review; no browser tool, viewports or lock/policy/scan commands exist yet, so those gates report `unavailable` |
| E Agent adapters (root `AGENTS.md` and `GEMINI.md`, `AGENTS/adapters/{kiro,gemini-cli,opencode}.md`, `QUALITY/adapter_conformance.md`, `SCRIPTS/adapters/check_adapters.py`) | delivered, pending owner review; loading mechanisms checked against official documentation on 2026-11-11; static checks and 46 tests pass; **no CLI was run, so live conformance (tests C1-C6) is `not_run` for all three and no adapter is proven to load** |
| F Stress test of the 15 scenarios, reusable template, installation and migration guide (`SCRIPTS/stress/test_scenarios.py`, `SCRIPTS/bootstrap/install_framework.py`, `WORKFLOW/installation_and_migration.md`) | delivered, pending owner review; the 15 scenarios ran against the real scripts and exposed 8 enforcement gaps, now closed (55 scenario tests, 10 installer tests pass); **not run by real agents, not run on Windows or macOS, template tested on Linux toy projects only** |

`MEMORY/` records exist. Mechanical checks: `SCRIPTS/memory/check_memory.py` (`state`, `handoff <file> --against-git`; see `WORKFLOW/handoff_protocol.md`) `SCRIPTS/documentation/check_registry.py` (`check [--since REV]`, `scan --write`, `refresh`, `trace`) and `SCRIPTS/adapters/check_adapters.py` (`check [--strict]`; static only, its last line always states the live CLI status); every other gate is still a manual obligation. `WORKFLOW/task_lifecycle.md` and the other `QUALITY/` documents are not written yet: record absent files as "not yet available", do not fabricate them.

## What the CONFIG files are

| File | Purpose |
|---|---|
| `framework.yml` | sequential mode, manual model switching, fail-closed statuses, approval list, installation status |
| `project_profile.yml` | paths, MUST-KEEP set, data classes, branch scheme, UI facts; `pending_owner` marks what the suite does not define |
| `project_contract_map.yml` | suite documents (with sha256), authority order, status/verdict/label mappings, PCD handling, known gaps |
| `command_profiles.yml` | every project command with status `exists`, `unavailable_until:<WP>` or `owner_machine_only` |
| `model_profiles.yml` | advisory only, empty |
| `../QUALITY/evidence_schema.yml` | required fields and labels for evidence records |

## Rules of thumb

- Work only on the work package the owner names. Do not pick the next one.
- Never resolve a PCD. Use its interim default and record it, or stop.
- An unavailable or skipped gate is never "passed".
- If the suite documents no longer match the sha256 values in the contract map, stop and have the owner confirm the change.
