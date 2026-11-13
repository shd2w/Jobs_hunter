# 06 — Execution Plan

Status: **binding procedure**. Repository-specific details (branch names, base branch, CI provider) are marked **[configurable]** because the source fixes only the rules, not the names (PCD-001, ASM-003).

## 1. Implementation sequence

Dependencies in GOV-04 are binding; this is the recommended order. Release contents are in GOV-04 §1.

| Step | Work | Notes |
| ---- | ---- | ----- |
| 1 | Phase 00 foundations | WP-00-01 first; WP-00-04 needs the owner's machine and network and runs in parallel |
| 2 | Phase 01 stabilise | packages are independent of each other and may run in parallel after WP-00-03; WP-01-07 must precede WP-05-03 |
| 3 | Phase 02 service layer and scheduler | WP-02-01 → WP-02-02 → (WP-02-03, WP-02-04, WP-02-05) |
| 4 | Phase 03 data and migration | strictly sequential WP-03-01 → 02 → 03 → 04; run verification on a **copy** of the owner's real workspace |
| 5 | Phase 04 source infrastructure | WP-04-01 → WP-04-02 → (WP-04-03, WP-04-04) → WP-04-05 |
| 6 | Phase 05 ingestion core | WP-05-01 and WP-05-02 in parallel; then WP-05-03; WP-05-04 and WP-05-05 after it; WP-05-06 after WP-05-05 |
| 7 | Phase 06 dedup stage 2 and lifecycle | WP-06-01 → WP-06-02 |
| 8 | WP-08-01, WP-08-02 (enrichment lite) | completes **R1** |
| 9 | Phase 07 profile, then rest of phase 08, then phase 09, then phase 10 | R2; WP-08-04 needs WP-07-02 and WP-06-02 |
| 10 | Phases 11 and 12 | R3; WP-11-01 has a hard date (2027-02-10); pilots run only after the baseline exists |
| 11 | Phases 13–16 | R4; each phase needs its PCDs answered first |

Stop-and-ask checkpoint after phases 01 and 05: the owner reviews the report, answers pending decisions that now matter, and says "go" for the next phase (the working contract's rule of one stage per session).

## 2. Branch strategy [configurable]

| Branch | Purpose | Rule |
| ------ | ------- | ---- |
| base branch | the owner's current line (`feature/extra-sources` lineage until PCD-001 is answered) | never committed to directly |
| `phase/NN-<slug>` | integration branch of one phase | created from the base; receives only reviewed work-package branches; merged to the base at the phase exit |
| `wp/WP-pp-nn-<slug>` | one work package | created from the phase branch; small commits, each followed by the full test suite; one reviewer |
| `pilot/<slug>` | experiments and pilots (GOV-07) | never merged into a phase branch; converted by a new work package |
| `docs/<slug>` | documentation-only changes | must not change code or tests |

Commit messages start with the work-package id. Tags `phase-NN-merged` mark phase exits and serve as rollback points.

## 3. Agent operating rules

Before writing code, an implementation agent must:

1. Read GOV-00 (charter), GOV-01 (invariants), GOV-02 (decisions and pending decisions), GOV-03 (security), the assigned package in GOV-04, and GOV-05 §1–§2.
2. Run `git status` and the full test suite read-only; record the baseline (counts, skips).
3. List every file it expects to touch and the MUST-KEEP files among them.
4. Check each DEC in the package's row and each PCD it references; note which interim defaults will apply.
5. Confirm all dependencies are `merged`; otherwise set the package `blocked` and stop.
6. Create the `wp/` branch from the phase branch.

While working it must implement **only** the assigned scope, keep commits small, run the suite after each commit, write tests first for defect fixes, label mocked and simulated results, and never resolve a PCD or widen the scope. If the package cannot be completed as specified it stops, records the finding as a proposed PCD and sets the package to `blocked`.

After working it must run every required gate, attach evidence, list skipped gates with reasons, and produce the report in §7. It reports status exactly: a package is `ready_for_review` only if GOV-05 §10 allows it.

If it does not know something (a provider's current limit or error code, a site's markup, a library API), it says so, reads the official documentation or the code, or asks; it never writes a plausible-looking answer.

## 4. Implementation prompt template

```text
You are implementing ONE work package of the JobHunter project.

READ FIRST (in order): 00_project_charter.md, 01_architecture_contract.md,
02_decision_log_and_scope.md, 03_security_and_credentials.md, 04_work_packages.md
(your package only), 05_validation_matrix.md (sections 1, 2 and your gates).

ASSIGNMENT
  Work package : <WP-pp-nn> — <name>
  Phase branch : <phase/NN-slug>      Work branch: <wp/WP-pp-nn-slug>
  Scope        : <copy the Scope cell>
  Non-scope    : <copy the Non-scope cell>
  Depends on   : <ids> (all must be merged)
  Controlling decisions : <DEC ids>   Pending decisions referenced: <PCD ids and the interim default for each>
  Required tests and evidence : <copy the Tests / evidence cell>
  Gates        : <G ids>              Exit criteria: <copy the Exit cell>

RULES
  1. Implement only the scope. Anything else: stop and report.
  2. Do not resolve a pending decision. Use the stated interim default only where the
     package says so, and record that you did.
  3. Do not add dependencies, change invariants, weaken a gate, or touch MUST-KEEP files
     beyond scope (no file may shrink by more than 20 percent without asking).
  4. Existing tests must pass unchanged. Label mocked, simulated and designer-written
     results as such. Never report an unavailable or skipped gate as passed.
  5. No real credentials, contact data or personal data in code, tests, fixtures or logs.
  6. If you do not know something, say so and check the docs or code; do not guess.

FINISH WITH the report in 06_execution_plan.md section 7, filled in exactly.
```

## 5. Reviewer prompt template

```text
You are reviewing ONE work package of the JobHunter project. You did not implement it.
Your job is to find reasons it should NOT be merged. Do not validate by default.

READ: 00, 01, 02, 03 and the package row in 04; 05 sections 2, 3 and 9; the implementer's report.

CHECK, with evidence for each (pass, fail or n/a):
  - Scope: anything implemented outside Scope, or required but missing?
  - Architecture: which invariants (INV-nn) could this change affect, and do they still hold?
  - Decisions: DEC rules followed? Any PCD silently resolved? Defaults recorded?
  - Correctness: does the code do what the exit criteria require? Edge cases and failure paths?
  - Security and privacy: data classes, payloads, logs, new dependencies, secrets, untrusted input.
  - Tests: do they fail on the old behaviour? Do they test behaviour, or only existence?
  - Evidence: reproducible? Dated real runs where the package claims real behaviour?
  - Fakes: any hard-coded success, swallowed exception, stub reported as working, mocked result
    presented as verified?
  - Skipped or unavailable gates counted as passed?
  - Atomicity: one reviewable change; unrelated behaviour changes (CLI flags, exit codes, exports,
    UI wording, file formats)?
  - Hidden assumptions or new open questions that should be proposed PCDs?

OUTPUT: verdict (merge / changes required / blocked), findings ordered by severity with file and line,
list of gates you re-ran yourself, and any proposed PCD.
```

## 6. Merge and release procedure

1. **Package merge:** report complete → reviewer verdict "merge" with no open finding → implementer rebases on the phase branch → default gate re-run on the rebased branch → merge into the phase branch (no squash that hides the commit history of the package) → status `merged` → evidence filed in the repository's evidence folder **[configurable]**.
2. **Phase exit:** all packages `merged`; phase gates green on the phase branch; no blocking PCD open for the phase; phase report (§7 phase variant: list of packages, gates, skipped gates, PCD usage); owner says "go"; phase branch merged to the base; tag `phase-NN-merged`.
3. **Release to a user (local):** the release scope's gates G6, G7, G13 and, for every source claimed as working, G20; install from the lock on a clean Windows environment; run the owner-machine live check; migration run on a copy first; backup verified.
4. **Hosted deployment (staged):** not defined here; it requires PCD-005, PCD-012, PCD-013, PCD-022 and PCD-026 first (GOV-03 §12).
5. **Post-merge verification:** re-run the full suite on the base branch; confirm queue golden unchanged; confirm no new skips; record the date and machine for any live check.
6. **Rollback:** revert to the previous phase tag; authority flags back to `file` for migrated entities (INV-21); restore from the pre-migration backup if data changed.

## 7. Exact report format

```text
WP:                 <WP-pp-nn> — <name>
Status:             <blocked | ready_for_validation | ready_for_review | ...>   (exact, per GOV-05 section 10)
Branch / base:      <wp branch> from <phase branch>
Commit(s):          <hash list>
Baseline:           <tests passed / skipped before>   After: <tests passed / skipped after>
Files changed:      <git diff --stat>; MUST-KEEP files with before/after line counts;
                    files DELETED or SHRUNK by more than 20 percent: <list or none>
Scope implemented:  <bullets mapped to the Scope cell>
Scope NOT implemented / deviations: <bullets, with reason>
Validation:         <gate> | <command> | <result> | <evidence link>     (one row per required gate)
Mocked / simulated / designer-written results: <list, labelled>
Live (real) runs:   <date, machine, network, provider, result> or none
Skipped or unavailable gates: <gate and reason> or none
DEC impact:         <decisions relied on; any decision that appears wrong>
PCD impact:         <PCDs encountered; interim defaults USED; proposed new PCDs>
Dependencies added: none | <name, version, approval DEC/PCD>
Security / privacy notes: <data classes touched; confirmation that no personal data or secret was added>
Blockers:           <list or none>
Notes:              <anything the reviewer must know>
```
A phase report adds: packages and statuses, gates per package, skipped gates, PCD defaults in force, and the exit-condition check.

## 8. Handling pending decisions during execution

An agent that meets a PCD: (a) reads its mode in GOV-02 §3; (b) if non-blocking, uses the interim default **and writes it in the report**; (c) if blocking for the guarded behaviour, leaves that behaviour out and says so; (d) never edits GOV-02; (e) proposes a new PCD if it finds a question the log does not cover. The owner answers in GOV-02 §9 form; affected packages are re-checked by the reviewer.

## 9. Live verification procedure (gate G20)

Run on the owner's machine: record date and time, operating system, Python version, network (home, office, VPN), the exact command, the provider, the queries, counts returned, per-error class counts, fields populated (for aggregators: which link fields), and any block (HTTP 401/403/429). Never include credentials or personal data. Store the record in the verification file created by WP-00-04. A source with no record is **unverified**; fixtures-only results are labelled **mocked**.

## 10. Phase milestones

| Phase | Goal | Exit condition |
| ----- | ---- | -------------- |
| 00 Foundations and guardrails | Reproducible installs, policy and secret gates, CI, baseline live probe | all 4 work packages merged; gates G1 G3 G7 G9 G12 G20 green with evidence; no open blocking PCD for the phase; phase report filed |
| 01 Stabilise existing behaviour | Known defects closed; no automatic documents; AI failures explicit | all 7 work packages merged; gates G1 G5 G6 G9 G14 G16 G17 green with evidence; no open blocking PCD for the phase; phase report filed |
| 02 Shared service layer and scheduler | One code path for CLI and UI; single scheduler with lease | all 5 work packages merged; gates G1 G4 G14 G15 G17 green with evidence; no open blocking PCD for the phase; phase report filed |
| 03 Canonical data and migration | Database authoritative with verified, reversible migration and byte-identical exports | all 4 work packages merged; gates G1 G6 G13 green with evidence; no open blocking PCD for the phase; phase report filed |
| 04 Source infrastructure | Honest source states, budgets, guards and run metrics | all 5 work packages merged; gates G1 G8 G10 G15 G17 green with evidence; no open blocking PCD for the phase; phase report filed |
| 05 Ingestion core | Canonical jobs from ATS, aggregators, imports; company catalog funnel | all 6 work packages merged; gates G1 G8 G11 G12 G17 G20 green with evidence; no open blocking PCD for the phase; phase report filed |
| 06 Dedup stage 2 and lifecycle | Cross-source links and safe closing of jobs | all 2 work packages merged; gates G1 G10 green with evidence; no open blocking PCD for the phase; phase report filed |
| 07 Candidate profile and onboarding | Confirmed-profile model with proficiency provenance and eligibility data | all 4 work packages merged; gates G1 G5 G12 G13 G15 green with evidence; no open blocking PCD for the phase; phase report filed |
| 08 Enrichment, matching and evaluation | Explainable deterministic matching, eligibility verdict, AI failure semantics | all 6 work packages merged; gates G1 G9 G12 G15 G16 green with evidence; no open blocking PCD for the phase; phase report filed |
| 09 User-initiated documents | Per-job draft, review, approval, export with versioning | all 2 work packages merged; gates G1 G5 G12 G15 green with evidence; no open blocking PCD for the phase; phase report filed |
| 10 Tracking, notifications, feedback | Application events, queue export from database, Telegram rules, feedback loop | all 5 work packages merged; gates G1 G6 G12 green with evidence; no open blocking PCD for the phase; phase report filed |
| 11 Extended sources and pilots | More sources through the controlled expansion process; pilots with kill criteria | all 9 work packages merged; gates G8 G9 G17 G20 green with evidence; no open blocking PCD for the phase; phase report filed |
| 12 Monitoring and operations | Drift detection, backups, deletion, Windows packaging | all 4 work packages merged; gates G7 G9 G10 G12 G13 G17 G20 green with evidence; no open blocking PCD for the phase; phase report filed |
| 13 Accounts and tenancy | Hosted multi-user mode with proven isolation | all 3 work packages merged; gates G12 G13 G18 G21 green with evidence; no open blocking PCD for the phase; phase report filed |
| 14 Hosted operations | Shared ingestion plane and per-user plane running as a service | all 3 work packages merged; gates G13 G17 G18 green with evidence; no open blocking PCD for the phase; phase report filed |
| 15 Privacy, compliance, redistribution | Consent, export, deletion, per-source redistribution gating | all 2 work packages merged; gates G12 G18 G19 G21 green with evidence; no open blocking PCD for the phase; phase report filed |
| 16 Capacity and cost controls | Scope-driven ingestion limits, per-user budgets, load evidence | all 2 work packages merged; gates G1 G9 G16 green with evidence; no open blocking PCD for the phase; phase report filed |
