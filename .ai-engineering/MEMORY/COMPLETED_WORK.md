# Completed Work (append-only)

| Date | Item | Commit | Evidence |
|---|---|---|---|
| 2026-11-10 | Framework Phase A: CONFIG files, evidence schema, README (pending owner review) | uncommitted | validation run in session; no evidence file (Phase D not built) |
| 2026-11-10 | Framework Phase B: memory records, handoff template, checkpoint schema, check_memory.py with tests (pending owner review) | uncommitted | `SCRIPTS/memory/test_check_memory.py` output, see EVIDENCE/FW-B |
| 2026-11-10 | Framework Phase C: file and feature registries, schema, check_registry.py with 21 tests (pending owner review; entries unreviewed) | uncommitted | EVIDENCE/FW-C |
| 2026-11-11 | Framework Phase D: gate runner with 45 tests, defect-repair and browser/UX workflows, quality-gate reference (pending owner review) | uncommitted | EVIDENCE/FW-D |
| 2026-11-11 | Framework Phase E: root `AGENTS.md` and `GEMINI.md`, three adapter documents, conformance suite definition, `check_adapters.py` with 46 tests (pending owner review; live CLI conformance NOT run) | uncommitted | EVIDENCE/FW-E |
| 2026-11-12 | Framework Phase F: 15-scenario stress suite (55 tests) that found and closed 8 enforcement gaps (`start`, `regressions`, `approvals`, REG and UI gates, live-evidence rules, stale feature docs, encoding and line-ending bugs); installer, template and migration guide (10 tests); real project baseline captured: 286 passed (pending owner review; not run by real agents or on Windows/macOS) | uncommitted | EVIDENCE/FW-F |
| 2026-11-13 | WP-00-01: Dependency lock — GTK/Pango runtime installed via MSYS2; G1 gate 286 passed on Windows; all WP-00-01 gates green | committed (merge to phase/00) | G1: 286 passed; EVIDENCE/WP-00-01/validation/ |
| 2026-11-13 | WP-00-02: Policy/secret/PII gates — blocked-dependency test (G3), secret/PII scan (G12), profile.example.yml tracked template, config/profile.yml + CV_Example.py gitignored (S4) | committed (merge to phase/00) | G3: 2 passed; G12: PASS; G1: 288 passed |
| 2026-11-13 | WP-00-03: CI with Windows and WeasyPrint — .github/workflows/ci.yml (ubuntu+windows matrix), scripts/verify_windows.ps1 (G7/PCD-011), windows_verify command activated | committed (merge to phase/00) | G1: 288 passed; G7: install+pip check+verify_windows pass; G9: dated live run |
| 2026-11-13 | WP-00-04: Baseline live source probe — docs/SOURCE_VERIFICATION.md (464 jobs, 4 feeds OK, 0 errors, dated 2026-11-13) | committed (merge to phase/00) | G20: dated live record; G9: live run cited |
| 2026-11-13 | WP-01-01: Remove automatic CV path (DEC-019) — --create-cv only with --url, deprecation warnings for create_cv/auto_cv_threshold | committed (merge to phase/00) | G1: 288 passed (unchanged) |
| 2026-11-13 | WP-01-02: Evaluator reads profile — prompt built from profile.yml candidate.languages; unconfirmed levels marked "unconfirmed" | committed (merge to phase/00) | G1: 288 passed (unchanged) |
| 2026-11-13 | WP-01-03: Deterministic total score — compute_domain_score() from dimensions (30/20/20/20/10), ignores model global_score | committed (merge to phase/00) | G1: 288 passed (unchanged) |
| 2026-11-13 | WP-01-04: Atomic file writes — _atomic_write() for pipeline.md + scan-history.tsv; crash-injection tests | committed (merge to phase/00) | G1: 290 passed (+2 crash tests) |
| 2026-11-13 | WP-01-05: Source policy gate — SmartRecruiters authorized flag, disabled_by_policy, removed unused pages config | committed (merge to phase/00) | G1: 290 passed |
| 2026-11-13 | WP-01-06: AI error taxonomy — RateLimit/Auth/Network/Model error classes, per-key cooldown, jitter, failed=no score | committed (merge to phase/00) | G1: 290 passed (unchanged) |
| 2026-11-13 | WP-01-07: Pin title-filter defect — 3 xfail tests for substring matching (lead/leadership, staff/staffing, architect/architecture) | committed (merge to phase/00) | G1: 290 passed, 3 xfailed |
| 2026-11-13 | WP-02-01: Package skeleton + layer lint — jobhunter package (domain/app/adapters/interfaces), domain scoring+filters moved, G4 layer-lint test | committed (merge to phase/00) | G1: 294 passed; G4: 4 passed |
| 2026-11-13 | WP-02-02: Result type + services — Result[T] Ok/Err, EvaluationService, JobsService, ApplicationsService, HealthService | committed (merge to phase/00) | G1: 307 passed (+18 service tests) |
| 2026-11-13 | WP-02-03: CLI shims — run_evaluate, run_export_queue, run_health call services; flags and exit codes unchanged | committed (merge to phase/00) | G1: 307 passed (unchanged) |
| 2026-11-13 | WP-02-04: UI on services + ranking consolidation — domain scoring weights, G15 parity test (CLI==HTTP ranking) | committed (merge to phase/00) | G1: 310 passed; G15: 3 passed |
| 2026-11-13 | WP-02-05: Scheduler worker with lease — LockFileLease, CadenceManager, CircuitBreaker, PerHostBudget, SchedulerService | committed (merge to phase/00) | G1: 325 passed (+18 scheduler tests) |
