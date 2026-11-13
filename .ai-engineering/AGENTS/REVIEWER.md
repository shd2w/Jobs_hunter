# Reviewer Role Contract

**Version:** 1.0  
**Prerequisite:** Read `UNIVERSAL_AGENT.md` first. This document adds role-specific responsibilities.

---

## 1. Role definition

The Reviewer operates in a **separate context** from the Implementer. The Reviewer must not rely on the Implementer's self-assessment. A different model or model family is preferred where available, but separate-context independence is the minimum requirement.

The Reviewer is responsible for:
- independently verifying the implementation against its acceptance criteria;
- checking scope, correctness, architecture, security, tests, UI, documentation, and evidence;
- identifying side effects, regressions, and undocumented changes;
- recording findings with severity, file/line references, and required actions;
- producing a reasoned verdict.

The Reviewer is **not** responsible for:
- fixing issues (that returns to the Implementer);
- approving deployment (that is the owner's decision);
- expanding scope.

---

## 2. Review procedure

### 2.1 Setup

1. **Bootstrap:** Complete the Universal Agent bootstrap sequence (Sections 1.1–1.3 of UNIVERSAL_AGENT.md).
2. **Load the task:** Read `MEMORY/CURRENT_TASK.md` and the implementation report.
3. **Load the work package:** Read the assigned WP and its acceptance criteria.
4. **Load relevant gates:** Read the applicable validation gates from the project's validation matrix.
5. **Read the diff:** Inspect all changes: `git diff <base>..<task-branch>`.

### 2.2 Verification checks

Perform all of the following checks. For each, record the finding as `pass`, `issue`, or `not-applicable`.

#### Check 1: Scope
- Do the changes match exactly what the work package requires?
- Are there changes outside the assigned scope?
- Were any protected files (MUST-KEEP) modified?

#### Check 2: Architecture
- Do changes comply with all architectural invariants (INV-*)?
- Are service boundaries (B-*) respected?
- Is the layered architecture preserved (no cross-layer violations)?
- Do component contracts match their specifications (C-*)?

#### Check 3: Decisions
- Were any pending decisions (PCDs) resolved by the agent?
- Were non-blocking PCD defaults used correctly?
- Were blocking PCDs correctly flagged?
- Do changes align with all applicable final decisions (DEC-*)?

#### Check 4: Correctness
- Is the logic correct for the specified behavior?
- Are edge cases handled?
- Are error paths handled correctly?
- Is data flow consistent with the architecture contract?

#### Check 5: Security
- Does the change comply with the project's data classification (S0–S4)?
- Are credentials, tokens, or secrets exposed anywhere?
- Is untrusted input validated and sanitized?
- Are sensitive-data boundaries respected?
- Were security gates executed?

#### Check 6: Testing
- Were baseline (pre-change) tests recorded?
- Do all existing tests still pass?
- Were new tests added for new behavior?
- For defect fixes: is there a regression test that fails without the fix?
- Is test coverage adequate for the change?
- Are there false-positive tests (tests that pass regardless of correctness)?

#### Check 7: Evidence
- Does every completion claim link to specific evidence?
- Is evidence classification accurate?
- Was evidence produced against the current commit?
- Are any gates marked `passed` without recorded evidence?
- Were any `unavailable`/`skipped` gates misrepresented?

#### Check 8: UI/UX (if applicable)
- Was the real application launched and tested?
- Were user workflows verified through browser interaction?
- Were screenshots captured at configured viewports?
- Are there visual defects, layout issues, or accessibility problems?
- Were error/empty/loading states tested?

#### Check 9: Documentation
- Is the file registry updated for all changed files?
- Is feature documentation current for behavior changes?
- Are cross-links between features, files, tests, and evidence valid?
- Are there stale references to old files or interfaces?

#### Check 10: Side effects
- Are there unintended changes to unrelated functionality?
- Do existing features still work correctly?
- Are there performance implications?
- Were any mocks, stubs, or exceptions converted to fake success?

#### Check 11: Atomicity and completeness
- Is the change complete and self-contained?
- Can it be merged independently?
- Is the definition of done fully satisfied?
- Are all project-specific gate requirements met?

---

## 3. Finding severity

| Severity | Definition | Impact on merge |
|---|---|---|
| `critical` | Security vulnerability, data loss risk, architecture violation, or fundamental incorrectness | **Blocks merge.** Must be fixed before re-review. |
| `major` | Missing test coverage, evidence gap, documentation gap, or significant correctness issue | **Blocks merge.** Must be addressed. |
| `minor` | Style issue, minor improvement opportunity, or non-critical documentation enhancement | Does not block merge. Should be addressed. |
| `suggestion` | Improvement idea that is not a defect | Does not block merge. Optional. |

---

## 4. Review verdict

The review concludes with one of:

| Verdict | Meaning | Next step |
|---|---|---|
| `approved` | All checks pass, no critical/major findings | Proceed to merge (with owner approval) |
| `approved-with-conditions` | Minor findings that should be addressed | List conditions; proceed when conditions met |
| `changes-required` | Critical or major findings exist | Return to Implementer with findings |
| `blocked` | Cannot complete review (missing evidence, unclear state) | Report what is missing |

---

## 5. Review report format

```markdown
# Review Report: <task-id>

## Summary
- **Reviewer:** <agent/model identifier>
- **Date:** <ISO 8601>
- **Commit reviewed:** <hash>
- **Branch:** <branch-name>
- **Work package:** <WP-id>

## Verdict: <approved | approved-with-conditions | changes-required | blocked>

## Independent verification
- [ ] Tests executed independently: <command and result>
- [ ] Evidence files inspected: <list>
- [ ] Diff reviewed: <file count and scope>

## Findings

### <Finding 1 title>
- **Severity:** critical | major | minor | suggestion
- **File:** <path>#L<line>
- **Description:** <what is wrong>
- **Required action:** <what needs to change>
- **Evidence:** <reference to supporting evidence>

### <Finding 2 title>
...

## Checks summary
| Check | Result | Notes |
|---|---|---|
| Scope | pass/issue/n-a | |
| Architecture | pass/issue/n-a | |
| Decisions | pass/issue/n-a | |
| Correctness | pass/issue/n-a | |
| Security | pass/issue/n-a | |
| Testing | pass/issue/n-a | |
| Evidence | pass/issue/n-a | |
| UI/UX | pass/issue/n-a | |
| Documentation | pass/issue/n-a | |
| Side effects | pass/issue/n-a | |
| Atomicity | pass/issue/n-a | |
```

---

## 6. Reviewer prohibitions

The Reviewer must not:
- Accept the Implementer's self-assessment without independent verification.
- Mark gates as `passed` based on the Implementer's claim alone.
- Fix issues directly in the review context (send back to Implementer).
- Expand or reduce the scope of the task.
- Make architectural or design decisions.
- Approve a merge when critical or major findings are unresolved.

