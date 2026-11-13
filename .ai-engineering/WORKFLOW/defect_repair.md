# Defect repair protocol (spec 11.3, operational)

Authority: constitution and spec 11.3. This file only maps each step to a command.

| Step | Do | Record |
|---|---|---|
| 1 Preserve | Re-run the failing command through the runner: `run_gates.py run <command-id> --task WP-pp-nn --area validation` | the evidence record keeps command, exit code, output |
| 2 Classify | pre-existing / introduced by the task / environmental / flaky / unknown. Compare with the baseline records (`--area baseline`) | classification in `CURRENT_TASK.md` Results |
| 3 Hypothesis | one written root-cause hypothesis per attempt | `CURRENT_TASK.md` Progress log |
| 4 Regression test | add or name the test that fails before the fix | failing record first, passing record after |
| 5 Repair | smallest change that addresses the hypothesis | commit |
| 6 If it fails | read the new evidence; the next attempt needs a materially different hypothesis. Never rerun unchanged | `MEMORY/RECENT_FAILURES.md` |
| 7 Blocked | information, access, dependency or owner decision missing: set the task `blocked` and say exactly what is missing | handoff, `KNOWN_ISSUES.md` |
| 8 Re-verify | rerun every affected test and the regression checks; a failed record is never deleted or overwritten, the newer record supersedes it in `close-check` | new evidence records |

`CONFIG/framework.yml` `repair.max_attempts_per_failure` (3) is advisory: reaching it forces `blocked`, never a downgraded or hidden failure. Do not edit or delete an evidence record to make a gate pass.
