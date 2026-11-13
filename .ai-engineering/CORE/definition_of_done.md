# Definition of Done

**Version:** 1.0  
**Authority:** Supplements the Engineering Constitution. A task is not complete until all applicable items below are satisfied.

---

## 1. Universal definition of done

Every task, regardless of type, must satisfy **all** of the following before it can be closed:

### 1.1 Scope

- [ ] All acceptance criteria from the task assignment are met.
- [ ] No scope was added or removed without owner approval.
- [ ] Changes are limited to files and modules identified in the task plan.

### 1.2 Code quality

- [ ] Code is syntactically valid and follows project conventions.
- [ ] No new warnings or errors introduced (or justified and recorded).
- [ ] No unrelated changes included.
- [ ] No new dependencies added without project approval.

### 1.3 Testing

- [ ] Baseline (pre-change) test results recorded.
- [ ] All existing tests pass after changes (or pre-existing failures documented).
- [ ] New tests added for new behavior or fixed defects.
- [ ] Regression test demonstrates the old (broken) behavior failing, for defect fixes.
- [ ] Post-change test results recorded with exact commands and outputs.

### 1.4 Validation gates

- [ ] All applicable project-defined gates executed.
- [ ] Each gate result classified: `passed`, `failed`, `skipped`, `unavailable`, `not-applicable`.
- [ ] No gate marked `passed` without recorded evidence.
- [ ] No `skipped` or `unavailable` gate misrepresented as `passed`.
- [ ] Failed gates either resolved or the task is blocked with documented reason.

### 1.5 Evidence

- [ ] All completion claims link to specific evidence files.
- [ ] Evidence classification is accurate (no mislabeling).
- [ ] Evidence is current (produced against the current commit).
- [ ] Evidence stored in `.ai-engineering/EVIDENCE/<task-id>/`.

### 1.6 Documentation

- [ ] File registry updated for all added, changed, moved, or deleted maintained files.
- [ ] Feature documentation updated for all behavior changes.
- [ ] Architecture/API documentation updated if contracts or boundaries changed.
- [ ] Cross-links between features, files, tests, and evidence are current.
- [ ] No stale references to deleted or renamed files/interfaces.

### 1.7 Memory and state

- [ ] `CURRENT_TASK.md` updated with final status.
- [ ] `PROJECT_STATE.yml` updated with latest checkpoint.
- [ ] `COMPLETED_WORK.md` appended with task summary.
- [ ] `KNOWN_ISSUES.md` updated if new issues discovered or existing issues resolved.
- [ ] `RECENT_FAILURES.md` updated if failed approaches were tried.
- [ ] Decisions referenced (not duplicated) from the project decision log.

### 1.8 Review

- [ ] Independent review completed in a separate context.
- [ ] Review report recorded with findings, severity, and verdict.
- [ ] All critical and major findings resolved.
- [ ] Review verdict is `approved` or `approved-with-conditions` (conditions met).

### 1.9 Git

- [ ] Changes committed on the correct task branch.
- [ ] Commit messages include task identifiers.
- [ ] No unrelated changes in the branch.
- [ ] Protected files not modified without approval.
- [ ] Branch is up-to-date with base branch.

### 1.10 Approval

- [ ] All required human approvals obtained for the actions performed.
- [ ] No approval gate was bypassed.

---

## 2. Additional requirements by task type

### 2.1 Defect fix

- [ ] Root cause identified and documented.
- [ ] Regression test added that demonstrates the defect.
- [ ] Regression test shown failing before the fix.
- [ ] Regression test shown passing after the fix.

### 2.2 UI-affecting change

- [ ] Real application launched and tested (not just unit tests).
- [ ] Primary user journey verified through browser interaction.
- [ ] Alternate and failure journeys tested where applicable.
- [ ] Loading, empty, success, error states verified where applicable.
- [ ] Browser console checked for errors.
- [ ] Screenshots captured at configured viewports (desktop, tablet, mobile).
- [ ] Screenshots reviewed for layout defects, clipped content, inconsistent styling.
- [ ] Keyboard/focus behavior verified where applicable.

### 2.3 Security-sensitive change

- [ ] Security scan executed.
- [ ] Data classification rules verified.
- [ ] No credentials exposed in code, logs, or evidence.
- [ ] Sensitive-data boundaries respected.
- [ ] Owner-approved if privilege escalation or new data sharing.

### 2.4 Data/migration change

- [ ] Migration is reversible or owner-approved if irreversible.
- [ ] Existing data preserved and verified.
- [ ] Schema changes documented.
- [ ] Rollback instructions provided.

### 2.5 Source adapter / external integration

- [ ] Source safety compliance verified (robots.txt, rate limits, no CAPTCHA bypass).
- [ ] Circuit breaker / error handling in place.
- [ ] Live verification dated and recorded, or marked unavailable.
- [ ] No production endpoint used without approval.

---

## 3. What is NOT sufficient

The following do **not** constitute completion, individually or combined:

- Code was written.
- The build succeeds.
- The agent believes the code is correct.
- A previous session's tests passed.
- Only unit tests pass (when integration or UI tests are applicable).
- Documentation says "will be updated later."
- The review was performed by the same agent in the same context.
- Mocked/simulated evidence is presented as live verification.
- A `skipped` gate is counted as `passed`.

