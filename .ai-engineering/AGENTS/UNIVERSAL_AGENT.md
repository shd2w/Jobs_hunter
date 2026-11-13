# Universal Agent Protocol

**Version:** 1.0  
**Authority:** Defines the operating contract that every agent must follow, regardless of role, CLI, or model.

---

## 1. Bootstrap sequence

Every agent session begins with this sequence. No implementation work may start until bootstrap is complete.

### 1.1 Read framework foundations

1. Read `CORE/engineering_constitution.md` — internalize all principles, prohibitions, and authority hierarchy.
2. Read `CORE/universal_standards.md` — code, testing, commit, review, documentation standards.
3. Read `CORE/evidence_and_claims.md` — evidence rules, storage, and classification.
4. Read `CORE/definition_of_done.md` — completion requirements.

### 1.2 Load project configuration

5. Read `CONFIG/project_profile.yml` — project identity, paths, commands, classifications.
6. Read `CONFIG/project_contract_map.yml` — authority order, document locations, mapping.
7. Read `CONFIG/framework.yml` — framework settings and policies.

### 1.3 Load project state

8. Read `MEMORY/PROJECT_STATE.yml` — current project status, active task, last checkpoint.
9. Read `MEMORY/CURRENT_TASK.md` — if a task is active, load its full state.
10. Read `MEMORY/KNOWN_ISSUES.md` — known defects and limitations.
11. Read `MEMORY/RECENT_FAILURES.md` — failed approaches to avoid repeating.

### 1.4 Check for handoff

12. If resuming: read the latest handoff in `MEMORY/handoffs/<task-id>/`.
13. If a handoff exists: follow the Resume Protocol (Section 3).

### 1.5 Load role contract

14. Read the role-specific document (IMPLEMENTER.md or REVIEWER.md).

### 1.6 Load assigned work

15. Read the assigned work package from the project's work-package document.
16. Read applicable validation gates from the project's validation matrix.
17. Verify the task is authorized, dependencies are complete, and no blocking decision exists.

---

## 2. Operating rules

### 2.1 Scope discipline

- Work only on the assigned task or work package.
- Do not select the next backlog item; that is the owner's decision.
- Do not expand scope without owner approval.
- If you discover something outside the assigned scope that needs fixing, record it in `KNOWN_ISSUES.md` and continue with the assigned work.

### 2.2 Decision discipline

- Follow the project's decision log as the single authority for decisions.
- Do not resolve pending decisions (PCDs) on the owner's behalf.
- If a PCD blocks the task, check whether it has a non-blocking default. Use the default if one exists, and record that you did so.
- If a PCD is marked blocking and has no default, mark the task blocked and report what decision is needed.

### 2.3 Evidence discipline

- Record evidence for every action that supports a completion claim.
- Use accurate evidence classifications (Section 4 of the Constitution).
- Store evidence in `.ai-engineering/EVIDENCE/<task-id>/`.
- Never claim a result you cannot point to in the evidence store.

### 2.4 Communication discipline

- Report status at every major checkpoint.
- Surface unknowns, blockers, and contradictions immediately.
- When you encounter a problem, explain what you know, what you don't know, and what you need.
- Do not silently skip steps or gates.

### 2.5 State discipline

- Update `MEMORY/CURRENT_TASK.md` at every significant state change.
- Update `MEMORY/PROJECT_STATE.yml` at task transitions and checkpoints.
- Create handoff records before any session end or interruption.
- Keep state records concise, structured, and verifiable.

---

## 3. Resume protocol

When resuming from a handoff:

1. **Read** the latest handoff record and all canonical project documents.
2. **Inspect** the actual repository: `git status`, `git log --oneline -5`, `git branch`, `git diff --stat`.
3. **Compare** actual state with handoff claims:
   - Is the branch correct?
   - Is the HEAD commit what the handoff says?
   - Are the claimed changed files actually changed?
   - Are there unexpected uncommitted changes?
4. **Verify** by rerunning the minimum checkpoint checks:
   - If the handoff says tests pass, run them and confirm.
   - If the handoff says a specific file was modified, inspect it.
5. **Reconcile** any discrepancies:
   - If user made additional changes, record them and integrate.
   - If handoff is contradictory or incomplete, stop and report.
6. **Update** the checkpoint if actual state differs from recorded state.
7. **Continue** from the last verified point, not from the handoff's claimed next step.

---

## 4. Standard task lifecycle

Every task follows these stages. See `WORKFLOW/task_lifecycle.md` for detailed procedures.

| Stage | Name | Key actions |
|---|---|---|
| 1 | Bootstrap and understand | Load framework, project, state, handoff, role, task |
| 2 | Inspect and establish baseline | Repository inspection, baseline tests, UI inspection |
| 3 | Plan and define proof | Acceptance criteria, change surface, test plan, edge cases |
| 4 | Test-first implementation | Regression test, acceptance tests, implement, validate |
| 5 | Continuous validation | Run tests after each increment, full suite before completion |
| 6 | Real application / UX validation | Launch app, browser testing, screenshots, responsive checks |
| 7 | Documentation and memory sync | File registry, feature docs, project state, evidence links |
| 8 | Independent review | Separate-context review of all aspects |
| 9 | Integrate and close | Merge, post-merge checks, final report |

---

## 5. Checkpoint creation

Create a checkpoint (update `MEMORY/CURRENT_TASK.md` and `MEMORY/PROJECT_STATE.yml`) at these triggers:

- Task status changes (e.g., planning → implementing → validating).
- Baseline capture complete.
- Plan finalized.
- Each major implementation increment complete.
- All tests pass after changes.
- Before requesting review.
- After review verdict.
- Before merge.
- On any blocker, failure, or interruption.
- Before session end.

---

## 6. Error handling

### 6.1 Test failures

1. Capture the full failure output.
2. Classify: pre-existing, introduced by task, environmental, flaky, or unknown.
3. For task-introduced failures: diagnose, hypothesize, fix, retest.
4. For pre-existing failures: record in `KNOWN_ISSUES.md`, do not hide.
5. Never retry the same approach without a new hypothesis.

### 6.2 Tool/environment failures

1. Record the exact error and context.
2. If the tool is configured in `project_profile.yml`, verify the configuration.
3. If the tool is unavailable, record the gate as `unavailable`.
4. Do not fabricate tool output.

### 6.3 Blockers

1. Record what is blocked and why.
2. List what is known, unknown, and what is needed.
3. Identify any safe work that can continue.
4. Update task state to `blocked`.
5. Report to the owner.

---

## 7. Session end protocol

Before ending any session (whether task is complete or not):

1. Commit any completed, tested work.
2. Update `MEMORY/CURRENT_TASK.md` with current state.
3. Update `MEMORY/PROJECT_STATE.yml`.
4. Create a handoff record if work is incomplete.
5. Report the session summary: what was done, what remains, what is blocked.
6. Leave the repository in a clean, recoverable state.

