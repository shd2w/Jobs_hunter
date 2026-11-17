# Current Task

**Task:** WP-03-01
**Status:** in_progress
**Branch / base:** wp/WP-03-01-schema-v1-migration-runner from phase/00-foundations
**Merge target (owner-confirmed 2026-11-17):** phase/00-foundations
**Last updated:** 2026-11-17
**Agent:** OpenCode CLI / glm-5.3-flash-free (implementer)

## Scope (GOV-04 line 145, verbatim)
- tables for R1 per SRC design doc 04 s4, s10, s11 with user_id from the first migration; migration runner with automatic backup

## Non-scope (verbatim)
- Hosted engine (PCD-005 blocking for the guarded behaviour)

## Dependencies
- WP-02-02 (merged into phase/00, tagged phase-02-merged). Phase 02 missing independent review
  accepted by the owner 2026-11-17 (decision record: MEMORY/decisions/phase02_approval_wp0301_start_2026-11-17.md).

## Controlling decisions and PCD defaults in force
- DEC-003: Layered architecture (C-01 interfaces, C-02 app services, C-03 domain, C-04 source registry)
- DEC-004: Database is authority per entity after cutover; flat files become derived exports; cutover per entity and reversible; files never deleted
- DEC-036: user_id present on every per-user table from the first migration
- DEC-046: Migrations additive; automatic backup precedes each; atomic writes for all file exports
- PCD impact: PCD-005 blocking for the guarded behaviour (hosted engine) — hosted engine out of scope; interim default in force: SQLite local; PostgreSQL hosted.

## Acceptance criteria
- T: migration idempotence on fixtures (empty and legacy fixtures)
- E: backup file created
- Exit criterion (verbatim): "Schema applies on empty and legacy fixtures"
- G13: recorded as `unavailable` for WP-03-01 (command unavailable_until:WP-03-04, owner instruction
  2026-11-17); fixture-test evidence attached as package proof. Never counted as passed.
- G1: existing tests pass unchanged (suite baseline captured per task)
- Default gate: G2 (must_keep_line_count), G3 (policy_test), G12 (secret_pii_scan) run with evidence

## Files changed
- (to be recorded during implementation)

## Progress log (timestamped)
- 2026-11-17 Bootstrap complete (marker verified, CORE x4, role, config, memory; check_memory.py state OK)
- 2026-11-17 Owner approvals received: Phase 02 accepted; WP-03-01 start authorized; G13=unavailable for
  WP-03-01; merge target confirmed; state-file update authorized as first step
- 2026-11-17 CURRENT_TASK.md / PROJECT_STATE.yml updated (stale head_commit 853c7a9 -> a1812f0 reconciled)

## Blockers and open questions
- G13 command does not exist until WP-03-04 (fail-closed: unavailable, never passed) — owner decision recorded
- Python 3.13/3.14 execution, Linux install parity, UI viewports: unchanged known limitations (PROJECT_STATE)

## Next actions
- Create wp/WP-03-01-schema-v1-migration-runner; capture baseline (G1/G2/G3/G12) with evidence
- Read docs/04_DATA_AND_INTEGRATION_DESIGN.md s4, s10, s11; plan schema and runner
