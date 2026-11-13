# Adapter: OpenCode

**Adapter protocol:** 1. This file holds loading facts only. It defines no policy; the canonical rules are in
`../../CORE/` and `../UNIVERSAL_AGENT.md`. If this file disagrees with them, this file is wrong.

## 1. Canonical instructions
OpenCode reads the repository-root `AGENTS.md`, which lists the canonical files (`CORE/*.md`, `AGENTS/UNIVERSAL_AGENT.md`).
Nothing is copied into OpenCode-specific files.

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
- **Sources:** https://opencode.ai/docs/rules/ and https://opencode.ai/en/docs/rules (official documentation)
- **Verified from the documentation:**
  - A project `AGENTS.md` is read natively; rule files are searched by traversing up from the current directory, then the global `~/.config/opencode/AGENTS.md`.
  - The first matching file wins within each category: `AGENTS.md` takes precedence over `CLAUDE.md`.
  - `opencode.json` accepts an `instructions` list (paths, globs, remote URLs); those files are combined with `AGENTS.md`.
  - OpenCode does not automatically parse file references inside `AGENTS.md`; the agent must read referenced files with its tools.
- **Not verified here:** no OpenCode session was run; no OpenCode version is recorded.
- **Entry file used:** root `AGENTS.md`. No `opencode.json` is created.

## 7. How to confirm the contract loaded
Start a fresh session and send the C1 prompt from `QUALITY/adapter_conformance.md`. The reply must quote the line
beginning `AEF-ADAPTER-MARKER` without the agent first reading any file.

## 8. Known caveats
- **Reading is by instruction, not injection:** only `AGENTS.md` itself is guaranteed to be in context. The canonical files are
  read because `AGENTS.md` tells the agent to. If a model does not follow that instruction, C2 fails. Forcing them into context
  with `instructions` in `opencode.json` is possible but loads every listed file into every session. That trade-off is an
  owner decision and is not made here.
- **Global rules:** `~/.config/opencode/AGENTS.md` also applies. Foreign text there does not override the canonical rules.
- **Claude Code fallback files:** `CLAUDE.md` is used only when no `AGENTS.md` exists. None exists in this repository.

## 9. Conformance status
- **Status:** not_run
- **Evidence:** none. The C1 to C6 sessions in `QUALITY/adapter_conformance.md` must be run on the owner's machine.
