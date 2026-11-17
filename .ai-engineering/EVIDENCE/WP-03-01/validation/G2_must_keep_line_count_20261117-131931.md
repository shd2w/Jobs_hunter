---
task_id: "WP-03-01"
gate_id: "G2"
label: "automated-test"
status: "passed"
agent_label: "unlabelled-agent"
commit: "a165a242327f170beeb629142c0fa0a642f6f940"
tree_dirty: true
source_fingerprint: "a1e6b10f807f07d52643f5189174eef52ca7924d37fab29faaf1c4e19ee50b48"
command: "run_gates.py mustkeep --base a1812f0485df1ef62f597a290620e88329c4e884"
environment: "Windows 10; python 3.10.0"
verdict_rationale: "no deletion or shrink beyond limit"
command_id: "must_keep_line_count"
output_ref: "inline below"
timestamp: "2026-11-17T13:19:31+02:00"
---

MUST-KEEP check against `a1812f0485df1ef62f597a290620e88329c4e884` (limit 20% shrink; any change needs a recorded reason, docs/PROMPT.md section 2)

| file | before | after | flag |
|---|---|---|---|
| run_evaluate.py | 472 | 472 | changed |
| run_export_queue.py | 92 | 92 | changed |
| run_health.py | 198 | 198 | changed |
| scanners/ats.py | 238 | 238 | changed |
| scanners/bridge.py | 218 | 218 | changed |
| agents/evaluator.py | 374 | 374 | changed |
| agents/smart_router.py | 383 | 383 | changed |
