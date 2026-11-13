# Handoff and Resume Protocol

**Version:** 1.0  
**Authority:** Defines the complete protocol for saving state before a model/session switch and resuming in a new session.

---

## 1. When to create a handoff

A handoff record **must** be created when:

| Trigger | Action |
|---|---|
| Model or CLI switch | Full handoff before stopping |
| Quota or rate limit reached | Full handoff before stopping |
| Provider outage | Full handoff at earliest safe point |
| Context limit reached | Full handoff before stopping |
| Owner requests switch | Full handoff before stopping |
| Task blocked | Full handoff with blocker details |
| Task suspended | Full handoff with suspension reason |
| Session ending with incomplete work | Full handoff |

---

## 2. Handoff record location and naming

```
.ai-engineering/MEMORY/handoffs/<task-id>/<YYYYMMDD-HHmmss>_<agent-label>.md
```

Example: `MEMORY/handoffs/WP-00-01/20261110-101500_gemini-cli-pro.md`

---

## 3. Handoff template

```markdown
# Handoff Record

## Identification
- **Task:** <task-id and title>
- **Work package:** <WP-id>
- **Date/time:** <ISO 8601>
- **Agent:** <CLI name and model label — no secrets>
- **Trigger:** <why this handoff is being created>

## Repository state
- **Branch:** <current branch name>
- **Base branch:** <branch this was created from>
- **HEAD commit:** <full SHA>
- **Git status summary:**
  ```
  <output of git status --short>
  ```

## File changes
### Committed
- <path>: <what changed and why>

### Uncommitted (staged)
- <path>: <what changed and why>

### Uncommitted (unstaged)
- <path>: <what changed and why>

### Untracked
- <path>: <what it is>

## Implementation progress
### Completed steps
1. <step>: <evidence reference>
2. ...

### Remaining scope
1. <step>: <what needs to happen>
2. ...

## Validation state
### Baseline (pre-change)
- **Command:** <exact command>
- **Result:** <pass/fail counts>
- **Evidence:** <path to evidence file>

### Latest post-change
- **Command:** <exact command>
- **Result:** <pass/fail counts>
- **Evidence:** <path to evidence file>

### Gate status
| Gate | Status | Evidence |
|---|---|---|
| <gate> | passed/failed/skipped/unavailable/n-a | <evidence path> |

## Last verified checkpoint
- **What was verified:** <description>
- **What was NOT verified:** <description>
- **Verification evidence:** <path>

## Blockers and open items
- [ ] <blocker or open item with detail>

## Unresolved questions
- <question that needs an answer>

## Pending decisions
- <PCD-id>: <how it affects this task>

## Required approvals
- <what needs owner approval>

## Failed approaches
1. **Approach:** <what was tried>
   **Result:** <what happened>
   **Why it failed:** <analysis>
   **Evidence:** <path>

## Documentation status
### Updated
- <file>: <what was updated>

### Still pending
- <file>: <what still needs updating>

## Exact next actions
1. <specific action with exact command if applicable>
   **Expected outcome:** <what should happen>
2. ...

## Recovery instructions
<If the working tree is dirty or an operation was interrupted, explain how to recover safely.>
```

---

## 4. Resume checklist

A resuming agent must complete ALL of these steps before continuing implementation:

### 4.1 Read
- [ ] Read `CORE/engineering_constitution.md`
- [ ] Read `AGENTS/UNIVERSAL_AGENT.md` and role contract
- [ ] Read `CONFIG/project_profile.yml`
- [ ] Read `CONFIG/project_contract_map.yml`
- [ ] Read `MEMORY/PROJECT_STATE.yml`
- [ ] Read `MEMORY/CURRENT_TASK.md`
- [ ] Read `MEMORY/KNOWN_ISSUES.md`
- [ ] Read `MEMORY/RECENT_FAILURES.md`
- [ ] Read the latest handoff record

### 4.2 Verify
- [ ] Run `git status` — compare with handoff
- [ ] Run `git log --oneline -5` — confirm HEAD matches
- [ ] Run `git branch` — confirm correct branch
- [ ] Run `git diff --stat` — compare changed files with handoff claims
- [ ] Check for unexpected user changes since handoff
- [ ] Rerun the checkpoint validation (or documented safe subset)
- [ ] Verify baseline test results are still valid

### 4.3 Reconcile
- [ ] If state matches handoff: proceed from last verified point
- [ ] If user made additional changes: record and integrate
- [ ] If handoff contradicts repository: stop and report
- [ ] If handoff is incomplete: stop and report
- [ ] Update checkpoint if actual state differs

### 4.4 Continue
- [ ] Resume from the **last verified point**, not the handoff's claimed next step
- [ ] Inherit the same acceptance criteria, quality gates, and security requirements
- [ ] Do not skip any gate a previous agent was required to pass
- [ ] Record that a resume occurred in the task state

---

## 5. Handoff quality requirements

A valid handoff must:
- be parseable and complete (no placeholder sections);
- reference real files, commits, and evidence that exist in the repository;
- accurately describe the repository state (verified by `git` commands);
- not contain credentials, secrets, personal data, or S3/S4 classified content;
- include actionable next steps, not vague descriptions.

An invalid handoff requires reconciliation before any implementation continues.

