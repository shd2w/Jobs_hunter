# Known Issues

Confirmed defects, limitations, unresolved root causes. Format per entry: id, status, classification
(pre-existing / environmental / introduced / flaky / unknown), evidence, workaround.

## KI-001 - test collection errors in the review container
- Status: resolved 2026-11-12 (see the resolution line below), classification: environmental
- 3 collection errors (`tests/test_extra_sources.py`, `test_jd_fetcher.py`, `test_run_all_export_integration.py`): `ModuleNotFoundError: httpx`. `httpx>=0.27.0` is in `requirements.txt`; it was not installed in that container.
- Observed 2026-11-10 with `python -m pytest --collect-only -q` (243 collected). No baseline run was made. Capture a real baseline after installing requirements.
- Resolution 2026-11-12: `pip install -r requirements.txt` in a fresh Python 3.12.3 venv (`pip check` clean), then `python -m pytest -q`: **286 passed, 0 failed, 0 skipped** in 14.9 s. This confirms the 286 figure in the governance documents on Linux. Not verified: Windows, Python 3.13, the owner's real environment.

## KI-002 - MUST-KEEP file set is an interpretation
- Status: open, classification: unknown
- `docs/PROMPT.md` section 2 names features and some wildcards (`*_client.py`); `CONFIG/project_profile.yml` lists the concrete files. Owner to confirm the exact set.

## KI-003 - suite counts not machine-verified
- Status: open. The spec states 73 WPs / 51 DEC / 29 PCD / 27 INV / 21 gates; no script checks them against the documents yet (planned for Phase C/D).

## KI-004 - owner contact data in tracked files
- Status: open, classification: pre-existing (known to the suite)
- `config/profile.yml` and `CV_Example.py` are tracked by Git and contain the owner's real contact details (S4 under GOV-03). GOV-03 section 4 requires them in an untracked profile with a tracked example; WP-00-02 is the package that fixes this. The framework did not change either file and does not copy the values anywhere (registry classifies both S4).
- Note for the owner: if the repository is or becomes public, these values are already in its history.

## KI-005 - German-policy guard test replicates production logic
- Status: open, classification: pre-existing
- `docs/PROMPT.md` names `tests/test_german_policy.py` as the guard for AI scoring and German policies. That test defines its own `apply_german_policy` and `clamp_score` ("Replicates the logic from run_evaluate.py ... lines 216-256") and imports nothing from the project, so it cannot detect a regression in `run_evaluate.py`. Treat it as a fixture of intended behaviour, not as an automated test of the code.
- Observed 2026-11-10 by reading the test header and imports.

## KI-006 - German policy default: README versus code (to verify)
- Status: open, classification: unknown
- README says the default `evaluation.german_filter` is `reject_b1_plus`; `run_evaluate.py` line 408 falls back to `accept_all` when `config/profile.yml` has no such key. Whether the shipped profile sets it was not checked. Related: PCD-006 / WP-01-02.

## KI-007 - adapters are not proven to load in any real CLI
- Status: open, classification: environmental (no Kiro, Gemini CLI or OpenCode session was available when Phase E was built)
- `SCRIPTS/adapters/check_adapters.py` and its 46 tests show the entry files are well formed. They cannot show that a CLI loads or follows them. Live tests C1-C6 (`QUALITY/adapter_conformance.md`) are `not_run` for all three CLIs; spec 18 criteria 1-3 are therefore unmet.
- Next step: the owner runs C1-C6 per CLI in a disposable clone and records `EVIDENCE/FW-E/conformance/<cli>_<date>.md`.

## KI-012 - Windows: missing GTK/Pango runtime aborts the whole test suite at collection
- Status: open, classification: environmental (pre-existing)
- Observed 2026-11-13, WP-00-01 baseline (Windows 11, fresh Python 3.12.8 venv with `requirements.txt` installed, `pip check` clean): the configured baseline command `python -m pytest -q` exits 2 with **1 collection error and zero tests run**. `tests/test_ui_integration.py:10` calls `pytest.importorskip("weasyprint")`; WeasyPrint 70.0 raises `OSError: cannot load library 'libgobject-2.0-0'` because the GTK/Pango runtime is absent on the machine. `importorskip` catches only `ImportError`, so the `OSError` aborts collection for the entire suite.
- Evidence: baseline record `.ai-engineering/EVIDENCE/WP-00-01/baseline/G1_tests_all_20261113-120305.md` (status failed, exit 2); diagnostic run excluding only that module: **283 passed, 0 failed** in 11.5 s (`.ai-engineering/EVIDENCE/WP-00-01/baseline/diagnostic_pytest_ignore-ui-integration_20261113-*.txt`). The Linux reference is unchanged: 286 passed (KI-001, 2026-11-12).
- Workaround: install the GTK runtime on Windows (owner decision, PCD-011), or run pytest with `--ignore=tests/test_ui_integration.py` (diagnostic only; it is not the configured gate command).
- Related: PCD-011; WP-00-03 ("missing WeasyPrint fails instead of skipping" is the designed behaviour per docs/06 section 1; making the skip robust against `OSError` would be a test change needing a written reason per G1).
- Not fixed in WP-00-01 (scope is the dependency lock; G1 requires tests unchanged).

## KI-013 - Dockerfile installs playwright outside the dependency manifest
- Status: open, classification: manifest inconsistency (pre-existing)
- The Dockerfile build stage runs `pip install playwright && playwright install --with-deps chromium` after installing the hash-locked core lock; `playwright` is declared in neither `pyproject.toml` nor any `requirements*.in`, so a container build's Python environment is not fully described by the manifest and that install bypasses hash-locked installation.
- Owner decision 2026-11-13: leave unchanged in WP-00-01; track for a later work package (container/CI scope, cf. WP-00-03).
- Related: WP-00-01 (the core-lock install line itself now uses `--require-hashes`).

## KI-014 - run_gates.py manifest_names parses pyproject.toml as a requirements file
- Status: open, classification: framework defect (pre-existing; first observed 2026-11-13 in WP-00-01)
- `manifest_names` (SCRIPTS/validation/run_gates.py) extracts the leading bare token of any non-comment line, so pyproject.toml is parsed like a requirements file: quoted dependencies are skipped and bare TOML keys (dependencies, description, docs, ingestion, name, requires-python, version) are reported as if they were packages.
- Effect: the approvals gate can miss a genuinely new quoted dependency; in WP-00-01 it passed only via the pre-existing approval record (`.ai-engineering/MEMORY/approvals/WP-00-01/add_dependency_or_external_service.md`).
- Mitigation until fixed: every pyproject.toml dependency change requires explicit human review (owner decision 2026-11-13; also recorded in CONFIG/project_profile.yml dependency_policy).
- Tracked: WP-00-05 (framework work item created 2026-11-13 per owner instruction; regression tests required).

## KI-015 - install_from_lock gate can false-pass on a pre-populated venv
- Status: open, classification: framework hardening (observed 2026-11-13 in the WP-00-01 review)
- The configured command (`python -m pip install --require-hashes -r requirements.txt`) proves little when the target venv already contains the pins: the gate record of 2026-11-13 13:29:25 shows every line "Requirement already satisfied", so that record alone does not demonstrate a hash-checked install.
- Mitigations in place: the real fresh-install proof lives in `EVIDENCE/WP-00-01/proof_venv/` (exit-0 logs), and the independent review re-executed a true fresh install (`--require-hashes --no-cache-dir`, exit 0) whose freeze exactly equals the lock union; a corrected negative test (all hashes of one pin flipped) confirmed pip refuses mismatches.
- Owner decision 2026-11-13: track as future hardening - consider a fresh-venv-per-run or `--no-cache-dir` variant of the gate command (framework item; not WP-00-01 scope).

## KI-008 - parts of the adapter facts come from third parties or are version-dependent
- Status: open, classification: unknown
- Official documentation verified 2026-11-11: Kiro steering page (updated 2026-10-21), Gemini CLI GEMINI.md page, OpenCode rules page. Unverified: whether `file://AGENTS.md` works in a Kiro custom agent's `resources`; the reported Kiro symlink limitation (user-filed GitHub issue); exact CLI versions; Gemini CLI `/memory reload` versus `/memory refresh` and the `context.fileName` versus legacy `contextFileName` key differ between documentation versions.
- Owner decisions, not made by the framework: (a) whether to force the canonical files into context (`instructions` in `opencode.json`, imports in `GEMINI.md`) instead of relying on the read instruction in `AGENTS.md`, at the cost of loading them into every session; (b) whether to add a `CLAUDE.md` adapter for Claude Code (outside the three targets in the spec; a third-party source says Claude Code does not read `AGENTS.md` natively; not verified against Claude Code documentation).

## KI-009 - approval and evidence records cannot be authenticated by the scripts
- Status: open, classification: unknown (design limit)
- `run_gates.py approvals` proves an approval record exists and names the operation, the task, the owner message and the scope. It cannot prove the owner wrote it. An agent can also hand-write an evidence record or edit `status: failed` to `passed`; only the `exit_code` consistency rule and the independent review catch that. Mitigation: the reviewer checks each approval against the owner's actual message and re-runs the commands.
- Operations that leave no trace in Git (production deploy, data sent to an external service) are not detected at all.

## KI-010 - the template still carries a few JobHunter sentences
- Status: open, classification: unknown
- `CORE/universal_standards.md` (commit-message convention), `WORKFLOW/browser_ux_workflow.md` and one comment in `QUALITY/checkpoint_schema.yml` name JobHunter. They do not affect any check. Rewording them is a `CORE` amendment (constitution section 10), so the owner decides.
- `WP-nn-nn` ids and the work-package table layout are assumed by `check_memory.py start` and `known_wp_ids`; another project must use them or change `WP_ID` and the schema patterns.
- The installer and its guide were tested on Linux toy projects only.

## KI-011 - Phase F scenarios were run in a harness, not by real agents
- Status: open, classification: unknown
- `SCRIPTS/stress/test_scenarios.py` drives the scripts through their command lines to stage each scenario. It shows the scripts detect the violations. It does not show that a real agent, on a real CLI, follows the protocol; that remains the live conformance suite (KI-007). Scenarios 5 and 6 simulate the CLI switch inside one process; a switch between two real CLIs was not run.
