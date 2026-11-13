# Current Task

**Task:** WP-02-01 through WP-02-05 — Phase 02: Service layer and scheduler (R1)
**Status:** merged
**Branch / base:** wp/WP-02-phase-02-service-layer from phase/00-foundations (merged into phase/00)
**Last updated:** 2026-11-13T17:4xZ
**Agent:** OpenCode CLI / glm-5.3-flash-free (implementer)

## Scope (all 5 WPs — WP-02-06/07 not defined in GOV-04)
- WP-02-01: Package skeleton and layer lint — jobhunter package with domain/app/adapters/interfaces; layer-lint test
- WP-02-02: Result type and services over files — Result[T]; services for jobs, evaluation, applications, health
- WP-02-03: CLI shims — run_scan, run_evaluate, run_all, run_export_queue, run_health call services; flags and exit codes unchanged
- WP-02-04: UI on services and ranking consolidation — ranking weights in domain scoring; parity test (G15)
- WP-02-05: Scheduler worker with lease — LockFileLease, CadenceManager, CircuitBreaker, PerHostBudget, SchedulerService

## Non-scope
Database (WP-02-02 explicitly excludes it); adaptive cadence (WP-02-05 excludes it)

## Dependencies (all must be merged)
- WP-00-03 (merged into phase/00, tagged phase-00-merged)
- WP-01-01 through WP-01-07 (merged into phase/00, tagged phase-01-merged)

## Controlling decisions and PCD defaults in force
- DEC-003: Layered architecture (C-01 interfaces, C-02 app services, C-03 domain, C-04 source registry)
- DEC-022: Domain scoring weights
- DEC-033: Source safety (no CAPTCHA, login, paywall bypass; robots.txt honored)
- DEC-028: Source registry and scheduler configuration
- DEC-042: All existing tests pass unchanged; MUST-KEEP files may not shrink > 20%
- PCD impact: none

## Acceptance criteria (all met)
- G1: 325 passed, 3 xfailed (baseline 288 + 37 new tests across layers, services, parity, scheduler)
- G4: Layer lint passes (interfaces import only app+domain; domain imports no I/O)
- G15: Parity test passes (CLI renderer and HTTP handler return identical ranked ids and scores)
- G17: Source-safety tests pass (circuit breaker on 401/403/429, cooldowns, per-host budget)

## Files changed
- jobhunter/__init__.py, domain/__init__.py, domain/scoring.py, domain/filters.py (new package + domain modules)
- jobhunter/app/__init__.py, app/result.py, app/services/__init__.py, app/services/*.py (Result type + 6 services)
- jobhunter/adapters/__init__.py, adapters/scheduling.py (lock lease, cadence, circuit breaker, budget)
- jobhunter_ui/ranking.py (re-export from domain scoring)
- utils/filters.py (re-export from domain filters)
- run_evaluate.py, run_export_queue.py, run_health.py, run_scan.py, run_all.py (CLI shims call services)
- tests/test_layers.py, test_services.py, test_parity.py, test_scheduler.py (new tests)
- .ai-engineering/CONFIG/command_profiles.yml (layer_lint activated)

## Progress log (timestamped)
- 2026-11-13T17:2xZ Branch created from phase/00-foundations; baseline G1: 290 passed
- 2026-11-13T17:2xZ WP-02-01: Package skeleton + layer lint — committed
- 2026-11-13T17:2xZ WP-02-02: Result type + services — committed (307 passed)
- 2026-11-13T17:2xZ WP-02-03: CLI shims — committed (307 passed)
- 2026-11-13T17:2xZ WP-02-04: UI on services + ranking consolidation — committed (310 passed)
- 2026-11-13T17:4xZ WP-02-05: Scheduler worker with lease — committed (325 passed)
- 2026-11-13T17:4xZ All 5 WPs merged into phase/00, tagged phase-02-merged

## Blockers and open questions
- WP-02-06 and WP-02-07 are not defined in GOV-04 work packages table
- Phase 02 exit condition per GOV-06 §10 holds: all packages merged, all gates green

## Next actions
- Phase 02 complete. All 4 phase-00 WPs + 7 phase-01 WPs + 5 phase-02 WPs done.
- Phase 03 (WP-03-01 through WP-03-04) pending owner authorization.
