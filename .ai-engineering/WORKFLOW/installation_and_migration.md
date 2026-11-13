# Installation and migration guide

**Applies to:** installing the framework into another project, or into an existing project that already has agent
instruction files. **Status of this guide:** tested by `SCRIPTS/bootstrap/test_install_framework.py` on Linux with toy
projects only. It has not been run on Windows or macOS, or on any real second project.

## 1. What the installer does and does not do

`python <source>/.ai-engineering/SCRIPTS/bootstrap/install_framework.py --target <project> --name "<name>"` does this:

| It does | It does not |
|---|---|
| Copies `CORE/`, `AGENTS/`, `WORKFLOW/`, `QUALITY/`, `SCRIPTS/` (without the framework's own tests) | Run any gate or any test of the target project |
| Generates `CONFIG/`, `MEMORY/` and the registries with every owner decision set to `pending_owner` | Guess a language, a test command, protected files or a base branch |
| Writes root `AGENTS.md` and `GEMINI.md`, or `*.aef-proposed` if the file already exists | Overwrite or merge an existing `AGENTS.md` / `GEMINI.md` |
| Scans the target and registers its files as `generated-unreviewed` | Say what any file is for: `purpose` stays empty until a person writes it |

Re-running with `--force` replaces only the framework's own files. Existing `CONFIG/`, `MEMORY/` and registries are kept.

## 2. Steps for a new or existing project

1. **Commit or stash first.** Work from a clean tree so the installation is one reviewable change. Create a branch.
2. **Run the installer** (above). Read its output: it lists kept files and migration proposals.
3. **Owner fills `CONFIG/project_profile.yml`.** Replace each `pending_owner`: project type, platforms, source/test roots,
   `runtime_data` (directories with private data), `protected.must_keep` files, and approval-sensitive operations.
   Nobody else may decide these (constitution: owner decisions are not agent decisions).
4. **Set the real test command** in `CONFIG/command_profiles.yml` (`tests_all`: `run` and `status: exists`). Its failing
   output must contain lines starting `FAILED <test-id>` or `ERROR <test-id>` (pytest's default does) so that
   `run_gates.py regressions` can tell pre-existing failures from new ones. For another runner, adapt the output or
   `FAIL_ID` in `run_gates.py`, and record that change.
5. **Name the project's task board and decision log** in `CONFIG/project_contract_map.yml` with `role: task_source` and
   `role: decision_authority`. `check_memory.py start` reads them; without a task board it fails closed. The board must use
   the `WP-nn-nn` ids and the table layout `| id | title | scope | non-scope | dependencies | outputs | proof | exit | status |`,
   or the patterns in `QUALITY/checkpoint_schema.yml` and `WP_ID` in `check_memory.py` must be changed (known limit).
6. **Fill every registry `purpose`.** `python .ai-engineering/SCRIPTS/documentation/check_registry.py check` lists each
   file with an empty purpose as an error; this is intended. Write what the file is for in your own words after reading it.
   Flip `provenance` to `reviewed` only for entries a person actually confirmed.
7. **Baseline before any change.** Run `python .ai-engineering/SCRIPTS/validation/run_gates.py baseline --task <id>` and
   record what already fails. A failure that exists before your change is classified, not hidden.
8. **Run the three checks:** `check_memory.py state`, `check_registry.py check`, `check_adapters.py check`.
9. **Run the live CLI conformance suite** (`QUALITY/adapter_conformance.md`, C1 to C6) in each CLI you use. Until then the
   adapters are only well-formed files, and `phase_E_live_cli_conformance` stays `not_run`.
10. **Review, then commit** the installation on its branch.

## 3. Migration: a project that already has `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` or `.kiro/steering`

- The installer never edits them. It writes `AGENTS.md.aef-proposed` / `GEMINI.md.aef-proposed` beside them.
- Merge by hand. Rules that belong to the project (build commands, style) may stay in the existing file but must **not**
  weaken, replace or restate the framework's rules (adapters hold pointers, not policy; constitution section 6).
  `check_adapters.py` flags copied canonical lines, weakening phrases, completion definitions and double loading.
- Keep exactly one mechanism per CLI: Gemini CLI loads `GEMINI.md`, which imports `AGENTS.md`. If `.gemini/settings.json`
  also lists `AGENTS.md`, content loads twice.
- A `CLAUDE.md` is outside the three supported targets. If Claude Code is used, decide that separately (open decision KI-008).
- Existing steering or rules that contradict the framework: list them for the owner; do not delete them silently.

## 4. Upgrading an installation

Re-run the installer with `--force` from a newer source, then review the diff of `CORE/`, `AGENTS/`, `WORKFLOW/`,
`QUALITY/` and `SCRIPTS/` like any other change. `CORE/` changes only through constitution section 10. Run the three
checks again; refresh registry entries with `check_registry.py refresh <paths>` only after reading the changed files.

## 5. Known limits of the template

- The shared documents contain a few JobHunter examples (for instance the commit-message convention in
  `CORE/universal_standards.md`). They are harmless to the checks but should be reworded through a `CORE` amendment.
- The framework's own test suites and the Phase F stress suite are not copied; they target this repository's fixtures.
- Windows and macOS behaviour is unverified; paths with spaces, non-ASCII names, CRLF files and non-UTF-8 command output
  are covered by Linux tests only.
