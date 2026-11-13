---
record_type: "owner_decision_record"
task_id: "WP-00-01"
recorded_at: "2026-11-13T10:16:25Z"
recorded_by: "OpenCode CLI / GLM-5.3-Flash Free (implementer)"
source: "owner chat message, 2026-11-13 (OpenCode session, WP-00-01), quoted verbatim below"
status: "recorded; lock generation still requires final owner confirmation of the complete package-to-group mapping (owner's standing condition)"
---

# Decision record — WP-00-01 (owner, 2026-11-13)

## Decisions (verbatim)

> **1. Lock tool: APPROVED — A (pip-tools).**
>
> Use `pip-compile --generate-hashes` and install using `pip install --require-hashes`.
>
> Keep pip-tools as a development-only locking tool. Do not introduce uv or Poetry or migrate the project to another package manager.

> **2. Dependency group mapping: APPROVED WITH AMENDMENTS.**
>
> - `stamina`: Defer unless you demonstrate an existing mandatory runtime dependency.
> - `RapidFuzz`: Assign to `ingestion`, unless direct core usage demonstrates otherwise.
> - `pytest`: Test/CI tooling only. Do not include it in production dependency groups. Introduce a separate test/dev group if supported by the existing governance.
>
> Present the complete package-to-group mapping for confirmation before finalizing the locks.
>
> Keep `extruct`, `crawlee`, and `dedup` deferred.

> **3. requirements.txt transition: APPROVED — OPTION 2.**
>
> The generated core lock file will be `requirements.txt`.
>
> - Its source of truth must be the corresponding `.in` input.
> - Keep Dockerfile, compose, CI, and manifest detection compatible.
> - Do not manually maintain generated lock files.
> - Avoid modifying unrelated files outside the WP outputs.

> **4. In-scope confirmation: APPROVED.**
>
> Include both:
>
> - `CONFIG/command_profiles.yml`: `install_from_lock` and `dependency_consistency`.
> - `CONFIG/project_profile.yml`: `dependency_manifest` pointing to `pyproject.toml`.
>
> Follow GOV-05 §8 and ensure the configuration reflects the actual authoritative dependency manifests.

> **5. pydantic-xml: APPROVED FOR LOCKING NOW.**
>
> Follow the proposed resolution and verification plan:
>
> - Resolve latest compatible version at lock time.
> - Verify Python 3.12–3.14 and Pydantic >=2.14.2 compatibility.
> - Run the test suite in a clean virtual environment.
> - Record the exact resolved version and hashes.
> - Document resolution and update policies.
> - Flag compatibility concerns.
>
> Keep it locked despite phase-11 feeds not yet being wired.

> **6. GTK runtime (PCD-011): DEFER OWNER INSTALLATION.**
>
> Accept that G1 is unavailable on this Windows machine without GTK.
>
> - Record G1 as unavailable, not passed.
> - Record the 283 passing diagnostic tests as supplementary evidence.
> - Document the missing GTK runtime as the blocker.
> - Keep G1 validation outstanding until it runs successfully in an appropriately configured environment.
>
> Do not install machine-level dependencies without authorization.

> **Final instruction:** Update the decision and approval records with these exact decisions. Identify any remaining blockers before proceeding. Do not silently expand WP-00-01 or claim validation that has not actually occurred.

## Recorded implications and verifications (implementer notes, 2026-11-13T10:16:25Z)

- **stamina:** full-repository search (case-insensitive) finds **zero source imports** of stamina anywhere; hits are documentation only (docs/02 D7 traceability, docs/03 §polite scheduler, docs/04, docs/06 §1/§4/§6 register), GOV-02 DEC-013, GOV-04 WP-04-02, and this task's own records. No existing mandatory runtime dependency exists, so stamina is **deferred from the WP-00-01 lock** per the owner's amendment. DEC-013 ("stamina is the single retry layer") remains authoritative for the architecture; the wiring work package is WP-04-02.
- **RapidFuzz:** full-repository search finds **zero source imports** (documentation only: docs/01, docs/02 D4, docs/04 §stage 2, docs/06 §6 register, docs/09, docs/07). No direct core usage demonstrates otherwise → RapidFuzz is assigned to `ingestion` per the owner's amendment.
- **pytest / test-dev group:** pytest is not listed in the D7 register (docs/06 §6); it exists in the hand-maintained `requirements.txt`. GOV-04 WP-00-01 names hash-locked groups "(core, ingestion, docs)" and no governance file names a test/dev group; however GOV-04 WP-00-02 ("Policy, secret and PII gates") presumes a test lock exists ("test fails when selenium is added to a test lock"). The proposal recorded in CURRENT_TASK.md: pytest leaves all production groups and lives only in a separate test/dev lock file. Because the WP-00-01 definition row (owner-controlled, protected) lists only three groups, this is flagged as an owner-confirmed amendment, not silently adopted.
- **pydantic-xml (PyPI JSON metadata check, 2026-11-13):** latest release **2.22.0**; `requires_dist`: `pydantic>=2.14.0`, `pydantic-core>=2.15.0`, optional `lxml>=4.9.0` (extra "lxml"), Sphinx tooling under extra "docs"; `requires_python`: ">=3.10"; classifiers list Python 3.10–3.15 (3.12, 3.13, 3.14 included); pure-Python wheel. Compatible with the project floor (pydantic>=2.14.2; the baseline venv resolved pydantic 2.14.3 with pydantic-core 2.50.4) and with Python 3.12–3.14 per metadata. The owner's remaining conditions (suite run in a clean venv, exact version+hashes recorded in the lock, documented resolution/update policy) will be executed at lock time; **not yet performed**.
- **GOV-05 §8 exact wording (verified):** "Dependency consistency | `pip check` | standard tool; applies after WP-00-01" and "Install from lock | `<install-from-lock-command>` | defined by WP-00-01". An earlier note in CURRENT_TASK.md paraphrased both as "defined by WP-00-01"; the exact statuses differ and this record supersedes that paraphrase.
- **requirements.txt (Option 2):** the generated core lock file IS `requirements.txt`; its source of truth becomes a `.in` input; Dockerfile, compose, CI and manifest detection must stay compatible; generated lock files are never hand-maintained.
- **GTK / PCD-011:** the owner defers installing the GTK runtime. G1 (configured `python -m pytest -q`) on this Windows machine will be recorded **`unavailable`, never passed**; the 283-pass diagnostic (`.ai-engineering/EVIDENCE/WP-00-01/baseline/diagnostic_pytest_ignore-ui-integration_20261113-120352.txt`) is **supplementary evidence only**; KI-012 documents the missing-GTK blocker. No machine-level dependencies are installed without authorization.

## Authenticity note (KI-009)

This record was written by the implementer agent from the owner's chat message. The independent reviewer must confirm it against the owner's actual message before treating these decisions as authentic. Per AGENTS.md, chat history is not authoritative — repository files are — which is why this record carries the owner's instructions into the repository.
