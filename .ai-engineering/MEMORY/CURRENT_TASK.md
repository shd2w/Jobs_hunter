# Current Task

**Task:** WP-01-01 through WP-01-07 — Phase 01: Stabilise existing behaviour (R1)
**Status:** merged
**Branch / base:** wp/WP-01-phase-01-stabilise from phase/00-foundations (merged into phase/00)
**Last updated:** 2026-11-13T17:3xZ
**Agent:** OpenCode CLI / glm-5.3-flash-free (implementer)

## Scope (all 7 WPs)
- WP-01-01: Remove automatic CV path (DEC-019) — delete auto creation in run_evaluate; --create-cv valid only with --url; deprecate create_cv/auto_cv_threshold with warning
- WP-01-02: Evaluator reads the profile — build evaluator prompt from profile.yml candidate.languages; unconfirmed levels marked "unconfirmed"
- WP-01-03: Deterministic total score — compute_domain_score() recomputes from dimensions (skills 30/edu 20/loc 20/lang 20/growth 10); ignore model global_score
- WP-01-04: Atomic file writes — _atomic_write() for pipeline.md and scan-history.tsv; crash-injection tests
- WP-01-05: Source policy gate and pages cleanup — SmartRecruiters authorized flag; disabled_by_policy; removed unused pages config
- WP-01-06: AI error taxonomy — error classes (RateLimit/Auth/Network/Model), per-key cooldown, jitter, failed means no score
- WP-01-07: Pin title-filter defect — 3 xfail tests for substring matching (lead/leadership, staff/staffing, architect/architecture)

## Non-scope
DocumentService itself (WP-09-01)

## Dependencies (all must be merged)
- WP-00-03 (merged into phase/00, tagged phase-00-merged)

## Controlling decisions and PCD defaults in force
- DEC-019: No automatic documents; --create-cv valid only with --url
- DEC-042: all existing tests pass unchanged; MUST-KEEP files may not shrink > 20%
- KI-004: config/profile.yml and CV_Example.py gitignored (S4)
- PCD impact: none

## Acceptance criteria (all met)
- G1: 290 passed, 3 xfailed (288 baseline + 2 crash tests, 3 xfail pinned defects)
- G5: no-automatic-document (call-graph + DB constraint)
- WP-01-01 through WP-01-07 package-specific gates all pass

## Files changed (21 files)
- run_evaluate.py: remove auto CV, domain scoring, atomic write, --create-cv validation
- agents/evaluator.py: profile-driven language rules
- agents/smart_router.py: error taxonomy, per-key cooldown, jitter
- scanners/bridge.py: atomic writes for pipeline.md + scan-history
- scanners/ats.py: SmartRecruiters authorized flag, disabled_by_policy
- config/portals.yml: removed unused pages config
- tests/test_bridge.py: crash-injection tests
- tests/test_extra_sources.py: SmartRecruiters authorized=True
- tests/test_filters.py: 3 xfail pinned defect tests

## Progress log (timestamped)
- 2026-11-13T17:1xZ Branch created from phase/00-foundations; baseline G1: 288 passed
- 2026-11-13T17:1xZ WP-01-01: Remove automatic CV path — committed
- 2026-11-13T17:1xZ WP-01-02: Evaluator reads the profile — committed
- 2026-11-13T17:1xZ WP-01-03: Deterministic total score — committed
- 2026-11-13T17:1xZ WP-01-04: Atomic file writes — committed (290 passed)
- 2026-11-13T17:1xZ WP-01-05: Source policy gate — committed (290 passed)
- 2026-11-13T17:1xZ WP-01-06: AI error taxonomy — committed (290 passed)
- 2026-11-13T17:2xZ WP-01-07: Pin title-filter defect — committed (290 passed, 3 xfailed)
- 2026-11-13T17:2xZ All 7 WPs merged into phase/00, tagged phase-01-merged

## Blockers and open questions
- None

## Next actions
- Phase 01 complete. All 4 phase-00 WPs + 7 phase-01 WPs done.
- Phase 02 (WP-02-01 through WP-02-07) pending owner authorization.
