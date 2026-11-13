#!/usr/bin/env python3
"""Quality-gate runner and evidence tools (spec 11, roadmap Phase D). Standard library only.

    run_gates.py run <command-id> --task WP-pp-nn --area baseline|validation [--gate G1] [--label automated-test]
    run_gates.py mustkeep --base REV --task WP-pp-nn          # G2 line counts for MUST-KEEP files
    run_gates.py docs-gate --task WP-pp-nn                    # registry + memory consistency (spec 10.3)
    run_gates.py validate-evidence PATH [PATH ...]            # file or directory
    run_gates.py validate-review FILE [--task WP-pp-nn]       # --task also writes the REVIEW gate record
    run_gates.py baseline --task WP-pp-nn                     # tests + git state, area baseline (never closes a gate)
    run_gates.py protected --base REV --task WP-pp-nn         # owner-controlled paths unchanged
    run_gates.py record-ui --task ... --viewport WxH --image F --workflow W --result passed|failed --tool T
    run_gates.py summary --task WP-pp-nn
    run_gates.py close-check --task WP-pp-nn [--require G1,G2,...] [--base REV]   # REG, UI, REGRESSIONS are gate ids too
    run_gates.py regressions --task WP-pp-nn                  # baseline vs post-change failures: pre-existing / introduced / fixed
    run_gates.py approvals --base REV --task WP-pp-nn         # high-risk operations in the change need an owner approval record

Commands come from CONFIG/command_profiles.yml; nothing toolchain-specific is hard-coded.
Fail closed: a command that is unavailable, owner_machine_only or has no `run` is recorded as
`unavailable` and never as passed. Exit codes: 0 ok, 1 gate failed / findings, 2 usage or environment error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path

FW = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FW / "SCRIPTS" / "memory"))
sys.path.insert(0, str(FW / "SCRIPTS" / "documentation"))
import check_memory as cm  # noqa: E402
import check_registry as cr  # noqa: E402

ROOT = FW.parent
MAX_OUTPUT = 400_000


# ------------------------------------------------------------------ helpers
def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).astimezone()


def load(fw: Path):
    return (cm.load_yaml(fw / "CONFIG/command_profiles.yml"), cm.load_yaml(fw / "CONFIG/project_profile.yml"),
            cm.load_yaml(fw / "QUALITY/evidence_schema.yml"))


def redact(text: str) -> tuple[str, int]:
    n = 0
    for pat, _ in cm.SECRET_PATTERNS:
        text, k = re.subn(pat, "[REDACTED]", text)
        n += k
    return text, n


def source_fingerprint(fw: Path) -> str:
    """Hash of every maintained file outside the framework folder: detects code/config change."""
    root = fw.parent
    profile = cm.load_yaml(fw / "CONFIG/project_profile.yml")
    h = hashlib.sha256()
    for rel in cr.maintained_files(root, profile):
        if rel.startswith(".ai-engineering/"):
            continue
        h.update(rel.encode() + b"\0" + cr.sha(root / rel).encode() + b"\n")
    return h.hexdigest()


def head(root: Path) -> str:
    return (cm.git(root, "rev-parse", "HEAD") or "unknown").strip()


def safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")[:60] or "x"


def write_record(fw: Path, rec: dict, body: str, area: str) -> Path:
    ts = now()
    rec.setdefault("timestamp", ts.isoformat(timespec="seconds"))
    d = fw / "EVIDENCE" / rec["task_id"] / area
    d.mkdir(parents=True, exist_ok=True)
    name = f"{safe(rec['gate_id'])}_{safe(rec.get('command_id', rec['gate_id']))}_{ts.strftime('%Y%m%d-%H%M%S')}.md"
    p = d / name
    n = 1
    while p.exists():
        p = d / name.replace(".md", f"-{n}.md")
        n += 1
    lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in rec.items()] + ["---", "", body.rstrip(), ""]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def read_record(p: Path):
    t = p.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n(.*)", t, re.S)
    if not m:
        raise ValueError("no front matter")
    return cm.parse_yaml_subset(m.group(1)), m.group(2)


def base_record(fw: Path, task: str, gate: str, label: str, status: str, command: str, rationale: str, **extra) -> dict:
    root = fw.parent
    dirty = bool((cm.git(root, "status", "--porcelain") or "").strip())
    rec = {
        "task_id": task, "gate_id": gate, "label": label, "status": status,
        "agent_label": os.environ.get("AI_AGENT_LABEL", "unlabelled-agent"),
        "commit": head(root), "tree_dirty": dirty, "source_fingerprint": source_fingerprint(fw),
        "command": command,
        "environment": f"{platform.system()} {platform.release()}; python {platform.python_version()}",
        "verdict_rationale": rationale,
    }
    rec.update(extra)
    return rec


# ---------------------------------------------------------------------- run
UNAVAILABLE = ("unavailable", "owner_machine_only")
MOCK_WORDS = re.compile(r"(mock|fake|stub|fixture|simulat|offline|dry[- ]?run|canned|demo)", re.I)
NOT_LIVE_PROJECT_LABELS = ("Fixture", "Simulation", "Designer-written", "Prototype", "Demo")
MASS_DELETE = 10                  # deleting this many tracked files in one change is "a large set of files" (spec 12)
FAIL_ID = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.M)
# Command ids -> GOV-05 gate ids, so `run` and `close-check` agree on one id per gate.
GATE_ALIAS = {"tests_all": "G1", "must_keep_line_count": "G2", "policy_test": "G3", "layer_lint": "G4",
              "queue_golden": "G6", "windows_verify": "G7", "simulation_regression": "G10",
              "secret_pii_scan": "G12", "migration_verify": "G13", "golden_cli_tests": "G14"}


def cmd_run(fw: Path, cid: str, task: str, area: str, gate: str | None, label: str | None, timeout: int) -> int:
    cp, _, _ = load(fw)
    cmd = (cp.get("commands") or {}).get(cid)
    if cmd is None:
        print(f"ERROR unknown command id {cid!r}", file=sys.stderr)
        return 2
    gate = gate or GATE_ALIAS.get(cid, cid)
    status = str(cmd.get("status", ""))
    run = cmd.get("run")
    if not run or status.startswith(UNAVAILABLE) or status.startswith("unavailable_until"):
        why = {"owner_machine_only": "needs the owner's machine/network"}.get(status, status or "no run command")
        rec = base_record(fw, task, gate, "unavailable", "unavailable", str(run), f"not run: {why}", command_id=cid,
                          output_ref="n/a (nothing executed)")
        p = write_record(fw, rec, f"Command `{cid}` was NOT executed ({why}). Recorded as unavailable; this is not a pass.", area)
        print(f"UNAVAILABLE {cid}: {why} -> {p.relative_to(fw.parent)}")
        return 1                      # fail closed
    lab = label or cmd.get("evidence_label") or "automated-test"
    try:
        argv = shlex.split(run, posix=(os.name != "nt"))
        if argv and argv[0] in ("python", "python3"):
            argv[0] = sys.executable          # the interpreter running this script; `python` may not exist
        r = subprocess.run(argv, cwd=fw.parent, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        out, code = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""), r.returncode
        st = "passed" if code == 0 else "failed"
        why = f"exit code {code}"
    except subprocess.TimeoutExpired as e:
        partial = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        out, code, st, why = f"timed out after {timeout}s\n{partial}", None, "failed", f"timeout after {timeout}s"
    except OSError as e:
        out, code, st, why = f"could not start: {e}", None, "failed", f"could not start command: {e}"
    out, red = redact(out)
    trunc = len(out) > MAX_OUTPUT
    if trunc:
        out = out[:MAX_OUTPUT // 2] + "\n[... truncated ...]\n" + out[-MAX_OUTPUT // 2:]
    rec = base_record(fw, task, gate, lab, st, redact(run)[0], why, command_id=cid, exit_code=code,
                      output_ref="inline below" + (" (truncated)" if trunc else ""), redactions=red)
    p = write_record(fw, rec, "```\n" + out.rstrip() + "\n```", area)
    print(f"{st.upper()} {cid} ({why}) -> {p.relative_to(fw.parent)}")
    return 0 if st == "passed" else 1


# ----------------------------------------------------------------- mustkeep
def line_count(b: bytes) -> int:
    return b.count(b"\n") + (1 if b and not b.endswith(b"\n") else 0)


def cmd_mustkeep(fw: Path, base: str, task: str, write=True) -> tuple[int, str]:
    _, prof, _ = load(fw)
    root = fw.parent
    mk = prof["protected"]["must_keep"]
    limit = float(mk.get("shrink_stop_and_ask_percent", 20))
    if cm.git(root, "rev-parse", "--verify", base + "^{commit}") is None:
        print(f"ERROR base revision {base!r} not found", file=sys.stderr)
        return 2, ""
    tracked = (cm.git(root, "ls-tree", "-r", "--name-only", base) or "").splitlines()
    rows, stop, notes = [], [], []
    for entry in mk["files"]:
        pref = entry if entry.endswith("/") else None
        paths = [t for t in tracked if (t.startswith(pref) if pref else t == entry)]
        if not paths and not pref and not (root / entry).exists():
            notes.append(f"{entry}: not present at {base[:10]} or now (nothing to compare)")
        for path in paths:
            r = subprocess.run(["git", "-C", str(root), "show", f"{base}:{path}"], capture_output=True)
            before = line_count(r.stdout)
            f = root / path
            if not f.exists():
                rows.append((path, before, None, "DELETED"))
                stop.append(f"{path} deleted (was {before} lines)")
                continue
            after = line_count(f.read_bytes())
            if after == before and f.read_bytes() == r.stdout:
                continue
            pct = (before - after) / before * 100 if before else 0
            flag = "SHRUNK>" + f"{limit:g}%" if pct > limit else ("shrunk" if after < before else "changed")
            rows.append((path, before, after, flag))
            if pct > limit:
                stop.append(f"{path} shrank {pct:.0f}% ({before} -> {after})")
    lines = [f"MUST-KEEP check against `{base}` (limit {limit:g}% shrink; any change needs a recorded reason, docs/PROMPT.md section 2)", ""]
    if rows:
        lines += ["| file | before | after | flag |", "|---|---|---|---|"]
        lines += [f"| {p} | {b} | {a if a is not None else '-'} | {fl} |" for p, b, a, fl in rows]
    else:
        lines.append("No MUST-KEEP file changed.")
    lines += [""] + [f"note: {n}" for n in notes]
    if stop:
        lines += ["", "STOP AND ASK (DEC-042): " + "; ".join(stop)]
    body = "\n".join(lines)
    st = "failed" if stop else "passed"
    print(body)
    if write:
        rec = base_record(fw, task, "G2", "automated-test", st, f"run_gates.py mustkeep --base {base}",
                          "stop-and-ask condition" if stop else "no deletion or shrink beyond limit",
                          command_id="must_keep_line_count", output_ref="inline below")
        p = write_record(fw, rec, body, "validation")
        print(f"{st.upper()} G2 -> {p.relative_to(root)}")
    return (1 if stop else 0), body


# ---------------------------------------------------------------- docs gate
def cmd_docs_gate(fw: Path, task: str) -> int:
    reg = cr.check(fw)
    mem = cm.check_state(fw)
    errs = [m for s, m in reg.items + mem.items if s == "error"]
    warns = [m for s, m in reg.items + mem.items if s == "warn"]
    body = "\n".join([f"ERROR {m}" for m in errs] + [f"WARN  {m}" for m in warns] or ["no findings"])
    st = "failed" if errs else "passed"
    rec = base_record(fw, task, "DOCS", "automated-test", st, "check_registry.check + check_memory.check_state",
                      f"{len(errs)} error(s), {len(warns)} warning(s)", command_id="docs_gate", output_ref="inline below")
    p = write_record(fw, rec, body, "validation")
    print(body)
    print(f"{st.upper()} DOCS -> {p.relative_to(fw.parent)}")
    return 1 if errs else 0


# ------------------------------------------------------- evidence validation
def validate_record(fw: Path, p: Path, schema: dict) -> cm.Findings:
    f = cm.Findings()
    root = fw.parent
    try:
        rec, body = read_record(p)
    except (ValueError, OSError) as e:
        f.error(f"{p.name}: unreadable evidence record ({e})")
        return f
    ev = schema["record"]
    for k in ev["required_fields"]:
        if rec.get(k) in (None, ""):
            f.error(f"{p.name}: required field {k!r} missing or empty")
    label, status = rec.get("label"), rec.get("status")
    if label not in schema["labels"]:
        f.error(f"{p.name}: unknown label {label!r}")
    if status not in schema["gate_statuses"]:
        f.error(f"{p.name}: unknown status {status!r}")
    if status == "passed":
        if label in ("unavailable", "skipped", "mocked", "simulation", "fixture"):
            f.error(f"{p.name}: status passed with label {label!r}: only allowed if the gate permits it; mocked/simulated/fixture evidence cannot prove a live claim")
        if not body.strip() and not rec.get("output_ref"):
            f.error(f"{p.name}: passed without output")
    if label in ("unavailable", "skipped") and status == "passed":
        f.error(f"{p.name}: {label} can never be passed")
    if status in ("unavailable", "skipped") and label not in ("unavailable", "skipped"):
        f.error(f"{p.name}: status {status} must carry label {status!r}")
    if label == "skipped" and not rec.get("verdict_rationale"):
        f.error(f"{p.name}: skipped without justification")
    ec = rec.get("exit_code")
    if status == "passed" and ec not in (None, ""):
        try:
            bad_exit = int(str(ec)) != 0
        except ValueError:
            bad_exit = True
        if bad_exit:
            f.error(f"{p.name}: status passed but exit_code is {ec!r}")
    if label == "live-verification":
        # schema requires: date (= timestamp), machine_or_os (= environment), exact_command (= command),
        # network and provider_or_service (own fields). None of them may be empty.
        for k in ("environment", "command", "network", "provider_or_service"):
            if not rec.get(k):
                f.error(f"{p.name}: live-verification missing {k}")
        marks = sorted({m.lower() for fld in ("provider_or_service", "command", "environment", "network")
                        for m in MOCK_WORDS.findall(str(rec.get(fld) or ""))})
        if marks:
            f.error(f"{p.name}: labelled live-verification but the record mentions {', '.join(marks)}: mocked, simulated, "
                    "fixture, offline or demo output is never live verification (spec 11.2)")
        if rec.get("project_label") in NOT_LIVE_PROJECT_LABELS:
            f.error(f"{p.name}: project label {rec.get('project_label')!r} cannot be live verification")
    if label == "screenshot-evidence":
        for k in ("viewport", "image_path"):
            if not rec.get(k):
                f.error(f"{p.name}: screenshot-evidence missing {k}")
        ip = rec.get("image_path")
        if ip and not (root / ip).exists():
            f.error(f"{p.name}: screenshot file {ip} does not exist")
    if rec.get("commit") and rec["commit"] != "unknown" and cm.git(root, "cat-file", "-e", f"{rec['commit']}^{{commit}}") is None:
        f.error(f"{p.name}: commit {str(rec['commit'])[:10]} not in this repository")
    txt = p.read_text(encoding="utf-8")
    for pat, lab in cm.SECRET_PATTERNS:
        if re.search(pat, txt):
            f.error(f"{p.name}: possible secret in evidence ({lab})")
    return f


def cmd_validate_evidence(fw: Path, targets: list[str]) -> int:
    _, _, schema = load(fw)
    files = []
    for t in targets:
        p = Path(t)
        files += sorted(p.rglob("*.md")) if p.is_dir() else [p]
    if not files:
        print("ERROR no evidence records found", file=sys.stderr)
        return 2
    allf = cm.Findings()
    for p in files:
        allf.items += validate_record(fw, p.resolve(), schema).items
    return allf.report()


# --------------------------------------------------------- review validation
def cmd_validate_review(fw: Path, file: Path, task: str | None = None) -> int:
    _, _, schema = load(fw)
    rv = schema["review_report"]
    f = cm.Findings()
    text = file.read_text(encoding="utf-8")
    secs = {k.lower(): v for k, v in cm.sections(text).items()}
    fields = {k.lower(): v for k, v in cm.bold_fields(text).items()}
    for k in rv["required_fields"]:
        key = k.replace("_", " ")
        if not (any(key in s for s in secs) or any(key in x for x in fields)):
            f.error(f"review report missing '{key}'")
    verdict = next((v for k, v in fields.items() if "verdict" in k), "") or next((v for k, v in secs.items() if "verdict" in k), "")
    # longest first: "approved" must not match inside "approved-with-conditions"
    vm = next((v for v in sorted(rv["verdicts"], key=len, reverse=True)
               if re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", verdict.lower())), None)
    if not vm:
        f.error(f"verdict missing or not one of {rv['verdicts']}")
    sev = [m.group(1).lower() for m in re.finditer(r"^\s*[-*|]?\s*\**severity\**\s*[:|]\s*(\w+)", text, re.I | re.M)]
    for s in sev:
        if s not in rv["severities"]:
            f.error(f"unknown severity {s!r}")
    open_blocking = [s for s in sev if s in ("critical", "major")]
    if vm == "approved" and open_blocking:
        f.error(f"verdict 'approved' with {len(open_blocking)} open critical/major finding(s)")
    if vm in ("approved", "approved-with-conditions") and not re.search(r"independen", text, re.I):
        f.error("no statement of independent checks performed (separate context, reran checks, inspected diff)")
    if re.search(r"<[A-Za-z][^<>\n]{1,60}>", re.sub(r"`[^`\n]*`", "", text)):
        f.error("review report has unfilled placeholders")
    rc = f.report()
    if task:
        errs = [m for s_, m in f.items if s_ == "error"]
        ok = not errs and vm == "approved"       # only a clean 'approved' closes the REVIEW gate (GOV-05 section 10)
        why = "approved, report valid" if ok else (f"verdict {vm!r} does not close the gate" if not errs else f"{len(errs)} report error(s)")
        try:
            ref = file.resolve().relative_to(fw.parent.resolve()).as_posix()
        except ValueError:
            ref = str(file)
        rec = base_record(fw, task, "REVIEW", "manual-verification", "passed" if ok else "failed",
                          f"run_gates.py validate-review {ref}", why, command_id="validate_review", output_ref=ref)
        p = write_record(fw, rec, f"Review report `{ref}`; verdict: {vm}.\n" + "\n".join(errs), "review")
        print(f"{'PASSED' if ok else 'FAILED'} REVIEW -> {p.relative_to(fw.parent)}")
        return 0 if ok else 1
    return rc


# ---------------------------------------------------- summary and close-check
def collect(fw: Path, task: str):
    _, _, schema = load(fw)
    d = fw / "EVIDENCE" / task
    recs = []
    for p in sorted(d.rglob("*.md")) if d.is_dir() else []:
        try:
            r, _ = read_record(p)
        except ValueError:
            continue
        r["_path"] = p.relative_to(fw.parent).as_posix()
        r["_area"] = p.parent.name
        m = re.search(r"_\d{8}-\d{6}(?:-(\d+))?\.md$", p.name)       # same-second records are suffixed -1, -2 ...
        r["_seq"] = int(m.group(1)) if m and m.group(1) else 0
        recs.append(r)
    return recs


def closing_records(recs):
    """Baseline records describe the state BEFORE the change; they never close a gate."""
    return [r for r in recs if r["_area"] != "baseline"]


def latest_by_gate(recs):
    out = {}
    for r in sorted(recs, key=lambda r: (str(r.get("timestamp")), r.get("_seq", 0))):
        out[r["gate_id"]] = r
    return out


def stale_reason(fw: Path, r: dict) -> str | None:
    if r.get("source_fingerprint") and r["source_fingerprint"] != source_fingerprint(fw):
        return "source files changed since this evidence was produced"
    return None


def cmd_summary(fw: Path, task: str) -> int:
    recs = collect(fw, task)
    if not recs:
        print(f"no evidence for {task}")
        return 1
    print("| gate | status | label | commit | fresh | evidence |\n|---|---|---|---|---|---|")
    for g, r in sorted(latest_by_gate(closing_records(recs)).items()):
        sr = stale_reason(fw, r)
        print(f"| {g} | {r['status']} | {r['label']} | {str(r['commit'])[:10]} | {'no - ' + sr if sr else 'yes'} | {r['_path']} |")
    return 0


def body_of(fw: Path, r: dict) -> str:
    try:
        return read_record(fw.parent / r["_path"])[1]
    except (OSError, ValueError):
        return ""


def failing_ids(text: str) -> list[str]:
    return sorted(set(FAIL_ID.findall(text)))


def changed_paths(root: Path, base: str) -> set[str] | None:
    if cm.git(root, "rev-parse", "--verify", base + "^{commit}") is None:
        return None
    out = set((cm.git(root, "diff", "--name-only", base) or "").splitlines())
    return out | set((cm.git(root, "ls-files", "--others", "--exclude-standard") or "").splitlines())


def ui_changed(root: Path, prof: dict, base: str) -> bool:
    globs = [r["glob"] for r in prof["registry"]["component_rules"] if str(r.get("component", "")).startswith("ui-")]
    names = changed_paths(root, base) or set()
    return any(cr.glob_match(n, g) for n in names for g in globs)


def ui_gate(fw: Path, prof: dict, latest: dict, f: cm.Findings) -> None:
    vp = (prof.get("ui") or {}).get("viewports") or {}
    active = vp.get("active") if str(vp.get("status")) == "active" else None
    if not active:
        f.error("UI: ui.viewports is not defined by the owner (status "
                f"{vp.get('status')!r}), so UI validation is unavailable, never passed. The owner must set active viewports "
                "in project_profile.yml, then record a screenshot per viewport with record-ui")
        return
    for name, size in active.items():
        g = f"UI-{size}"
        r = latest.get(g)
        if r is None:
            f.error(f"{g}: no screenshot evidence for the {name} viewport (a UI change needs every configured viewport)")
        elif r["status"] != "passed":
            f.error(f"{g}: status is {r['status']} - not closable ({r['_path']})")
        elif stale_reason(fw, r):
            f.error(f"{g}: passed but stale: {stale_reason(fw, r)}")


def reg_gate(fw: Path, allrecs: list, latest: dict, f: cm.Findings) -> None:
    """Spec 11.3 step 4 / scenario 2: the regression test must be shown FAILING before the fix and passing after."""
    before = latest_by_gate([r for r in allrecs if r["_area"] == "baseline"]).get("REG")
    after = latest.get("REG")
    if after is None:
        f.error("REG: no post-fix record for the regression test")
    elif after["status"] != "passed":
        f.error(f"REG: status is {after['status']} - not closable ({after['_path']})")
    elif stale_reason(fw, after):
        f.error(f"REG: passed but stale: {stale_reason(fw, after)}")
    if before is None or before["status"] != "failed":
        f.error("REG: the regression test was never shown failing before the fix (no baseline record with status failed); "
                "a test that never failed proves nothing about the defect")
    elif after is not None and before.get("command") != after.get("command"):
        f.error("REG: the failing-before and passing-after records ran different commands")


def preexisting_only(fw: Path, latest: dict, f: cm.Findings) -> bool:
    """G1 failed, but REGRESSIONS shows every failure also failed on the baseline. Accept only if each one is
    recorded in KNOWN_ISSUES.md (spec 11.3: classify, never hide)."""
    reg = latest.get("REGRESSIONS")
    if reg is None or reg["status"] != "passed" or stale_reason(fw, reg):
        return False
    ids = [ln.split(":", 1)[1].strip() for ln in body_of(fw, reg).splitlines() if ln.startswith("pre-existing:")]
    if not ids:
        return False
    ki = fw / "MEMORY/KNOWN_ISSUES.md"
    known = ki.read_text(encoding="utf-8-sig") if ki.exists() else ""
    for i in ids:
        if i not in known:
            f.error(f"G1: pre-existing failure {i} is not recorded in MEMORY/KNOWN_ISSUES.md (classify it there; do not hide it)")
    return True


def cmd_close_check(fw: Path, task: str, require: list[str] | None, base: str | None = None) -> int:
    cp, prof, _ = load(fw)
    req = require or list(cp.get("default_gate_sequence") or []) + ["DOCS", "REVIEW"]
    # default_gate_sequence holds command ids; evidence gate ids default to the same id except G2/DOCS
    req = [GATE_ALIAS.get(x, x) for x in req]
    allrecs = collect(fw, task)
    latest = latest_by_gate(closing_records(allrecs))
    f = cm.Findings()
    if base:
        if changed_paths(fw.parent, base) is None:
            f.error(f"base revision {base!r} not found")
        elif ui_changed(fw.parent, prof, base) and "UI" not in req:
            req.append("UI")                      # a UI-affecting change cannot close without UI evidence (spec 11.1)
    for g in req:
        if g == "UI":
            ui_gate(fw, prof, latest, f)
            continue
        if g == "REG":
            reg_gate(fw, allrecs, latest, f)
            continue
        r = latest.get(g)
        if r is None:
            f.error(f"{g}: no evidence record (a gate that was not run is not passed)")
            continue
        if r["status"] == "not-applicable":
            if not r.get("verdict_rationale"):
                f.error(f"{g}: not-applicable without justification")
            continue
        if r["status"] != "passed":
            if g == "G1" and r["status"] == "failed" and preexisting_only(fw, latest, f):
                continue
            f.error(f"{g}: status is {r['status']} - not closable ({r['_path']})")
            continue
        sr = stale_reason(fw, r)
        if sr:
            f.error(f"{g}: passed but stale: {sr}")
    return f.report()


# ------------------------------------------------------------- regressions
def cmd_regressions(fw: Path, task: str) -> int:
    """Spec 11.3 / scenario 12: separate pre-existing failures from regressions using the baseline."""
    recs = collect(fw, task)
    before = latest_by_gate([r for r in recs if r["_area"] == "baseline"]).get("G1")
    after = latest_by_gate(closing_records(recs)).get("G1")
    lines, st, why = [], "failed", ""
    if after is None:
        why = "no post-change G1 record: run the tests first"
    elif after["status"] == "passed":
        fixed = failing_ids(body_of(fw, before)) if before else []
        lines = [f"fixed: {i}" for i in fixed]
        st, why = "passed", "post-change tests pass; no failures to classify"
    else:
        post_ids = failing_ids(body_of(fw, after))
        if not post_ids:
            why = "cannot classify: G1 failed but no FAILED/ERROR test ids could be read from its output"
        elif before is None:
            why = "no baseline G1 record: failures cannot be shown to pre-exist. Capture a baseline before editing"
            lines = [f"introduced: {i}" for i in post_ids]
        else:
            base_ids = set(failing_ids(body_of(fw, before)))
            intro = [i for i in post_ids if i not in base_ids]
            lines = ([f"pre-existing: {i}" for i in post_ids if i in base_ids] + [f"introduced: {i}" for i in intro]
                     + [f"fixed: {i}" for i in sorted(base_ids - set(post_ids))])
            st = "failed" if intro else "passed"
            why = f"{len(intro)} introduced, {len(post_ids) - len(intro)} pre-existing failure(s)"
    rec = base_record(fw, task, "REGRESSIONS", "automated-test", st, "run_gates.py regressions", why,
                      command_id="regressions", output_ref="inline below")
    body = "\n".join(lines) or "(none)"
    p = write_record(fw, rec, body, "validation")
    print(body)
    print(f"{st.upper()} REGRESSIONS: {why} -> {p.relative_to(fw.parent)}")
    return 0 if st == "passed" else 1


# ---------------------------------------------------------------- approvals
def manifest_names(text: str) -> set[str]:
    out = set()
    for ln in text.splitlines():
        m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", ln)
        if m and not ln.lstrip().startswith(("#", "-")):
            out.add(m.group(1).lower().replace("_", "-"))
    return out


def detect_operations(root: Path, prof: dict, base: str) -> dict[str, list[str]]:
    """High-risk operations visible in the change set (spec 12). Not every operation leaves a trace in Git
    (production deploys, data sent to an external service): those stay a reviewer's obligation."""
    ops: dict[str, list[str]] = {}
    add = lambda op, why: ops.setdefault(op, []).append(why)
    if cm.git(root, "merge-base", "--is-ancestor", base, "HEAD") is None:
        add("force_push_or_history_rewrite", f"{base[:10]} is not an ancestor of HEAD: history was rewritten")
    status = {}
    for ln in (cm.git(root, "diff", "--name-status", "-M", base) or "").splitlines():
        parts = ln.split("\t")
        status[parts[-1]] = parts[0][0]
    for n in (cm.git(root, "ls-files", "--others", "--exclude-standard") or "").splitlines():
        status.setdefault(n, "A")
    deleted = sorted(n for n, s in status.items() if s == "D")
    runtime = [x.rstrip("/") for x in (prof.get("paths") or {}).get("runtime_data", [])]
    hit = [n for n in deleted if any(n.startswith(r + "/") for r in runtime) or "backup" in n.lower()]
    if hit:
        add("delete_or_overwrite_user_data_or_backups", f"deleted runtime-data or backup file(s): {', '.join(hit[:3])}")
    if len(deleted) >= MASS_DELETE:
        add("delete_or_overwrite_user_data_or_backups", f"{len(deleted)} tracked files deleted (large set, threshold {MASS_DELETE})")
    manifest = (prof.get("stack") or {}).get("dependency_manifest")
    if manifest and (root / manifest).exists():
        old = manifest_names(cm.git(root, "show", f"{base}:{manifest}") or "")
        new = manifest_names((root / manifest).read_text(encoding="utf-8-sig")) - old
        if new:
            add("add_dependency_or_external_service", f"new package(s) in {manifest}: {', '.join(sorted(new))}")
    for n, s in status.items():
        b = n.rsplit("/", 1)[-1]
        if s == "A" and ((b == ".env" or b.startswith(".env.")) and not b.endswith((".example", ".sample"))
                         or b.endswith((".pem", ".key", ".p12")) or b.startswith("id_rsa") or b == "credentials.json"):
            add("change_credentials_or_access_or_consent", f"credential-like file added: {n}")
    for tag in (cm.git(root, "tag", "--points-at", "HEAD") or "").split():
        if re.match(r"^v?\d+(\.\d+)+", tag):
            add("production_deploy_or_release", f"release tag {tag} on HEAD")
    return ops


def cmd_approvals(fw: Path, base: str, task: str) -> int:
    """Each detected high-risk operation needs MEMORY/approvals/<task>/<operation>.md naming the owner message that
    approved it. This proves an approval was RECORDED and matches the operation; it cannot prove the owner wrote it,
    so the independent reviewer must confirm authenticity against the owner's actual message."""
    _, prof, _ = load(fw)
    root = fw.parent
    if cm.git(root, "rev-parse", "--verify", base + "^{commit}") is None:
        print(f"ERROR base revision {base!r} not found", file=sys.stderr)
        return 2
    ops = detect_operations(root, prof, base)
    problems, lines = [], []
    for op, why in sorted(ops.items()):
        lines.append(f"{op}: " + "; ".join(why))
        ap = fw / "MEMORY/approvals" / task / f"{op}.md"
        if not ap.is_file():
            problems.append(f"{op}: no approval record at .ai-engineering/MEMORY/approvals/{task}/{op}.md")
            continue
        try:
            rec, _ = read_record(ap)
        except (ValueError, OSError) as e:
            problems.append(f"{op}: approval record unreadable ({e})")
            continue
        if rec.get("operation") != op or rec.get("task_id") != task:
            problems.append(f"{op}: approval record is for {rec.get('operation')!r}/{rec.get('task_id')!r} (approval is specific and does not transfer)")
        for k in ("approved_by", "owner_message_ref", "scope"):
            if not rec.get(k):
                problems.append(f"{op}: approval record missing {k}")
    body = "\n".join(["detected: " + (", ".join(sorted(ops)) or "none")] + lines + [f"PROBLEM {x}" for x in problems])
    st = "failed" if problems else "passed"
    rec = base_record(fw, task, "APPROVALS", "automated-test", st, f"run_gates.py approvals --base {base}",
                      f"{len(ops)} high-risk operation(s) detected, {len(problems)} without a valid approval record",
                      command_id="approvals", output_ref="inline below")
    p = write_record(fw, rec, body, "validation")
    print(body)
    print(f"{st.upper()} APPROVALS -> {p.relative_to(root)}")
    return 1 if problems else 0


# ------------------------------------------------------------------ baseline
def cmd_baseline(fw: Path, task: str, timeout: int) -> int:
    """Spec 11.1: capture the state BEFORE any change. Never closes a gate; failures are
    recorded, then classified by the task (pre-existing / environmental / flaky / unknown)."""
    root = fw.parent
    cmd_run(fw, "tests_all", task, "baseline", "G1", None, timeout)
    status = cm.git(root, "status", "--short", "--untracked-files=all") or ""
    rec = base_record(fw, task, "BASELINE-GIT", "automated-test", "passed", "git status --short; git rev-parse HEAD",
                      "repository state captured", command_id="baseline_git", output_ref="inline below")
    p = write_record(fw, rec, f"HEAD {head(root)}\n```\n{status.rstrip() or '(clean)'}\n```", "baseline")
    print(f"recorded repository state -> {p.relative_to(root)}")
    print("Baseline captured. Classify every failure (pre-existing / introduced / environmental / flaky / unknown) in the task record.")
    return 0


# --------------------------------------------------------- protected paths
def cmd_protected(fw: Path, base: str, task: str) -> int:
    """Report-only: any change under owner-controlled paths fails the gate. There is no override
    flag by design; the owner resolves it (GOV-02 section 9, constitution section 10)."""
    _, prof, _ = load(fw)
    root = fw.parent
    prot = prof["protected"]
    prefixes = [x for x in (prot.get("project_governance") or []) + (prot.get("framework_rules") or [])]
    if cm.git(root, "rev-parse", "--verify", base + "^{commit}") is None:
        print(f"ERROR base revision {base!r} not found", file=sys.stderr)
        return 2
    changed = set((cm.git(root, "diff", "--name-only", base) or "").splitlines())
    changed |= set((cm.git(root, "ls-files", "--others", "--exclude-standard") or "").splitlines())
    hits = sorted(c for c in changed if any(c == x.rstrip("/") or c.startswith(x.rstrip("/") + "/") for x in prefixes))
    body = "\n".join(f"CHANGED {h}" for h in hits) if hits else "no protected path changed"
    st = "failed" if hits else "passed"
    rec = base_record(fw, task, "PROTECTED", "automated-test", st, f"run_gates.py protected --base {base}",
                      f"{len(hits)} protected path(s) changed", command_id="protected_paths", output_ref="inline below")
    p = write_record(fw, rec, body, "validation")
    print(body)
    print(f"{st.upper()} PROTECTED -> {p.relative_to(root)}")
    return 1 if hits else 0


# -------------------------------------------------------------- UI evidence
def cmd_record_ui(fw: Path, a) -> int:
    _, prof, _ = load(fw)
    root = fw.parent
    approved = str((prof.get("ui") or {}).get("browser_automation", "unavailable"))
    tool = a.tool
    if tool != "manual" and (approved in ("unavailable", "None") or tool != approved):
        print(f"ERROR tool {tool!r} is not project-approved (profile ui.browser_automation = {approved!r}). "
              "Use --tool manual for a person-captured screenshot, or have the owner approve a tool in project_profile.yml.",
              file=sys.stderr)
        return 2
    if not re.fullmatch(r"\d{3,5}x\d{3,5}", a.viewport):
        print("ERROR --viewport must look like 1920x1080", file=sys.stderr)
        return 2
    img = Path(a.image)
    if not img.is_file():
        print(f"ERROR screenshot {img} not found", file=sys.stderr)
        return 2
    d = fw / "EVIDENCE" / a.task / "browser"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{safe(a.viewport)}_{safe(a.workflow)}_{now().strftime('%Y%m%d-%H%M%S')}{img.suffix.lower()}"
    dest.write_bytes(img.read_bytes())
    extra = {"viewport": a.viewport, "image_path": dest.relative_to(root).as_posix(), "workflow": a.workflow,
             "tool": tool, "url": a.url or ""}
    if a.console_log:
        cl = Path(a.console_log)
        if cl.is_file():
            clean, red = redact(cl.read_text(encoding="utf-8", errors="replace"))
            cp = dest.with_suffix(".console.txt")
            cp.write_text(clean, encoding="utf-8")
            extra.update(console_log=cp.relative_to(root).as_posix(), redactions=red)
    rec = base_record(fw, a.task, f"UI-{a.viewport}", "screenshot-evidence", a.result, a.command or f"{tool}: {a.workflow}",
                      a.note or f"workflow '{a.workflow}' at {a.viewport} judged {a.result} by the recording agent",
                      command_id="record_ui", output_ref=extra["image_path"], **extra)
    p = write_record(fw, rec, f"Workflow: {a.workflow}\nViewport: {a.viewport}\nTool: {tool}\nScreenshot: `{extra['image_path']}`\n"
                     "A screenshot proves the UI state shown, not that the workflow is correct beyond what was inspected.", "browser")
    print(f"{a.result.upper()} UI-{a.viewport} -> {p.relative_to(root)}")
    return 0 if a.result == "passed" else 1


# ----------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):               # a legacy console (cp1252) must not crash on a non-ASCII file name
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--framework-dir", type=Path, default=FW)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("command_id")
    r.add_argument("--task", required=True)
    r.add_argument("--area", default="validation", choices=["baseline", "validation", "browser", "review"])
    r.add_argument("--gate")
    r.add_argument("--label")
    r.add_argument("--timeout", type=int, default=1800)
    m = sub.add_parser("mustkeep")
    m.add_argument("--base", required=True)
    m.add_argument("--task", required=True)
    d = sub.add_parser("docs-gate")
    d.add_argument("--task", required=True)
    v = sub.add_parser("validate-evidence")
    v.add_argument("paths", nargs="+")
    rv = sub.add_parser("validate-review")
    rv.add_argument("file", type=Path)
    rv.add_argument("--task", help="also write the REVIEW gate evidence record")
    b = sub.add_parser("baseline")
    b.add_argument("--task", required=True)
    b.add_argument("--timeout", type=int, default=1800)
    pr = sub.add_parser("protected")
    pr.add_argument("--base", required=True)
    pr.add_argument("--task", required=True)
    u = sub.add_parser("record-ui")
    u.add_argument("--task", required=True)
    u.add_argument("--viewport", required=True)
    u.add_argument("--image", required=True)
    u.add_argument("--workflow", required=True)
    u.add_argument("--result", required=True, choices=["passed", "failed"])
    u.add_argument("--tool", required=True)
    u.add_argument("--url")
    u.add_argument("--console-log")
    u.add_argument("--command")
    u.add_argument("--note")
    s = sub.add_parser("summary")
    s.add_argument("--task", required=True)
    c = sub.add_parser("close-check")
    c.add_argument("--task", required=True)
    c.add_argument("--require")
    c.add_argument("--base", help="revision the task branched from; a UI-affecting change then requires UI evidence")
    rg_ = sub.add_parser("regressions")
    rg_.add_argument("--task", required=True)
    ap_ = sub.add_parser("approvals")
    ap_.add_argument("--base", required=True)
    ap_.add_argument("--task", required=True)
    a = ap.parse_args(argv)
    fw = a.framework_dir.resolve()
    try:
        if a.cmd == "run":
            return cmd_run(fw, a.command_id, a.task, a.area, a.gate, a.label, a.timeout)
        if a.cmd == "mustkeep":
            return cmd_mustkeep(fw, a.base, a.task)[0]
        if a.cmd == "docs-gate":
            return cmd_docs_gate(fw, a.task)
        if a.cmd == "validate-evidence":
            return cmd_validate_evidence(fw, a.paths)
        if a.cmd == "validate-review":
            return cmd_validate_review(fw, a.file, a.task)
        if a.cmd == "baseline":
            return cmd_baseline(fw, a.task, a.timeout)
        if a.cmd == "protected":
            return cmd_protected(fw, a.base, a.task)
        if a.cmd == "record-ui":
            return cmd_record_ui(fw, a)
        if a.cmd == "summary":
            return cmd_summary(fw, a.task)
        if a.cmd == "close-check":
            return cmd_close_check(fw, a.task, a.require.split(",") if a.require else None, a.base)
        if a.cmd == "regressions":
            return cmd_regressions(fw, a.task)
        if a.cmd == "approvals":
            return cmd_approvals(fw, a.base, a.task)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
