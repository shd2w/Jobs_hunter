---
task_id: "FW-D"
gate_id: "G2"
label: "automated-test"
status: "passed"
agent_label: "unlabelled-agent"
commit: "00d6a5f5b9b8e0ba4be9d2a9ab91ffe55e0ed072"
tree_dirty: true
source_fingerprint: "603e92d23ffac17a3c838ec1960dd125dbfb49174f9999201b21adb4c308dcc2"
command: "run_gates.py mustkeep --base HEAD"
environment: "Linux 6.18.44-fc-v378; python 3.13.18"
verdict_rationale: "no deletion or shrink beyond limit"
command_id: "must_keep_line_count"
output_ref: "inline below"
timestamp: "2026-11-11T17:03:09+02:00"
---

MUST-KEEP check against `HEAD` (limit 20% shrink; any change needs a recorded reason, docs/PROMPT.md section 2)

No MUST-KEEP file changed.
