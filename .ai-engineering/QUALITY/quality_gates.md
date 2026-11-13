# Quality gates: runner reference

Runner: `python .ai-engineering/SCRIPTS/validation/run_gates.py <subcommand>` (standard library only; project commands come from `CONFIG/command_profiles.yml`).

| Subcommand | Purpose | Records gate |
|---|---|---|
| `baseline --task T` | tests plus git state before any change, `EVIDENCE/T/baseline/`; never closes a gate | G1 (baseline), BASELINE-GIT |
| `run <command-id> --task T` | run one project command; unavailable / owner-machine commands are recorded `unavailable` and exit 1 | GOV-05 id (G1, G3, G12...) via alias table, else the command id |
| `mustkeep --base REV --task T` | before/after line counts of MUST-KEEP files; deletion or shrink over the limit is a stop-and-ask | G2 |
| `protected --base REV --task T` | owner-controlled paths (docs/governance, docs/PROMPT.md, CORE) unchanged; no override flag | PROTECTED |
| `docs-gate --task T` | registry check plus memory state check | DOCS |
| `validate-review FILE [--task T]` | review report structure, severities, verdict, independence; with `--task` writes the gate (only a clean `approved` passes) | REVIEW |
| `record-ui ...` | screenshot evidence, see `WORKFLOW/browser_ux_workflow.md` | UI-<viewport> |
| `validate-evidence PATH...` | every record against `QUALITY/evidence_schema.yml` | n/a |
| `summary --task T` | latest status per gate with freshness | n/a |
| `close-check --task T [--require G1,...] [--base REV]` | every required gate has a latest closing record that is `passed` (or justified `not-applicable`) and not stale. Also understands the pseudo-gates below. With `--base`, a change touching a `ui-*` component adds `UI` automatically | n/a |
| `regressions --task T` | compares the baseline G1 failures with the post-change G1 failures and prints `pre-existing`, `introduced` and `fixed` test ids. Fails on any introduced failure, on a failure it cannot classify, or when no baseline exists | REGRESSIONS |
| `approvals --base REV --task T` | detects high-risk operations in the change (new dependency, history rewrite, mass deletion or deletion of runtime data/backups, credential-like files, release tag) and requires `MEMORY/approvals/T/<operation>.md` for each, naming the owner message that approved it | APPROVALS |

Companion command in `check_memory.py`: `start --task T` refuses to start a work package unless its status is `ready_for_implementation` or `in_progress`, all its dependencies are `merged`, and every pending decision (PCD) that references it is handled as its mode requires: a *non-blocking* PCD needs a `PCD impact: PCD-nnn ...` line in `CURRENT_TASK.md`, a *blocking* one needs `PCD out of scope: PCD-nnn ...`.

Pseudo-gates accepted by `close-check --require`:

| Id | Passes when |
|---|---|
| `REG` | a baseline-area record for gate `REG` has status `failed`, a later closing record with the same command is `passed` and fresh (a defect's regression test must be shown failing before the fix; a test that never failed proves nothing) |
| `UI` | `project_profile.yml ui.viewports` is `active` (owner-defined) and every configured viewport has a `passed`, fresh `UI-<WxH>` screenshot record. While viewports are `pending_owner`, UI validation is unavailable and never passes |
| `REGRESSIONS` | a fresh `regressions` record passed. When `G1` is itself `failed`, `G1` is accepted only if every failing id is pre-existing **and** recorded in `MEMORY/KNOWN_ISSUES.md` |

Rules enforced mechanically: unavailable, skipped, failed, mocked, simulated or fixture evidence never counts as passed; a record whose `status` is `passed` but whose `exit_code` is not 0 is rejected; a `live-verification` record must carry `network` and `provider_or_service` and must not mention mock, fake, stub, fixture, simulated, offline, dry-run, canned or demo sources, nor carry a Fixture, Simulation, Designer-written, Prototype or Demo project label; records store the commit, whether the tree was dirty, and a fingerprint of all maintained source files, so evidence goes stale when code or config changes (framework files do not); baseline records never close a gate; secrets in command output are redacted before storing.

Default `close-check` requirement: `default_gate_sequence` from `command_profiles.yml` (G1, G3, G12, G2) plus DOCS and REVIEW. Task-specific gates (G4, G6, UI-*...) are added with `--require`. Exit codes: 0 ok, 1 gate failed or findings, 2 usage/environment error.

Not covered by the runner: whether an approval record or an evidence record was really written by the owner or really produced by the stated command (a forged record is caught only by the independent review), operations that leave no trace in Git (production deploys, data sent to an external service), judging whether a test is meaningful, whether a review was genuinely independent beyond the stated checks, or whether a screenshot shows what the agent says it shows.
