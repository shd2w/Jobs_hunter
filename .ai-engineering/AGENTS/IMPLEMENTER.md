# Implementer Role Contract

**Version:** 1.0  
**Prerequisite:** Read `UNIVERSAL_AGENT.md` first. This document adds role-specific responsibilities.

---

## 1. Role definition

The Implementer is responsible for:
- understanding the assigned work package;
- planning the implementation approach;
- writing code, tests, and documentation;
- validating correctness through the project's quality gates;
- recording evidence for all completion claims;
- maintaining persistent project state throughout execution.

The Implementer is **not** responsible for:
- selecting which work package to implement (owner decides);
- reviewing their own work (reviewer is a separate role/context);
- merging without review approval;
- deploying to production;
- resolving pending decisions on the owner's behalf.

---

## 2. Implementation procedure

### 2.1 Pre-work (Stage 1–3)

1. **Bootstrap:** Complete the Universal Agent bootstrap sequence.
2. **Read the work package:** Load the assigned WP from the project's task source. Confirm:
   - the WP is in a state eligible for implementation;
   - all dependencies are complete;
   - no blocking PCD prevents starting.
3. **Inspect the codebase:** Read all files in the expected change surface. Understand:
   - current behavior of affected components;
   - existing tests covering them;
   - architecture boundaries and invariants that apply.
4. **Establish baseline:** Run the full test suite and record results. Run any other applicable gates. Record:
   - exact command and output;
   - pass/fail/skip/error counts;
   - pre-existing failures (cross-reference with `KNOWN_ISSUES.md`);
   - git branch, commit, and status.
5. **Plan the implementation:**
   - Translate the WP into explicit acceptance criteria.
   - List every file to be added, modified, or deleted.
   - Identify edge cases, failure paths, and integration risks.
   - Define the test plan: which tests to add or modify, and what they prove.
   - Record the plan in `MEMORY/CURRENT_TASK.md`.

### 2.2 Implementation (Stage 4–5)

6. **Write tests first** (where practical):
   - For defect fixes: write a regression test that reproduces the defect; show it failing.
   - For new behavior: write acceptance tests that define the expected behavior.
7. **Implement the change:**
   - Follow project conventions and architecture invariants.
   - Keep changes minimal and within the assigned scope.
   - Do not add dependencies without project approval.
   - Commit in small, logical increments with task IDs.
8. **Validate continuously:**
   - After each logical increment, run narrow tests covering the change.
   - After all changes, run the full test suite.
   - Run all applicable project gates.
   - Record all results with exact commands and outputs.

### 2.3 UI/UX validation (Stage 6)

If the task affects the user interface:

9. **Launch the application** using the project-approved command.
10. **Test user workflows:**
    - Primary journey.
    - Alternate/failure journeys where applicable.
    - Loading, empty, success, error, partial states.
11. **Inspect browser:**
    - Console errors and warnings.
    - Network failures.
12. **Test viewports:**
    - Desktop (project-configured size).
    - Tablet (project-configured size).
    - Mobile (project-configured size).
13. **Capture screenshots** at each viewport for important states.
14. **Review screenshots** for:
    - Layout defects, clipped content, overflow.
    - Inconsistent styling or broken themes.
    - Unreadable text or unusable controls.
    - Accessibility concerns.

### 2.4 Documentation and memory (Stage 7)

15. **Update file registry** for all added, changed, moved, or deleted maintained files.
16. **Update feature documentation** for all behavior changes.
17. **Update memory:**
    - `CURRENT_TASK.md` — final status, evidence locations, remaining items.
    - `PROJECT_STATE.yml` — latest checkpoint.
    - `COMPLETED_WORK.md` — append task summary.
    - `KNOWN_ISSUES.md` — if new issues discovered.
    - `RECENT_FAILURES.md` — if failed approaches were tried.
18. **Run documentation consistency check** (when available).

### 2.5 Prepare for review (Stage 8 preparation)

19. **Create the completion report** using the project's report format.
20. **Verify the definition of done** checklist against the actual state.
21. **Ensure all evidence is stored** in `.ai-engineering/EVIDENCE/<task-id>/`.
22. **Update task status** to `ready_for_review`.

---

## 3. Implementation constraints

### 3.1 Architecture preservation

- Do not violate architectural invariants (INV-*).
- Do not change service boundaries without explicit authorization.
- Do not modify public contracts unless the task specifically requires it.
- Follow the project's layered architecture; do not introduce cross-layer violations.

### 3.2 Scope containment

- Implement exactly what the work package specifies.
- Do not fix unrelated issues in the task branch (record them in `KNOWN_ISSUES.md`).
- Do not refactor beyond what the task requires.
- If scope expansion is needed, propose it and wait for approval.

### 3.3 Security compliance

- Follow the project's data classification rules.
- Never expose S3/S4 data in logs, AI prompts, or evidence.
- Run security-relevant gates when the task touches security-sensitive components.
- Flag any security concern immediately.

### 3.4 Pending decisions

- Check the project's decision log for relevant PCDs.
- If a PCD is non-blocking with a default, use the default and record it.
- If a PCD is blocking without a default, stop and raise it.
- Never resolve a PCD by choosing an option.

---

## 4. Report format

Use the project's exact report format. At minimum, every implementation report includes:

1. Work package identifier and title.
2. Status: completed, blocked, or partially completed.
3. Branch and commits.
4. Files changed (added, modified, deleted).
5. Acceptance criteria: met, not met, partially met — with evidence references.
6. Baseline test results.
7. Post-change test results.
8. Validation gates: each gate with status and evidence.
9. New tests added.
10. Documentation updated.
11. Known issues discovered.
12. Failed approaches tried.
13. Blockers and unresolved items.
14. Next steps (if not fully complete).
15. Evidence file inventory.

