# Adapter: Gemini CLI

**Adapter protocol:** 1. This file holds loading facts only. It defines no policy; the canonical rules are in
`../../CORE/` and `../UNIVERSAL_AGENT.md`. If this file disagrees with them, this file is wrong.

## 1. Canonical instructions
Gemini CLI reads the repository-root `GEMINI.md`, whose only content is an import of the root `AGENTS.md`.
That file lists the canonical files (`CORE/*.md`, `AGENTS/UNIVERSAL_AGENT.md`). Nothing is copied.

## 2. Project profile and contract map
Listed in root `AGENTS.md` section 2: `CONFIG/project_profile.yml`, `CONFIG/project_contract_map.yml`, `CONFIG/framework.yml`.

## 3. Role
The owner names the role in the first prompt; the agent reads `AGENTS/IMPLEMENTER.md` or `AGENTS/REVIEWER.md`.

## 4. Bootstrap or resume
New task: `AGENTS/UNIVERSAL_AGENT.md` section 1. Resume: `AGENTS/HANDOFF_AND_RESUME.md` plus `WORKFLOW/handoff_protocol.md`.

## 5. Where state, evidence and handoffs go
`MEMORY/`, `MEMORY/handoffs/<task-id>/`, `EVIDENCE/<task-id>/` (all under `.ai-engineering/`).

## 6. Verified loading mechanism
- **Verified on:** 2026-11-11
- **Sources:** https://geminicli.com/docs/cli/gemini-md (official documentation site); https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html (older copy of the same page)
- **Verified from the documentation:**
  - Context files default to the name `GEMINI.md`; they are loaded hierarchically (global `~/.gemini/GEMINI.md`, workspace and parent directories, and just-in-time files found when tools touch a directory), concatenated, and sent with every prompt.
  - Imports use a line such as `@./components/instructions.md`.
  - `/memory show` prints the full concatenated context.
  - The filename list can be changed with `context.fileName` in `settings.json` (example shown: `["AGENTS.md", "CONTEXT.md", "GEMINI.md"]`).
- **Documentation differs between versions:** the current page lists `/memory reload`; the older copy lists `/memory refresh`. A third-party guide shows a legacy key `contextFileName`. Check `/help` on the installed version; no Gemini CLI version is recorded here.
- **Not verified here:** no Gemini CLI was run in the session that wrote this file.
- **Entry mechanism used:** `GEMINI.md` containing one import line, `@./AGENTS.md`. The `context.fileName` alternative is not used.

## 7. How to confirm the contract loaded
Start a fresh session, run `/memory show`, and confirm the text of the root `AGENTS.md` (including the line beginning
`AEF-ADAPTER-MARKER`) appears inline. Then send the C1 prompt from `QUALITY/adapter_conformance.md`. If the import path is
wrong a third-party guide reports the rules may simply be absent with no error, so `/memory show` is mandatory, not optional.

## 8. Known caveats
- **Do not combine mechanisms:** if `context.fileName` is set to include `AGENTS.md` while `GEMINI.md` also imports it, the
  content is loaded twice. `SCRIPTS/adapters/check_adapters.py` flags a project `.gemini/settings.json` that does this.
- **Global context:** `~/.gemini/GEMINI.md` is also concatenated. Inspect it in `/memory show`; foreign text there does not
  override the canonical rules.
- **Import syntax:** keep the import on its own line and outside code fences (this is the form shown in the documentation).

## 9. Conformance status
- **Status:** not_run
- **Evidence:** none. The C1 to C6 sessions in `QUALITY/adapter_conformance.md` must be run on the owner's machine.
