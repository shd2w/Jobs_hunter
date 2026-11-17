# Current Task

**Task:** WP-03-01
**Status:** ready_for_merge
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

## Plan (Stage 3, recorded 2026-11-17)
- Baseline captured with hash-locked venv (jobhunter_venv, Python 3.12, core+dev locks):
  G1 325 passed / 3 xfailed; G3 2 passed; G12 PASS; G2 PASSED. First G1 attempt (system Python 3.10,
  no deps) failed at collection — environmental (KI-001/KI-012 family), recorded in baseline evidence.
- Schema source: docs/04_DATA_AND_INTEGRATION_DESIGN.md s4 (base DDL), s10 (R1 additions,
  authoritative), s11 (R2-3 additions, authoritative where they differ).
- New files: jobhunter/adapters/store.py (MigrationRunner, MIGRATIONS, atomic backup via sqlite3
  backup API + os.replace), jobhunter/app/services/store.py (StoreService returning Result[T]),
  tests/test_store_migrations.py (empty + legacy fixtures, idempotence, backup created, user_id on
  per-user tables per DEC-036, failure rollback).
- Migration 0001 = R1 schema in one additive migration; version tracking via PRAGMA user_version;
  per-user tables get user_id TEXT NOT NULL; profile_* children keep version_id keys per s10 DDL
  (tenancy via future profile_version FK).

## Files changed
- jobhunter/adapters/store.py (new, 374 lines): Migration dataclass, MIGRATIONS (migration 0001 =
  R1 schema per docs/04 s4+s10+s11), connect/schema_version/pending_migrations/apply_migrations,
  backup_database (sqlite3 backup API + os.replace, atomic), PER_USER_TABLES/GLOBAL_TABLES
- jobhunter/app/services/store.py (new, 51 lines): StoreService.apply_migrations / schema_version
  returning Result[T]; Err codes store_migration_failed / store_backup_failed / store_open_failed /
  store_version_failed
- tests/test_store_migrations.py (new, 242 lines): 12 tests
- .ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml: 4 entries added (3 files + owner decision record)
- .ai-engineering/MEMORY/: CURRENT_TASK.md, PROJECT_STATE.yml, KNOWN_ISSUES.md (KI-018),
  decisions/phase02_approval_wp0301_start_2026-11-17.md
- .ai-engineering/EVIDENCE/WP-03-01/: baseline and validation records
- MUST-KEEP files: unchanged (G2 before/after line counts identical)

## Progress log (timestamped)
- 2026-11-17 Bootstrap complete (marker verified, CORE x4, role, config, memory; check_memory.py state OK)
- 2026-11-17 Owner approvals received: Phase 02 accepted; WP-03-01 start authorized; G13=unavailable for
  WP-03-01; merge target confirmed; state-file update authorized as first step
- 2026-11-17 CURRENT_TASK.md / PROJECT_STATE.yml updated (stale head_commit 853c7a9 -> a1812f0 reconciled);
  commit 2cd53f1 on wp/WP-03-01-schema-v1-migration-runner
- 2026-11-17 Baseline attempt 1 (system Python 3.10, no deps): G1 collection error (ModuleNotFoundError:
  pandas) — environmental, evidence kept; hash-locked venv created (jobhunter_venv, Python 3.12,
  core+dev locks, pip check clean)
- 2026-11-17 Baseline: G1 325 passed / 3 xfailed; G3 2 passed; G12 PASS; G2 PASSED
- 2026-11-17 Implementation: adapters/store.py + services/store.py + 12 tests; first narrow run found
  missing raw_job table (new hypothesis from failure output); fixed; narrow run 16 passed
- 2026-11-17 Post-change G1: 337 passed / 3 xfailed (325 baseline + 12 new; all existing tests unchanged)
- 2026-11-17 Post-change G2 PASSED; G3 2 passed; G12 PASS; commit 2717301
- 2026-11-17 Registry: 4 entries added (pre-existing Phase 02 gap recorded as KI-018, 19 errors remain)
- 2026-11-17 Completion report filed (EVIDENCE/WP-03-01/report/); status ready_for_review
- 2026-11-17 Owner review performed (verdict: merge; review record
  EVIDENCE/WP-03-01/review/REVIEW_WP-03-01_owner_20261117.md); status ready_for_merge

## Blockers and open questions
- G13 recorded `unavailable` for WP-03-01 per owner instruction (command unavailable_until:WP-03-04);
  fixture-test evidence attached as package proof. Never counted as passed.
- check_registry.py check still FAILs (33 findings) due to pre-existing Phase 02 registry gaps (KI-018)
- Independent review (Stage 8) pending — next step after this report

## Next actions
- Independent review of WP-03-01 (reviewer role, separate context); then merge to phase/00-foundations
