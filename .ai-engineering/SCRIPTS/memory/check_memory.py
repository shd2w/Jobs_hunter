#!/usr/bin/env python3
"""Validate AI Engineering Framework memory records (spec 9, roadmap Phase B).

    python .ai-engineering/SCRIPTS/memory/check_memory.py state
    python .ai-engineering/SCRIPTS/memory/check_memory.py handoff <file> [--against-git]
    python .ai-engineering/SCRIPTS/memory/check_memory.py start --task WP-pp-nn   # may this work package start?

Standard library only. Exit codes: 0 valid, 1 findings of severity error
(or warn with --strict), 2 usage/environment error. It checks that records are
complete, internally consistent, free of placeholders/secrets and agree with
Git. It does NOT prove the work is correct; a resuming agent must still re-run
the checkpoint tests.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

FW = Path(__file__).resolve().parents[2]          # .ai-engineering
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9_-]{20,}", "API key (sk-...)"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"(?i)bearer\s+[A-Za-z0-9._-]{20,}", "bearer token"),
    (r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9/+_-]{16,}", "credential assignment"),
    (r"\b\d{9}:[A-Za-z0-9_-]{30,}\b", "Telegram bot token"),
]


# ---------------------------------------------------------------- YAML subset
def _scalar(s: str):
    s = s.strip()
    if s in ("null", "~", ""):
        return None
    if s in ("true", "false"):
        return s == "true"
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        return inner.replace("\\\\", "\\").replace('\\"', '"') if s[0] == '"' else inner.replace("''", "'")
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in _split_top(inner)] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for part in _split_top(s[1:-1]):
            if ":" in part:
                k, v = part.split(":", 1)
                out[k.strip().strip("\"'")] = _scalar(v)
        return out
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _split_top(s: str):
    parts, depth, cur, q = [], 0, "", ""
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = ""
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _strip_comment(line: str) -> str:
    q = ""
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = ""
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def parse_yaml_subset(text: str):
    """Block maps, block lists of scalars, flow lists/maps, scalars, comments.
    Enough for the framework's own state files; raises ValueError otherwise."""
    rows = []
    lines = text.splitlines()
    n = 0
    while n < len(lines):
        raw = lines[n]
        n += 1
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip(" "))
        m = re.match(r"(.*:)\s+([>|])-?$", line.strip())
        if m:  # block scalar: gather deeper-indented lines
            body = []
            while n < len(lines) and (not lines[n].strip() or len(lines[n]) - len(lines[n].lstrip(" ")) > ind):
                body.append(lines[n].strip())
                n += 1
            joined = (" " if m.group(2) == ">" else "\n").join(x for x in body if x)
            rows.append((ind, m.group(1) + ' "' + joined.replace("\\", "\\\\").replace('"', '\\"') + '"'))
            continue
        rows.append((ind, line.strip()))

    def block(i, indent):
        if rows[i][1].startswith("- "):
            out = []
            while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
                rest = rows[i][1][2:]
                if re.match(r"[A-Za-z0-9_.-]+:(\s|$)", rest):   # list of block maps
                    rows[i] = (indent + 2, rest)
                    item, i = block(i, indent + 2)
                    out.append(item)
                else:
                    out.append(_scalar(rest))
                    i += 1
            return out, i
        out = {}
        while i < len(rows) and rows[i][0] == indent:
            m = re.match(r"([^:]+):(?:\s+(.*))?$", rows[i][1])
            if not m:
                raise ValueError(f"cannot parse line: {rows[i][1]!r}")
            key, val = m.group(1).strip().strip("\"'"), m.group(2)
            i += 1
            if val is None or val == "":
                if i < len(rows) and rows[i][0] > indent:
                    out[key], i = block(i, rows[i][0])
                else:
                    out[key] = None
            else:
                out[key] = _scalar(val)
        if i < len(rows) and rows[i][0] > indent:
            raise ValueError(f"unexpected indentation at {rows[i][1]!r}")
        return out, i

    if not rows:
        return {}
    value, _ = block(0, rows[0][0])
    return value


def load_yaml(path: Path):
    """Use PyYAML when installed (it is a project dependency); otherwise the
    stdlib subset parser, so the framework has no hard runtime dependency."""
    text = path.read_text(encoding="utf-8-sig")
    try:
        import yaml  # type: ignore
    except ImportError:
        return parse_yaml_subset(text)
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"{path.name}: {e}") from e


# ------------------------------------------------------------------- helpers
class Findings:
    def __init__(self):
        self.items = []

    def error(self, msg):
        self.items.append(("error", msg))

    def warn(self, msg):
        self.items.append(("warn", msg))

    def report(self, strict=False) -> int:
        for sev, msg in self.items:
            print(f"{sev.upper():5} {msg}")
        bad = [s for s, _ in self.items if s == "error" or (strict and s == "warn")]
        print(f"{'FAIL' if bad else 'OK'}: {len(self.items)} finding(s)")
        return 1 if bad else 0


def git(root: Path, *args) -> str | None:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(root), *args], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def repo_root(fw: Path) -> Path:
    return fw.parent


def doc_by_role(root: Path, contract: dict, role: str, default: str) -> Path:
    """Path of the project document with this role in the contract map (a project names its own task board and
    decision log there); falls back to the JobHunter location."""
    for d in (contract or {}).get("documents_read") or []:
        if d.get("role") == role and d.get("path"):
            return root / d["path"]
    return root / default


def known_wp_ids(root: Path, contract: dict) -> set[str] | None:
    src = doc_by_role(root, contract, "task_source", "docs/governance/04_work_packages.md")
    if not src.exists():
        return None
    return set(re.findall(r"WP-\d{2}-\d{2}", src.read_text(encoding="utf-8")))


def task_id_ok(task_id: str, schema: dict) -> bool:
    return any(re.match(p, task_id) for p in schema["handoff"]["task_id_patterns"])


def check_task_ref(task_id, root, wp_ids, schema, f: Findings, where):
    if not task_id_ok(task_id, schema):
        f.error(f"{where}: task id {task_id!r} matches no allowed pattern")
    elif task_id.startswith("WP-") and wp_ids is not None and task_id not in wp_ids:
        f.error(f"{where}: stale task reference {task_id} - not in docs/governance/04_work_packages.md")


# ---------------------------------------------------------------- state check
def check_state(fw: Path, strict=False) -> Findings:
    f = Findings()
    root = repo_root(fw)
    schema = load_yaml(fw / "QUALITY/checkpoint_schema.yml")
    sp = fw / "MEMORY/PROJECT_STATE.yml"
    if not sp.exists():
        f.error("MEMORY/PROJECT_STATE.yml missing")
        return f
    try:
        st = load_yaml(sp)
    except ValueError as e:
        f.error(f"PROJECT_STATE.yml unparseable: {e}")
        return f
    for k in schema["project_state"]["required_keys"]:
        if k not in st:
            f.error(f"PROJECT_STATE.yml missing required key {k!r}")
    lv = st.get("last_verified_checkpoint")
    if isinstance(lv, dict):
        for k in schema["project_state"]["last_verified_checkpoint_keys"]:
            if k not in lv:
                f.error(f"last_verified_checkpoint missing {k!r}")
    else:
        f.error("last_verified_checkpoint must be a map")

    contract = load_yaml(fw / "CONFIG/project_contract_map.yml")
    wp_ids = known_wp_ids(root, contract)

    # indexes exist
    for name, rel in (st.get("indexes") or {}).items():
        if not (root / rel).exists():
            f.error(f"indexes.{name}: {rel} does not exist")

    # active task consistency
    active = st.get("active_task")
    ct = fw / "MEMORY/CURRENT_TASK.md"
    ct_text = ct.read_text(encoding="utf-8") if ct.exists() else ""
    m = re.search(r"^\*\*Task:\*\*\s*(.+)$", ct_text, re.M)
    ct_task = m.group(1).strip() if m else None
    if active:
        check_task_ref(active, root, wp_ids, schema, f, "PROJECT_STATE.active_task")
        if not ct_task or not ct_task.startswith(str(active)):
            f.error(f"active_task {active} but CURRENT_TASK.md says {ct_task!r}")
        statuses = (contract.get("status_mapping") or {}).get("project_statuses", [])
        if st.get("task_status") not in statuses:
            f.error(f"task_status {st.get('task_status')!r} is not a project status {statuses}")
    else:
        if ct_task and not ct_task.lower().startswith("none"):
            f.error(f"active_task is null but CURRENT_TASK.md names {ct_task!r}")
        if st.get("task_status") not in (None, "n/a"):
            f.error("active_task is null but task_status is set")

    # handoff directories reference real tasks
    hd = fw / "MEMORY/handoffs"
    if hd.is_dir():
        for d in sorted(p for p in hd.iterdir() if p.is_dir()):
            check_task_ref(d.name, root, wp_ids, schema, f, f"handoffs/{d.name}")

    # suite revision read
    for d in contract.get("documents_read", []):
        p = root / d["path"]
        if not p.exists():
            f.error(f"contract map: {d['path']} missing")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != d["sha256"]:
            f.error(f"contract map: {d['id']} ({d['path']}) changed since it was read; owner must confirm")
    rev = (st.get("authoritative_documents") or {}).get("decision_log_revision_read", "")
    gov02 = next((d for d in contract.get("documents_read", []) if d["id"] == "GOV-02"), None)
    if gov02 and gov02["sha256"] not in str(rev):
        f.error("authoritative_documents.decision_log_revision_read does not match GOV-02 sha256 in the contract map")

    # git agreement
    head = git(root, "rev-parse", "HEAD")
    if head is None:
        f.warn("git unavailable or not a repository: branch/commit checks skipped")
    else:
        head = head.strip()
        branch = (git(root, "branch", "--show-current") or "").strip()
        if st.get("branch") != branch:
            f.warn(f"state branch {st.get('branch')!r} != current branch {branch!r}")
        sh = str(st.get("head_commit"))
        if git(root, "cat-file", "-e", f"{sh}^{{commit}}") is None:
            f.error(f"state head_commit {sh} is not a commit in this repository")
        elif sh != head:
            f.warn(f"state head_commit {sh[:10]} != HEAD {head[:10]} (state is behind)")
        lc = str((lv or {}).get("commit")) if isinstance(lv, dict) else ""
        if lc and git(root, "cat-file", "-e", f"{lc}^{{commit}}") is None:
            f.error(f"last_verified_checkpoint.commit {lc} not found")
    return f


# -------------------------------------------------------------- handoff check
def sections(text: str):
    """{heading: body} for '## ' headings, ignoring fenced code for heading detection."""
    out, cur, buf, fence = {}, None, [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = line[3:].strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def bold_fields(body: str):
    return {m.group(1).strip(): m.group(2).strip() for m in re.finditer(r"^- \*\*(.+?):\*\*\s*(.*)$", body, re.M)}


def claimed_paths(body: str):
    paths = []
    for line in body.splitlines():
        m = re.match(r"^- `?([^`:\s][^`:]*?)`?:", line)
        if m and not m.group(1).startswith("<"):
            paths.append(m.group(1).strip())
    return paths


def porcelain(root: Path):
    out = git(root, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return None
    res = {}
    for line in out.splitlines():
        res[line[3:].strip().strip('"')] = line[:2]
    return res


def check_handoff(fw: Path, hf: Path, against_git=False, strict=False) -> Findings:
    f = Findings()
    root = repo_root(fw)
    schema = load_yaml(fw / "QUALITY/checkpoint_schema.yml")
    contract = load_yaml(fw / "CONFIG/project_contract_map.yml")
    wp_ids = known_wp_ids(root, contract)
    text = hf.read_text(encoding="utf-8")
    secs = sections(text)
    hs = schema["handoff"]

    for name in hs["required_sections"]:
        if name not in secs:
            f.error(f"missing section '## {name}'")
        elif not secs[name].strip():
            f.error(f"section '## {name}' is empty")
    for sec, keys in hs["required_fields"].items():
        fields = bold_fields(secs.get(sec, ""))
        for k in keys:
            if not fields.get(k):
                f.error(f"{sec}: field '{k}' missing or empty")

    # placeholders (ignore inline code)
    no_code = re.sub(r"`[^`\n]*`", "", text)
    for m in re.finditer(r"<[A-Za-z][^<>\n]{1,80}>", no_code):
        f.error(f"unfilled placeholder {m.group(0)!r}")
        break
    # secrets
    for pat, label in SECRET_PATTERNS:
        if re.search(pat, text):
            f.error(f"possible secret in handoff: {label}")

    ident = bold_fields(secs.get("Identification", ""))
    wp = ident.get("Work package", "")
    if wp:
        check_task_ref(wp, root, wp_ids, schema, f, "Identification.Work package")
    parent = hf.parent.name
    if wp and parent != wp:
        f.error(f"handoff stored under {parent!r} but Work package is {wp!r}")
    if not re.match(r"^\d{8}-\d{6}_[A-Za-z0-9._-]+\.md$", hf.name):
        f.warn(f"file name {hf.name!r} does not follow <YYYYMMDD-HHmmss>_<agent-label>.md")

    repo = bold_fields(secs.get("Repository state", ""))
    sha = re.sub(r"[^0-9a-f]", "", repo.get("HEAD commit", "").lower())
    if repo.get("HEAD commit") and not (7 <= len(sha) <= 40):
        f.error("HEAD commit is not a SHA")
    elif sha and git(root, "cat-file", "-e", f"{sha}^{{commit}}") is None and git(root, "rev-parse", "HEAD") is not None:
        f.error(f"HEAD commit {sha[:10]} does not exist in this repository")

    # gate table
    gate_sec = secs.get("Validation state", "")
    for row in re.findall(r"^\|(.+)\|\s*$", gate_sec, re.M):
        cells = [c.strip() for c in row.split("|")]
        if len(cells) < 3 or cells[0].lower() in ("gate",) or set(cells[0]) <= set("-: "):
            continue
        status, ev = cells[1], cells[2]
        if status not in hs["gate_statuses"]:
            f.error(f"gate {cells[0]!r}: status {status!r} not in {hs['gate_statuses']}")
        if status == "passed" and (not ev or ev.lower() in ("n/a", "none", "-")):
            f.error(f"gate {cells[0]!r} marked passed without evidence path")

    # evidence paths exist
    for m in re.finditer(r"`?((?:\.ai-engineering/)?EVIDENCE/[^\s`|)]+)`?", text):
        rel = m.group(1)
        p = root / (rel if rel.startswith(".ai-engineering/") else f".ai-engineering/{rel}")
        if not p.exists():
            f.error(f"evidence path does not exist: {rel}")

    if not re.search(r"^\s*1\.\s+\S", secs.get("Exact next actions", ""), re.M):
        f.error("Exact next actions has no numbered action")

    if against_git:
        compare_git(root, secs, repo, sha, f)
    return f


def compare_git(root, secs, repo, sha, f: Findings):
    head = git(root, "rev-parse", "HEAD")
    if head is None:
        f.error("--against-git requested but git is unavailable")
        return
    head = head.strip()
    branch = (git(root, "branch", "--show-current") or "").strip()
    if repo.get("Branch") and repo["Branch"] != branch:
        f.error(f"handoff branch {repo['Branch']!r} != actual branch {branch!r}")
    if sha and not head.startswith(sha):
        anc = git(root, "merge-base", "--is-ancestor", sha, head)
        f.error(f"handoff HEAD {sha[:10]} != actual HEAD {head[:10]}" + (" (handoff is behind: new commits exist)" if anc is not None else " (not an ancestor)"))
    status = porcelain(root)
    if status is None:
        f.error("cannot read git status")
        return
    body = secs.get("File changes", "")
    parts = re.split(r"^### ", body, flags=re.M)
    claimed_dirty, claimed_commit = set(), set()
    for part in parts:
        title = part.split("\n", 1)[0].strip()
        paths = claimed_paths(part.split("\n", 1)[1] if "\n" in part else "")
        if title.startswith("Uncommitted") or title.startswith("Untracked"):
            claimed_dirty.update(paths)
        elif title.startswith("Committed"):
            claimed_commit.update(paths)
    ignore = lambda p: p.startswith(".ai-engineering/MEMORY/handoffs/")
    actual = {p for p in status if not ignore(p)}
    norm = lambda s: {p.rstrip("/") for p in s}
    claimed_dirty = norm(claimed_dirty)
    for p in sorted(claimed_dirty):
        if not any(a == p or a.startswith(p + "/") for a in actual):
            f.error(f"handoff claims uncommitted/untracked {p!r} but git status does not show it")
    for a in sorted(actual):
        if not any(a == c or a.startswith(c + "/") for c in claimed_dirty):
            f.error(f"unexpected change not in handoff: {a!r} ({status[a].strip() or '?'})")
    for p in sorted(claimed_commit):
        if not (root / p).exists() and git(root, "log", "-1", "--", p):
            continue  # deleted in a commit: acceptable
        if not (root / p).exists():
            f.error(f"handoff lists committed file {p!r} which does not exist")


# ------------------------------------------------------------------ task start
STARTABLE = ("ready_for_implementation", "in_progress")        # GOV-05 section 10
WP_ID = r"WP-\d{2}-\d{2}"


def wp_table(root: Path, contract: dict) -> dict | None:
    """Rows of the project's task board (contract map role task_source): id -> {deps, status}."""
    src = doc_by_role(root, contract, "task_source", "docs/governance/04_work_packages.md")
    if not src.exists():
        return None
    rows = {}
    for ln in src.read_text(encoding="utf-8-sig").splitlines():
        if not ln.startswith("| WP-"):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) >= 9 and re.fullmatch(WP_ID, c[0]):
            rows[c[0]] = {"deps": re.findall(WP_ID, c[4]), "status": c[-1]}
    return rows


def pcd_table(root: Path, contract: dict) -> list[dict]:
    """The decision log's 'PCD handling (interim defaults)' table (contract map role decision_authority)."""
    src = doc_by_role(root, contract, "decision_authority", "docs/governance/02_decision_log_and_scope.md")
    if not src.exists():
        return []
    out = []
    for ln in src.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"^\|\s*(PCD-\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$", ln)
        if m and ("blocking" in m.group(2)):
            out.append({"id": m.group(1), "mode": m.group(2), "wps": re.findall(WP_ID, m.group(3)), "default": m.group(4)})
    return out


def check_start(fw: Path, task: str) -> Findings:
    """May `task` start? Status, dependencies and every pending decision that references it (GOV-02 section 3)."""
    f = Findings()
    root = repo_root(fw)
    contract = load_yaml(fw / "CONFIG/project_contract_map.yml")
    rows = wp_table(root, contract)
    if rows is None:
        f.error("the project's task board (contract map role task_source) was not found: cannot confirm the task is "
                "authorised. Without one this gate fails closed; the owner must provide a work-package table")
        return f
    row = rows.get(task)
    if row is None:
        f.error(f"{task} is not in the project's task board (propose a work package; do not invent one)")
        return f
    if not any(row["status"].startswith(s) for s in STARTABLE):
        f.error(f"{task} status is {row['status']!r}; it may start only from {STARTABLE} (blocked work is not started)")
    for d in row["deps"]:
        ds = (rows.get(d) or {}).get("status", "unknown")
        if ds != "merged":
            f.error(f"{task} depends on {d}, whose status is {ds!r}, not 'merged'")
    ct = fw / "MEMORY/CURRENT_TASK.md"
    ct_text = ct.read_text(encoding="utf-8-sig") if ct.exists() else ""
    names_task = re.search(r"\*\*Task:\*\*[^\n]*" + re.escape(task), ct_text) is not None
    for pcd in pcd_table(root, contract):
        if task not in pcd["wps"]:
            continue
        blocking = pcd["mode"].lower().startswith("blocking")
        key = "PCD out of scope" if blocking else "PCD impact"
        recorded = names_task and re.search(rf"^\s*{key}:[^\n]*\b{pcd['id']}\b", ct_text, re.M) is not None
        if not recorded:
            if blocking:
                f.error(f"{pcd['id']} blocks the guarded behaviour of {task}: CURRENT_TASK.md must declare it out of scope "
                        f"with a line '{key}: {pcd['id']} ...' (the agent may not decide it)")
            else:
                f.error(f"{pcd['id']} (non-blocking) applies to {task}: record the interim default in CURRENT_TASK.md with a "
                        f"line '{key}: {pcd['id']} ...' (interim default in force: {pcd['default']})")
    return f


# ------------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--framework-dir", type=Path, default=FW)
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("state")
    st = sub.add_parser("start", help="may this work package start? (status, dependencies, pending decisions)")
    st.add_argument("--task", required=True)
    h = sub.add_parser("handoff")
    h.add_argument("file", type=Path)
    h.add_argument("--against-git", action="store_true")
    a = ap.parse_args(argv)
    fw = a.framework_dir.resolve()
    try:
        if a.cmd == "state":
            findings = check_state(fw)
        elif a.cmd == "start":
            findings = check_start(fw, a.task)
        else:
            findings = check_handoff(fw, a.file.resolve(), a.against_git)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR cannot run check: {e}", file=sys.stderr)
        return 2
    return findings.report(a.strict)


if __name__ == "__main__":
    sys.exit(main())
