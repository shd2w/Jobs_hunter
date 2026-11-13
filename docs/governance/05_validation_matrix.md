# 05 — Validation Matrix

Status: **binding**. This document defines what counts as proof. Commands are repository-dependent; where the source does not fix a command it is shown as a placeholder in angle brackets and **must be filled in from the repository** before first use (§8). Nothing here may be reported as passed unless it was executed (DEC-047).

## 1. Default gate (every work package)

1. Branch is up to date with the phase branch; working tree clean except the package scope.
2. Existing tests pass unchanged (G1); any changed test has a written reason.
3. New tests exist for the package's scope and fail before the change where the package is a defect fix.
4. MUST-KEEP files unchanged beyond scope; no file shrinks by more than 20 percent (G2).
5. Policy and secret scans pass (G3, G12).
6. The package's own gates (GOV-04 traceability table) are executed with evidence attached.
7. Report in the format of GOV-06 §7 lists skipped gates and says why; a skipped required gate means the package cannot advance (§10).

## 2. Required evidence by package type

| Package type | Required evidence |
| ------------ | ----------------- |
| Foundation | install log on each target OS; CI run links; policy test shown failing on a deliberate violation |
| Behaviour fix | a test that fails on the old behaviour and passes on the new; before and after output; no unrelated change |
| Refactor | existing tests unchanged and green; parity or golden test proving identical behaviour; line-count report for MUST-KEEP files |
| Data | migration run on empty and legacy fixtures; importer idempotence (second run is a no-op); verification report; byte-identical golden export; rollback demonstrated |
| Source infrastructure | state-transition tests; breaker test (one 429 stops requests); budget enforcement in a 24-hour simulation; honest-status tests |
| Source adapter | recorded fixtures; contract suite (G8); error-class tests; for any claim of working: a **dated live record** with machine and network (G20); otherwise labelled mocked |
| Domain logic | unit tests per rule; golden or labelled sets where accuracy is claimed (marked directional until a baseline exists); simulation tests where behaviour over time matters (G10) |
| AI | schema validation tests; quote-must-exist tests; error-class matrix; failure-state tests; payload capture proving no contact data or nationality (G12, G16) |
| UI | browser flow test of the journey; error, empty and partial states shown; untrusted text rendered as text |
| Security | upload and injection tests; isolation tests for hosted work (G18); reviewer-signed checklist (G21) |
| Pilot | report with measured numbers and sample sizes, method, date and machine; decision against the kill criterion (PCD-025) recorded; labelled directional if the sample is small |

Work packages by type:

| Package type | Meaning | Work packages |
| ------------ | ------- | ------------- |
| Foundation | Build, tooling, CI, packaging | WP-00-01, WP-00-02, WP-00-03, WP-02-05, WP-12-03, WP-12-04, WP-14-01 |
| Behaviour fix | Corrects an existing defect | WP-01-01, WP-01-02, WP-01-03, WP-01-04, WP-01-05, WP-01-07 |
| Refactor | Moves or consolidates existing behaviour without changing it | WP-02-01, WP-02-02, WP-02-03, WP-02-04 |
| Data | Schema, migration, importers, exporters | WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-10-02, WP-13-03 |
| Source infrastructure | Registry, protocol, guards, metrics | WP-04-01, WP-04-02, WP-04-03 |
| Source adapter | Adds or changes a provider adapter | WP-05-01, WP-05-02, WP-05-04, WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-05, WP-11-07, WP-14-03 |
| Domain logic | Pure rules, enrichment, scoring, lifecycle | WP-04-04, WP-05-03, WP-05-05, WP-05-06, WP-06-01, WP-06-02, WP-07-01, WP-07-02, WP-08-01, WP-08-02, WP-08-03, WP-08-04, WP-10-01, WP-10-04, WP-10-05, WP-12-01, WP-12-02, WP-16-01 |
| AI | Touches providers, prompts or generated content | WP-01-06, WP-08-05, WP-09-01 |
| UI | Screens and browser flows | WP-04-05, WP-07-04, WP-09-02 |
| Security | Privacy, isolation, consent, upload handling | WP-07-03, WP-10-03, WP-13-01, WP-13-02, WP-14-02, WP-15-01, WP-15-02 |
| Pilot | Experiment, verification or measurement with a decision outcome | WP-00-04, WP-08-06, WP-11-06, WP-11-08, WP-11-09, WP-16-02 |

## 3. Deployment-blocking gates

A release containing a package is blocked while any gate that package requires is red, skipped or only mocked where a real run is required.

| Gate | Pass condition | Required by work packages |
| ---- | -------------- | ------------------------- |
| G1 | Existing tests pass unchanged (286 today); any changed test has a written reason | WP-00-01, WP-00-03, WP-01-01, WP-01-02, WP-01-03, WP-01-04, WP-01-05, WP-01-06, WP-01-07, WP-02-01, WP-02-02, WP-02-03, WP-02-04, WP-02-05, WP-03-01, WP-03-03, WP-04-03, WP-05-03, WP-05-06, WP-06-01, WP-06-02, WP-07-01, WP-07-02, WP-08-01, WP-08-02, WP-08-03, WP-08-04, WP-08-05, WP-09-01, WP-10-01, WP-10-03, WP-10-04, WP-10-05, WP-16-01 |
| G2 | No MUST-KEEP file shrinks by more than 20 percent; deleted or shrunk files listed in the report | all packages of the relevant mode |
| G3 | Blocked-dependency policy test passes (DEC-014, DEC-015, DEC-033) | WP-00-02 |
| G4 | Layer-lint test passes: interfaces import only application services and domain models; domain imports no I/O | WP-02-01, WP-02-02, WP-02-04 |
| G5 | No-automatic-document test passes: call-graph test plus the database constraint (DEC-019) | WP-01-01, WP-07-03, WP-09-01, WP-09-02 |
| G6 | UAA queue export is byte-identical to the golden file (DEC-035, DEC-046) | WP-01-03, WP-03-03, WP-03-04, WP-10-02 |
| G7 | Installation from the generated hash-locked dependency files succeeds in a clean Windows environment using `pip install --require-hashes`, followed by successful dependency consistency verification | WP-00-01, WP-00-03, WP-12-04 |
| G8 | Adapter contract suite passes: fixtures normalise to valid Job, deterministic global_id, error classification | WP-04-01, WP-04-02, WP-04-03, WP-04-04, WP-05-01, WP-05-02, WP-05-03, WP-05-05, WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-05, WP-11-07 |
| G9 | Mocked, simulated and designer-written results are labelled as such; verified claims cite a dated real run (DEC-047) | WP-00-03, WP-00-04, WP-01-02, WP-08-01, WP-08-02, WP-08-03, WP-08-06, WP-11-08, WP-12-02, WP-16-02 |
| G10 | Simulation regression passes: real 60 percent drop re-baselines in 3 stable runs; stable zero outage never re-baselines; floored detector false alarms under 1 percent on small boards | WP-04-04, WP-06-02, WP-12-01 |
| G11 | Library contract tests pass on every upgrade of ats-scrapers and python-jobspy (DEC-041) | WP-05-01, WP-05-02 |
| G12 | Secret and PII scan finds nothing in tracked files; no secrets or personal data in logs, fixtures or notification payloads | WP-00-02, WP-05-04, WP-07-02, WP-07-03, WP-08-05, WP-09-01, WP-10-03, WP-12-03, WP-13-01, WP-15-01 |
| G13 | Migration verification passes: counts, URL sets, application_id equality, byte-identical queue, importer idempotence, rollback (DEC-046) | WP-03-01, WP-03-02, WP-03-03, WP-03-04, WP-07-01, WP-12-03, WP-13-03, WP-14-02 |
| G14 | CLI golden tests pass: flags, exit codes and --json shapes unchanged | WP-01-01, WP-02-03 |
| G15 | Parity test passes: CLI renderer and HTTP handler return identical ranked ids and scores for one fixture workspace | WP-02-04, WP-04-05, WP-07-04, WP-08-04, WP-09-02 |
| G16 | AI failure semantics pass: each error class takes its specified path; exhaustion yields failed with no score (DEC-034) | WP-01-06, WP-08-05, WP-16-01 |
| G17 | Source-safety tests pass: breaker opens on 401/403/429 and issues no further request; redirects and tracking links not followed; robots and per-domain budgets honoured (DEC-033) | WP-01-05, WP-02-05, WP-04-01, WP-04-02, WP-04-05, WP-05-01, WP-05-04, WP-05-05, WP-11-06, WP-11-07, WP-12-02, WP-14-01, WP-14-03 |
| G18 | Tenant-isolation tests pass for every per-user repository method (hosted mode only) | WP-13-02, WP-14-01, WP-14-02, WP-14-03, WP-15-01, WP-15-02 |
| G19 | Redistribution gating passes: personal_only and consumer-board data never appear in a hosted user's view (DEC-039) | WP-15-02 |
| G20 | Live verification record exists for each source claimed as working: dated, machine and network stated (DEC-047) | WP-00-04, WP-05-02, WP-11-01, WP-11-02, WP-11-03, WP-11-04, WP-11-06, WP-11-09, WP-12-04 |
| G21 | Security review checklist signed by a reviewer who did not implement the package | WP-13-01, WP-13-02, WP-15-01 |

## 4. Security proof

| Requirement | Proof |
| ----------- | ----- |
| No secrets or personal data in tracked files | secret and PII scan output (G12) |
| Contact data and nationality never in AI payloads, logs, notifications | payload-capture and log-scan tests (G12) |
| Documents only on explicit action | call-graph test plus database constraint test (G5) |
| Originals immutable | hash comparison before and after every document and extraction flow |
| Upload validation | spoofed extension, oversized file, malformed file are rejected (WP-07-03) |
| Injection resistance | adversarial job-text fixtures (instructions inside a posting) cannot change a score, state or tool call; sanitiser tests for imports and e-mails |
| Authentication, authorisation, isolation (hosted) | session and CSRF tests; enumerated per-user method isolation (G18) |
| Auditability | each privileged operation writes an audit event; tests assert presence |
| Blocked dependencies absent | G3 |

## 5. Reliability proof

| Requirement | Proof |
| ----------- | ----- |
| Idempotency | second run of an importer, scan or ingest creates no new rows (unique keys) |
| Retries | only transient classes retried; permanent and blocked never; jitter and backoff tests with the retry test mode on |
| Concurrency | second scheduler cannot take the lease; expired lease taken over |
| Failure recovery | crash during file write leaves the previous file intact; interrupted run recorded as failed and closes nothing |
| Timeouts | per-request timeout and size cap tests |
| Guard behaviour | simulation regression (G10): real 60 percent drop re-baselines; stable zero outage never does; floored detector false alarms under 1 percent on small boards |
| Transaction integrity | ingest batch is atomic; migration failure leaves the database at the prior version |
| Migration safety | G13 including byte-identical queue file and rollback |

## 6. AI proof

| Requirement | Proof |
| ----------- | ----- |
| Schema validity | invalid and truncated outputs rejected (G16) |
| Grounding | every extracted requirement quote occurs in the input text; ungrounded items dropped |
| Tool restriction | no tool or side-effect interface is passed to any model call (static test) |
| Failure behaviour | 429, 5xx, 4xx, timeout, malformed, key exhaustion each follow the specified path; exhaustion yields `failed` and no score |
| Scores independent of the model | changing model output text never changes a score (test) |
| Evaluation | labelled sets with sample sizes; numeric thresholds are **pending** (PCD-023) so reports state a baseline, not a pass |

## 7. Source-safety proof (G17)

Breaker opens on the first 401/403/429 and no further request reaches that host in the window; redirects and tracking links are not followed; robots.txt disallowed paths are not fetched; per-domain request budgets are never exceeded in a simulated run; a source without a policy flag or acknowledgement cannot be enabled; blocked adapters cannot be activated from configuration or UI.

## 8. Commands (repository-dependent)

| Purpose | Command | Status |
| ------- | ------- | ------ |
| Run all tests | `python -m pytest -q` | exists in the repository |
| Dependency consistency | `pip check` | standard tool; applies after WP-00-01 |
| Install from lock | `<install-from-lock-command>` | defined by WP-00-01 |
| Policy test | `python -m pytest tests/test_policy_blocked.py -q` | created by WP-00-02 |
| Secret and PII scan | `<scan-command>` | created by WP-00-02 |
| Layer lint | `python -m pytest tests/test_layers.py -q` | created by WP-02-01 (name to be confirmed) |
| Migration verify | `<migrate-verify-command>` | created by WP-03-04 |
| Simulation regression | `python -m pytest tests/test_guard_simulation.py -q` | created by WP-04-04 (ports `docs/feasibility/exp3_guard_sim.py`) |
| Source check (live, owner machine) | `python run_check_sources.py` | exists; output feeds G20 |
| Windows verification | `<windows-verify-command>` | created by WP-00-03 |

A placeholder in angle brackets means **unavailable until the named package is merged**; a report must say "unavailable", never "passed".

G7 evidence: a fresh-venv Windows install (KI-015: never a pre-populated venv) plus `pip check`; the Linux leg was removed by DEC-052 and the required-gate evidence rules of §1–§3 are unchanged.

## 9. Reviewer checklist

The reviewer is not the implementer (ASM-005). For each item the reviewer records pass, fail or not applicable with a reference.

1. **Scope:** only the package's scope was implemented; non-scope untouched; no unrelated files.
2. **Architecture:** every invariant in GOV-01 §3 that the package can affect still holds; layers respected.
3. **Decisions:** the DEC list was followed; no PCD was resolved; any default used is recorded.
4. **Security and privacy:** data classes respected (GOV-03 §2, §5); no new dependency outside §10 of GOV-03; no secret or personal data added.
5. **Tests:** they test behaviour, not only existence; defect fixes have a failing-before test; fixtures are labelled.
6. **Evidence:** every required item in §2 is attached and reproducible; live claims have a dated record.
7. **Skipped gates:** each skipped or unavailable gate is listed with reason; none is counted as passed.
8. **Unresolved decisions:** no hidden assumption; new questions filed as proposed PCDs.
9. **Behaviour changes:** no accidental change to CLI flags, exit codes, exports, file formats or UI wording; golden tests unchanged.
10. **Fake success:** no hard-coded success for an unavailable source, provider or model; no swallowed exception turned into an empty result.
11. **Atomicity:** one reviewable change set; commits traceable to the package.

## 10. Status rules

| Transition | Allowed only when |
| ---------- | ----------------- |
| `blocked` → `ready_for_implementation` | all dependencies `merged`; no blocking PCD applies to the whole package; scope unambiguous |
| `ready_for_implementation` → `in_progress` | an implementer is assigned and the branch exists |
| `in_progress` → `ready_for_validation` | the scope is code-complete |
| `ready_for_validation` → `ready_for_review` | every required gate executed; evidence attached; skipped gates listed |
| `ready_for_review` → `ready_for_merge` | reviewer checklist complete with no open finding; reviewer is not the implementer |
| `ready_for_merge` → `merged` | merged into the phase branch; post-merge default gate re-run green |
| any → `blocked` | contradiction found, dependency reopened, or blocking PCD raised |

A package is **never** `ready_for_review` or later when a required validation is skipped, unavailable, partially executed, run only against mocks where a real run is required, or reported without evidence. A phase is complete only when all its packages are `merged` and its exit condition in GOV-06 §10 holds.
