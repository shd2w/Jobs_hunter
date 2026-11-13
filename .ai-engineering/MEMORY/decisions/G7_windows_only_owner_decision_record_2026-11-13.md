---
record_type: "owner_decision_record"
decision_id: "DEC-052"
task_id: "governance (G7 scope; affects WP-00-01, WP-00-03, WP-12-04)"
recorded_at: "2026-11-13T14:19:43Z"
recorded_by: "OpenCode CLI / GLM-5.3-Flash Free (implementer)"
source: "owner chat message, 2026-11-13 (OpenCode session, G7 governance change), quoted verbatim below"
status: "recorded; change set implemented uncommitted per GOV-02 section 9 - commit awaits owner authorization"
---

# Decision record — DEC-052: G7 is Windows-only (owner, 2026-11-13)

## Owner authorization (verbatim)

> The G7 impact analysis is accepted in principle.
>
> I approve the proposed permanent change to make G7 Windows-only across WP-00-01, WP-00-03, and WP-12-04, subject to the following refinements:
>
> 1. Preserve all independent Linux requirements, particularly charter S1 and WP-00-03's Linux G1/CI requirements.
> 2. Explicitly retain Linux dependency-install validation as a requirement for any Docker image intended for distribution. Track this through KI-013.
> 3. Preserve the Python 3.13/3.14 verification limitation. Do not imply that Windows G7 validates untested Python versions.
> 4. Preserve the hosted-platform and Linux-deployment reopening triggers.
> 5. Preserve historical evidence without rewriting previous validation results.
> 6. Ensure WP-00-01 cannot be declared complete merely because G7's definition changes. G1 and all remaining exit criteria must still be satisfied.
>
> Before implementation, confirm that the proposed DEC-0XX identifier is available and that all affected governance references have been accounted for.
>
> Once confirmed, implement the approved governance change as one controlled change set, following GOV-02 §9.
>
> Run all required governance, integrity, documentation, contract-map, registry, and handoff validations.
>
> Do not stage or commit anything. Do not merge. Do not amend or rewrite existing commits.
>
> Return the complete diff, validation results, updated evidence, and any deviations for independent review.
>
> This authorization covers the governance change described above only. It does not authorize WP-00-01 completion or merging.

## Recorded implementation (one controlled change set, GOV-02 §9, uncommitted)

Identifier verification before implementation: GOV-02 §2 contained exactly 51 decisions (DEC-051 last; §5 traceability likewise ended at DEC-051), so **DEC-052** was adopted. Reference accounting was re-confirmed: the text-bearing G7/Linux requirements are GOV-05 §3 (L59) and §8 (no Linux command exists), GOV-04 WP-00-01 (L81) and WP-00-03 (L83) rows, and docs/06 L34; WP-12-04's definition row has no OS wording and its traceability row is ID-only.

| File | Edit |
| ---- | ---- |
| `docs/governance/05_validation_matrix.md` | §3 G7 row reworded to the accepted Windows-only condition ("Installation from the generated hash-locked dependency files succeeds in a clean Windows environment using `pip install --require-hashes`, followed by successful dependency consistency verification"); §8 evidence note added (fresh-venv Windows install per KI-015, never a pre-populated venv, plus `pip check`; Linux leg removed by DEC-052) |
| `docs/governance/04_work_packages.md` | WP-00-01 T cell → "clean-venv install on Windows (G7 per amended GOV-05 §3; Linux leg removed by DEC-052)" and exit cell → "G7 green (Windows-only per DEC-052); lock reproducible"; WP-00-03 exit cell → "G1 green on both OS (Linux CI per scope); G7 green (Windows-only per DEC-052)" (scope "CI on Linux and Windows" and T "286 pass, 0 skipped on both OS" untouched) |
| `docs/06_QUALITY_SECURITY_AND_OPERATIONS.md` | G7 row reworded accordingly |
| `docs/governance/02_decision_log_and_scope.md` | New DEC-052 row (Final-Owner) recording rationale, risks accepted, compensating controls, re-open triggers, the Docker-image Linux-install requirement, the 3.13/3.14 limitation and the non-completion clause; §5 traceability row `DEC-052 | C-14 C-15 | WP-00-01, WP-00-03, WP-12-04 | G7`; §2 count line 51 → 52 |
| `.ai-engineering/CONFIG/project_contract_map.yml` | GOV-02/GOV-04/GOV-05 sha256 re-pinned with annotations; `final_decisions` 51 → 52 with annotation |
| `.ai-engineering/MEMORY/KNOWN_ISSUES.md` | KI-013: retained Linux dependency-install validation for any distributable Docker image; KI-016 added (accepted risk: Linux install parity unverified; re-open triggers) |
| `.ai-engineering/MEMORY/decisions/G7_windows_only_owner_decision_record_2026-11-13.md` | This record (new file) |
| `.ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml` | Hashes refreshed; entry added for this record |
| `.ai-engineering/MEMORY/PROJECT_STATE.yml`, `.ai-engineering/MEMORY/CURRENT_TASK.md`, handoff record | Status migration to match the dirty tree (no historical records rewritten) |

Unchanged by design: charter S1 (L69), GOV-01, GOV-03, GOV-06 (§6.3/§10 gate IDs), `command_profiles.yml`, `run_gates.py`, `FEATURE_REGISTRY.yml`/F-05, `docs/PROMPT.md`, README, Dockerfile, all historical/evidence records.

## Refinement accounting

1. **Independent Linux requirements preserved:** charter S1 untouched (Linux+Windows test parity, proven by G1); WP-00-03 scope "CI on Linux and Windows" and T "286 pass, 0 skipped on both OS" untouched; its exit cell now explicitly says "G1 green on both OS (Linux CI per scope)".
2. **Docker:** KI-013 now records that any Docker image intended for distribution still requires Linux dependency-install validation (fresh-venv `--require-hashes` install plus `pip check` on Linux); DEC-052 carries the same clause and the Docker-build re-open trigger.
3. **Python 3.13/3.14:** DEC-052 states the decision does not validate 3.13/3.14 (unverified on any OS); KI-016 repeats it; the limitation stays in the not_verified records.
4. **Re-open triggers preserved and recorded in DEC-052 and KI-016:** the hosted-platform decision (PCD-005), any Linux deployment need, or a Docker image build (KI-013).
5. **Historical evidence untouched:** no prior validation result, review record, gate record or historical memory statement was edited (supersede-never-delete); the amended rows carry the DEC-052 reference instead.
6. **WP-00-01 not complete by this change:** DEC-052 says so explicitly; GOV-04 WP-00-01 keeps G1 and all remaining exit criteria; GOV-05 §10 status ceiling unchanged; G1 remains failed/environmental (KI-012, PCD-011).

## Boundaries (from the authorization)

- Nothing staged, nothing committed, nothing merged; no existing commit amended or rewritten.
- No formal "G7 passed" Windows-leg record exists yet (a fresh-venv install per KI-015 plus `pip check`); it awaits a separate owner go-ahead.
- Linux compatibility is NOT verified and must not be claimed under DEC-052 (DEC-047 unchanged).
- Merge and WP-00-01 completion remain NOT authorized.

## Validations (executed after the edits)

All commands run with `C:\Python312\python.exe` from the repository root, branch `wp/WP-00-01-dependency-lock`, HEAD `160adb8`, 2026-11-13 (~14:20-14:30Z). Nothing was staged or committed at any point.

| Validation | Command | Result | Evidence |
| --- | --- | --- | --- |
| Registry refresh | `check_registry.py refresh` over the 9 changed registered files | exit 0 - hashes re-pinned; a registry entry was added for this record (hash confirmed by the refresh) | `.ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml` |
| MUST-KEEP (G2) | `run_gates.py mustkeep --base 83c423f... --task WP-00-01` | PASSED - "No MUST-KEEP file changed" | `.ai-engineering/EVIDENCE/WP-00-01/validation/G2_must_keep_line_count_20261113-162210.md` |
| PROTECTED | `run_gates.py protected --base 83c423f... --task WP-00-01` | FAILED by design - flags exactly the three owner-authorized governance edits (`docs/governance/02_decision_log_and_scope.md`, `04_work_packages.md`, `05_validation_matrix.md`); accepted exception per the owner authorization recorded here, same precedent as records 140636/145006 | `.ai-engineering/EVIDENCE/WP-00-01/validation/PROTECTED_protected_paths_20261113-162208.md` |
| Documentation gate | `run_gates.py docs-gate --task WP-00-01` | PASSED - two known WARNs (F-03 "no tests linked", pre-existing; state head_commit behind HEAD, framework-consistent); a confirming re-run over the final tree followed the memory refresh | `.ai-engineering/EVIDENCE/WP-00-01/validation/DOCS_docs_gate_20261113-162216.md` (+ final re-run record, see CURRENT_TASK) |
| Gate summary | `run_gates.py summary --task WP-00-01` | exit 0, no crash; the post-change gates (DOCS/G2/PROTECTED) are fresh; the WP-00-01 implementation-era records (APPROVALS, G1, REGRESSIONS, dependency_consistency, install_from_lock) are correctly marked "not fresh - source files changed since" (the lock itself did not change) | console table, quoted in the change report |
| Memory state | `check_memory.py state` | exit 0 - exactly one expected WARN: `head_commit 76936a8 != HEAD 160adb8` (state deliberately points at the implementation commit; no commit authorization exists to update it) | this table |
| Handoff check | `check_memory.py handoff <record> --against-git` | Executed last, after the handoff record was updated to the final tree; result recorded in the handoff record's validation notes and the CURRENT_TASK progress log | handoff record |


## Authenticity note (KI-009)

This record was written by the implementer agent from the owner's chat message. The independent reviewer must confirm it against the owner's actual message before treating DEC-052 as authentic. Per AGENTS.md, chat history is not authoritative - repository files are - which is why this record carries the owner's instruction into the repository.
