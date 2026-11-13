# Handoff protocol (operational summary)

Authority: `AGENTS/HANDOFF_AND_RESUME.md` (triggers, resume checklist) and constitution section 6. This file adds the commands.

**Saving (outgoing agent).** Copy `WORKFLOW/handoff_template.md` to `MEMORY/handoffs/<task-id>/<YYYYMMDD-HHmmss>_<agent-label>.md`, fill every section, update `PROJECT_STATE.yml` and `CURRENT_TASK.md`, then run:

    python .ai-engineering/SCRIPTS/memory/check_memory.py state
    python .ai-engineering/SCRIPTS/memory/check_memory.py handoff <file> --against-git

Exit code 0 = valid, 1 = findings that must be fixed, 2 = usage/environment error. Fix findings before stopping; if the model is out of quota, record the unfixed findings in the handoff's Recovery instructions.

**Resuming (incoming agent).** Run the same two commands first. Any error finding means the saved state disagrees with the repository: reconcile before editing. The scripts do not replace re-running the checkpoint tests listed in the handoff.

The owner switches models manually; nothing here selects or switches a model.
