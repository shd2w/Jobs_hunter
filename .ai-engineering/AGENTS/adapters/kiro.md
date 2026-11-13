# Adapter: Kiro (IDE and CLI)

**Adapter protocol:** 1. This file holds loading facts only. It defines no policy; the canonical rules are in
`../../CORE/` and `../UNIVERSAL_AGENT.md`. If this file disagrees with them, this file is wrong.

## 1. Canonical instructions
Kiro reads the repository-root `AGENTS.md`, which lists the canonical files (`CORE/*.md`, `AGENTS/UNIVERSAL_AGENT.md`).
Nothing is copied into Kiro-specific files.

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
- **Sources:** https://kiro.dev/docs/steering/ (official; the page states "Page updated: October 21, 2026")
- **Verified from the official page:**
  - An `AGENTS.md` in the workspace root is picked up automatically and is always included; `AGENTS.md` files do not support inclusion modes.
  - The documentation table lists AGENTS.md support for IDE, CLI, Web and Mobile.
  - `AGENTS.md` files in subdirectories are also discovered (not used by this installation).
  - Custom agents do NOT include steering automatically; steering must be added to the agent's `resources`.
- **Not verified here:** no Kiro IDE or CLI was run in the session that wrote this file; no Kiro version is recorded.
- **Entry file used:** root `AGENTS.md`. No `.kiro/steering/` files are created, so no second instruction surface exists.

## 7. How to confirm the contract loaded
Start a fresh session and send the C1 prompt from `QUALITY/adapter_conformance.md`. The reply must quote the line
beginning `AEF-ADAPTER-MARKER` from the root `AGENTS.md` without the agent first reading any file. A reply that cannot
is a failed load, not a pass.

## 8. Known caveats
- **Custom agents:** the official page documents `"resources": ["file://.kiro/steering/**/*.md"]` for steering files.
  It does not say that this glob covers a root `AGENTS.md`. Whether `file://AGENTS.md` works in `resources` is **unverified**.
  If a custom agent is used, run C1 to C4 against it and record the result; do not assume it loads.
- **Symlinks (reported, unverified):** a user-filed GitHub issue (https://github.com/kirodotdev/Kiro/issues/8121) reports that a
  symlinked steering file was not loaded. This installation uses real files only; keep it that way (also required for Windows).
- **File references:** Kiro's `#[[file:...]]` syntax is Kiro-only. It is deliberately not used in the shared `AGENTS.md`.
- **Global steering:** `~/.kiro/steering/` also loads and may add instructions outside this repository. Check the session's
  steering list; global text does not override the canonical rules.

## 9. Conformance status
- **Status:** not_run
- **Evidence:** none. The C1 to C6 sessions in `QUALITY/adapter_conformance.md` must be run on the owner's machine.
