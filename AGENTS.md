# AGENTS.md - entry point for coding agents (JobHunter)

AEF-ADAPTER-MARKER: root-entry/1

This file is a thin loader. It states no policy and defines no exceptions. The canonical rules live in
`.ai-engineering/`. If this file and those rules ever disagree, the rules win and this file is wrong.
Chat history is not authoritative; the repository files are.

## 1. Canonical instructions (read all of them, in this order, before any other action)

1. `.ai-engineering/CORE/engineering_constitution.md`
2. `.ai-engineering/CORE/universal_standards.md`
3. `.ai-engineering/CORE/evidence_and_claims.md`
4. `.ai-engineering/CORE/definition_of_done.md`
5. `.ai-engineering/AGENTS/UNIVERSAL_AGENT.md` (bootstrap sequence and operating rules)

## 2. Project context

- `.ai-engineering/CONFIG/project_profile.yml`
- `.ai-engineering/CONFIG/project_contract_map.yml`
- `.ai-engineering/CONFIG/framework.yml`
- Project governance suite: `docs/governance/` and `docs/PROMPT.md` (authority for decisions, scope, work packages, gates).

## 3. Role

The owner names the role. Read the matching contract: `.ai-engineering/AGENTS/IMPLEMENTER.md` or
`.ai-engineering/AGENTS/REVIEWER.md`. If no role was named, ask before touching any file.

## 4. Bootstrap or resume

- New task: follow `.ai-engineering/AGENTS/UNIVERSAL_AGENT.md` section 1. The owner names the work package.
- Resuming, or the previous model or CLI stopped: follow `.ai-engineering/AGENTS/HANDOFF_AND_RESUME.md`
  and run the commands in `.ai-engineering/WORKFLOW/handoff_protocol.md` before editing.

## 5. Where records go

- State: `.ai-engineering/MEMORY/` (`PROJECT_STATE.yml`, `CURRENT_TASK.md`)
- Handoffs: `.ai-engineering/MEMORY/handoffs/<task-id>/`
- Evidence: `.ai-engineering/EVIDENCE/<task-id>/`
