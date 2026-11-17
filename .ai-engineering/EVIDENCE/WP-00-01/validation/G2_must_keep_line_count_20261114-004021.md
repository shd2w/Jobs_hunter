---
task_id: "WP-00-01"
gate_id: "G2"
label: "automated-test"
status: "passed"
agent_label: "unlabelled-agent"
commit: "1273eb3c79401c7997300856a356f15969d6f908"
tree_dirty: true
source_fingerprint: "1c46b2675f74c9f97a5bde1e60e72133f1143504c84c0b6da3a23ce79ecde6b4"
command: "run_gates.py mustkeep --base 83c423f"
environment: "Windows 10; python 3.10.0"
verdict_rationale: "no deletion or shrink beyond limit"
command_id: "must_keep_line_count"
output_ref: "inline below"
timestamp: "2026-11-14T00:40:21+02:00"
---

MUST-KEEP check against `83c423f` (limit 20% shrink; any change needs a recorded reason, docs/PROMPT.md section 2)

| file | before | after | flag |
|---|---|---|---|
| run_evaluate.py | 516 | 472 | shrunk |
| run_export_queue.py | 87 | 92 | changed |
| run_health.py | 177 | 198 | changed |
| scanners/ats.py | 230 | 238 | changed |
| scanners/bridge.py | 200 | 218 | changed |
| agents/evaluator.py | 320 | 374 | changed |
| agents/smart_router.py | 309 | 383 | changed |
