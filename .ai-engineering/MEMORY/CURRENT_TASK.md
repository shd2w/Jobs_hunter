# Current Task

**Task:** WP-00-04 - Baseline live source probe (informational)
**Status:** merged
**Branch / base:** wp/WP-00-04-baseline-live-source-probe from phase/00-foundations (merged into phase/00)
**Last updated:** 2026-11-13T16:2xZ
**Agent:** OpenCode CLI / glm-5.3-flash-free (implementer)

## Scope (copied from GOV-04, not reworded)
run run_check_sources on the owner's machine; record dated OK or FAIL per source and which link fields each aggregator provider populates

## Non-scope
Must not change scope or policy

## Dependencies (all must be merged)
- WP-00-01 (merged into phase/00, tagged phase-00-merged)

## Controlling decisions and PCD defaults in force
- DEC-044: live verification record (G20)
- DEC-047: verified claims cite a dated real run (G9)
- PCD-020: pending (WP-00-04 pending decision)
- PCD impact: none

## Acceptance criteria
- G20: live verification record exists for each source claimed as working: dated, machine and network stated
- G9: verified claims cite a dated real run; mocked/simulated results labelled as such
- docs/SOURCE_VERIFICATION.md written with dated table (machine + network)
- Every source marked verified, failed or unreachable

## Files expected to change
- docs/SOURCE_VERIFICATION.md (new: dated source verification table)
- .ai-engineering/MEMORY/CURRENT_TASK.md, PROJECT_STATE.yml (state sync)
- .ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml (registry entry for new doc)

## Test plan and required gates
- Baseline: python -m pytest -q → 288 passed
- G20: run_check_sources.py output recorded in docs/SOURCE_VERIFICATION.md (dated, machine, network)
- G9: live run cited (not mocked); 464 jobs, 0 errors across 4 feeds

## Progress log (timestamped)
- 2026-11-13T16:1xZ Branch wp/WP-00-04-baseline-live-source-probe created from phase/00-foundations
- 2026-11-13T16:1xZ Run `python run_check_sources.py`: 464 jobs, 0 errors; 4 feeds OK (arbeitnow 300, jobicy 50, remoteok 98, remotive 16); ATS boards empty (ats: [])
- 2026-11-13T16:1xZ Write docs/SOURCE_VERIFICATION.md with dated results and link fields per provider
- 2026-11-13T16:2xZ WP-00-04 merged into phase/00, tagged phase-00-merged. WP-00-04 status: merged.
- 2026-11-13T16:2xZ WP-00-03 merged into phase/00 (CI config, verify_windows.ps1). WP-00-03 status: merged.

## Results (baseline, after, gates)
- Baseline: python -m pytest -q → 288 passed (14.92s)
- G20: run_check_sources.py executed on owner's machine (Windows 11, Python 3.12.8, direct network); 464 jobs, 0 errors
- G9: dated live run cited (2026-11-13, Windows, no proxy); results are live evidence, not mocked

## Blockers and open questions
- PCD-020 pending decision for WP-00-04 (does not block merge)
- No other blockers

## Next actions
- WP-00-03 and WP-00-04 are merged. Phase 00 complete (all 4 WPs merged, tagged phase-00-merged).
- Phase 00 exit condition per GOV-06 §10 holds: all packages merged, all gates green.
- Awaiting owner authorization for Phase 01 (WP-01-01 through WP-01-07).
