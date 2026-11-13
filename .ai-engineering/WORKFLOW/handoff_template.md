# Handoff Record

## Identification
- **Task:** <task-id and title>
- **Work package:** <WP-id>
- **Date/time:** <ISO 8601>
- **Agent:** <CLI name and model label, no secrets>
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

### Remaining scope
1. <step>: <what needs to happen>

## Validation state
### Baseline (pre-change)
- **Command:** <exact command>
- **Result:** <pass/fail/skip counts>
- **Evidence:** <path to evidence file>

### Latest post-change
- **Command:** <exact command>
- **Result:** <pass/fail/skip counts>
- **Evidence:** <path to evidence file>

### Gate status
| Gate | Status | Evidence |
|---|---|---|
| <gate> | passed/failed/skipped/unavailable/not-applicable | <evidence path or reason> |

## Last verified checkpoint
- **What was verified:** <description>
- **What was NOT verified:** <description>
- **Verification evidence:** <path>

## Blockers and open items
- <blocker or "none">

## Unresolved questions
- <question or "none">

## Pending decisions
- <PCD-id: effect on this task, or "none">

## Required approvals
- <approval needed, or "none">

## Failed approaches
1. **Approach:** <what was tried>
   **Result:** <what happened>
   **Why it failed:** <analysis>
   **Evidence:** <path>

## Documentation status
### Updated
- <file>: <what was updated>

### Still pending
- <file>: <what is still pending, or "none">

## Exact next actions
1. <specific action with exact command>
   **Expected outcome:** <what should happen>

## Recovery instructions
<how to recover safely if the working tree is dirty or an operation was interrupted, or "tree clean, nothing interrupted">
