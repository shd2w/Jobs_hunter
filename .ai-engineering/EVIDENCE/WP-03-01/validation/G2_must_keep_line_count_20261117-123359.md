---
task_id: "WP-03-01"
gate_id: "G2"
label: "automated-test"
status: "passed"
agent_label: "unlabelled-agent"
commit: "2cd53f1e5c524cd9c0d4b9d5ad698924bbeee89b"
tree_dirty: true
source_fingerprint: "b3ab3742b157bbd731b435d9386333d2f5ad7ecef488128aa8e150f28a47bc56"
command: "run_gates.py mustkeep --base a1812f0485df1ef62f597a290620e88329c4e884"
environment: "Windows 10; python 3.10.0"
verdict_rationale: "no deletion or shrink beyond limit"
command_id: "must_keep_line_count"
output_ref: "inline below"
timestamp: "2026-11-17T12:33:59+02:00"
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
