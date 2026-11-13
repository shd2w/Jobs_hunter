#!/usr/bin/env python3
"""Documentation registry scanner and stale-entry checker (spec 10, roadmap Phase C).

    check_registry.py check  [--since REV] [--strict]
    check_registry.py scan   [--write]            # add skeleton entries for unregistered files
    check_registry.py refresh PATH [PATH ...]     # re-hash entries after you confirmed them
    check_registry.py trace  PATH|F-nn|WP-nn-nn

Standard library only (reads YAML through SCRIPTS/memory/check_memory.py). Exit codes:
0 ok, 1 findings, 2 usage/environment error. `scan` writes only generated-unreviewed
skeletons and never overwrites an existing entry.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import re
import subprocess
import sys
from pathlib import Path

FW = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FW / "SCRIPTS" / "memory"))
import check_memory as cm  # noqa: E402

ROOT = FW.parent


# ------------------------------------------------------------------ YAML out
def _q(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    import json
    return json.dumps(str(v), ensure_ascii=False)


def dump_entry(e: dict) -> str:
    lines = []
    first = True
    for k, v in e.items():
        pre = "  - " if first else "    "
        first = False
        if isinstance(v, list):
            lines.append(f"{pre}{k}: [" + ", ".join(_q(x) for x in v) + "]")
        else:
            lines.append(f"{pre}{k}: {_q(v)}")
    return "\n".join(lines)


def write_registry(path: Path, header: str, key: str, entries: list):
    body = "\n".join(dump_entry(e) for e in entries)
    path.write_text(f"{header}\n{key}:\n{body}\n", encoding="utf-8")


# ------------------------------------------------------------------ repo scan
def sha(p: Path) -> str:
    """Content hash that ignores line endings of text files: a Windows checkout with CRLF must not make every
    registry entry look stale. Binary files (any NUL byte) are hashed as they are."""
    raw = p.read_bytes()
    if b"\0" not in raw:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def glob_match(rel: str, pat: str) -> bool:
    if pat.endswith("/**"):
        return rel.startswith(pat[:-3] + "/") or fnmatch.fnmatch(rel, pat)
    if pat.startswith("**/"):
        return fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat[3:]) or ("/" + pat[3:]) in ("/" + rel) or any(
            fnmatch.fnmatch(part, pat[3:].rstrip("/*")) for part in rel.split("/"))
    return fnmatch.fnmatch(rel, pat)


def excluded(rel: str, rules: list) -> bool:
    for pat in rules:
        if pat.startswith("**/") and pat.endswith("/**"):
            if pat[3:-3] in rel.split("/")[:-1]:
                return True
        elif glob_match(rel, pat):
            return True
    return False


def maintained_files(root: Path, profile: dict) -> list[str]:
    rules = profile["registry"]["exclude_globs"]
    out = cm.git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    if out is None:  # no git: walk, honouring the profile exclusions only
        files = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    else:
        files = [x for x in out.splitlines() if (root / x).is_file()]
    return sorted(f for f in files if not excluded(f, rules))


def rule_for(rel: str, profile: dict) -> dict:
    for r in profile["registry"]["component_rules"]:
        if glob_match(rel, r["glob"]) or (r["glob"] == "*" and "/" not in rel):
            return r
    return profile["registry"]["component_rules"][-1]


# -------------------------------------------------------------- fact deriving
def py_facts(p: Path, root: Path) -> dict:
    src = p.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return {"purpose": None, "interfaces": [], "internal_imports": [], "side_effects": ["none-detected"]}
    doc = ast.get_docstring(tree) or ""
    purpose = " ".join(doc.split("\n\n")[0].split()) or None
    ifaces = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith("_")]
    tops = {x.name.split(".")[0] for x in root.glob("*.py")} | {d.name for d in root.iterdir() if d.is_dir() and (d / "__init__.py").exists()}
    tops = {t.removesuffix(".py") for t in tops}
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in tops:
                    imports.add(a.name)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0 and n.module.split(".")[0] in tops:
            imports.add(n.module)
    eff = []
    low = src
    if re.search(r"^\s*(import|from)\s+(httpx|requests|urllib|socket|jobspy|http\.client)\b", low, re.M) or "make_server" in low:
        eff.append("network")
    if re.search(r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]b?['\"]|\.mkdir\(|os\.(remove|rename|replace)|shutil\.|\.unlink\(|json\.dump\(|to_excel|\.save\(", low):
        eff.append("filesystem-write")
    if re.search(r"\bsubprocess\b", low):
        eff.append("subprocess")
    if re.search(r"os\.environ|getenv|load_dotenv", low):
        eff.append("environment")
    return {"purpose": purpose, "interfaces": ifaces[:12], "internal_imports": sorted(imports), "side_effects": eff or ["none-detected"]}


def other_purpose(p: Path) -> str | None:
    t = p.read_text(encoding="utf-8", errors="replace")
    suf = p.suffix.lower()
    if suf == ".md":
        m = re.search(r"^#\s+(.+)$", t, re.M)
        return m.group(1).strip() if m else None
    if suf in (".yml", ".yaml"):
        m = re.match(r"\s*#\s*(.+)", t)
        return m.group(1).strip() if m else None
    if suf in (".js", ".css"):
        m = re.match(r"\s*/\*+\s*(.+?)\s*\*/", t, re.S) or re.match(r"\s*//\s*(.+)", t)
        return " ".join(m.group(1).split()) if m else None
    if suf == ".html":
        m = re.search(r"<title>(.*?)</title>", t, re.S)
        return f"HTML page: {m.group(1).strip()}" if m else None
    return None


def test_refs(root: Path) -> dict[str, list[str]]:
    """module path -> tests that import it (AST, top-level + nested)."""
    refs: dict[str, set[str]] = {}
    for t in sorted((root / "tests").glob("test_*.py")) if (root / "tests").is_dir() else []:
        try:
            tree = ast.parse(t.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module] + [f"{n.module}.{a.name}" for a in n.names]
            for m in mods:
                for cand in (m.replace(".", "/") + ".py", m.replace(".", "/") + "/__init__.py"):
                    if (root / cand).exists():
                        refs.setdefault(cand, set()).add(t.relative_to(root).as_posix())
    return {k: sorted(v) for k, v in refs.items()}


def skeleton(rel: str, root: Path, profile: dict, trefs: dict) -> dict:
    p = root / rel
    rule = rule_for(rel, profile)
    if rel.endswith(".py"):
        facts = py_facts(p, root)
    else:
        facts = {"purpose": other_purpose(p), "interfaces": [], "internal_imports": [], "side_effects": []}
    e = {
        "path": rel,
        "type": (p.suffix.lstrip(".") or p.name.lower()),
        "purpose": facts["purpose"],
        "component": rule["component"],
        "classification": profile["registry"]["default_classification"],
        "status": "active",
        "provenance": "generated-unreviewed",
        "entry_sha256": sha(p),
        "untrusted_input": bool(rule.get("untrusted_input")),
    }
    for k in ("interfaces", "internal_imports", "side_effects"):
        if facts[k]:
            e[k] = facts[k]
    if trefs.get(rel):
        e["tests"] = trefs[rel]
    return e


# ------------------------------------------------------------------- loading
def load_all(fw: Path):
    root = fw.parent
    schema = cm.load_yaml(fw / "QUALITY/registry_schema.yml")
    profile = cm.load_yaml(fw / "CONFIG/project_profile.yml")
    fr = fw / "DOCUMENTATION/FILE_REGISTRY.yml"
    fe = fw / "DOCUMENTATION/FEATURE_REGISTRY.yml"
    files = (cm.load_yaml(fr) or {}).get("files") or [] if fr.exists() else None
    feats = (cm.load_yaml(fe) or {}).get("features") or [] if fe.exists() else None
    return root, schema, profile, files, feats


FILE_HEADER = ("# File registry (spec 10.1). One entry per maintained file. Validated by SCRIPTS/documentation/check_registry.py.\n"
               "# provenance generated-unreviewed = scanner-derived facts; reviewed = confirmed by a reader. See QUALITY/registry_schema.yml.")


def cmd_scan(fw: Path, write: bool) -> int:
    root, schema, profile, files, _ = load_all(fw)
    files = files or []
    have = {e["path"] for e in files}
    trefs = test_refs(root)
    new = [skeleton(r, root, profile, trefs) for r in maintained_files(root, profile) if r not in have]
    for e in new:
        print(f"NEW   {e['path']}  purpose={'<missing>' if not e['purpose'] else 'derived'}")
    if write and new:
        merged = sorted(files + new, key=lambda e: e["path"])
        write_registry(fw / "DOCUMENTATION/FILE_REGISTRY.yml", FILE_HEADER, "files", merged)
        print(f"wrote {len(new)} skeleton entries; fill null purposes and review before relying on them")
    print(f"{len(new)} unregistered maintained file(s)")
    return 0


def cmd_refresh(fw: Path, paths: list[str]) -> int:
    root, _, _, files, _ = load_all(fw)
    idx = {e["path"]: e for e in files or []}
    for p in paths:
        if p not in idx:
            print(f"ERROR no entry for {p}", file=sys.stderr)
            return 2
        idx[p]["entry_sha256"] = sha(root / p)
    write_registry(fw / "DOCUMENTATION/FILE_REGISTRY.yml", FILE_HEADER, "files", sorted(idx.values(), key=lambda e: e["path"]))
    return 0


# --------------------------------------------------------------------- check
def wp_and_dec_ids(root: Path):
    def ids(rel, pat):
        p = root / rel
        return set(re.findall(pat, p.read_text(encoding="utf-8"))) if p.exists() else None
    return ids("docs/governance/04_work_packages.md", r"WP-\d{2}-\d{2}"), ids("docs/governance/02_decision_log_and_scope.md", r"DEC-\d{3}")


def check(fw: Path, since: str | None = None) -> cm.Findings:
    f = cm.Findings()
    root, schema, profile, files, feats = load_all(fw)
    fs, es = schema["file_registry"], schema["feature_registry"]
    if files is None:
        f.error("DOCUMENTATION/FILE_REGISTRY.yml missing")
        return f
    if feats is None:
        f.error("DOCUMENTATION/FEATURE_REGISTRY.yml missing")
        feats = []
    rules = profile["registry"]["exclude_globs"]
    wp_ids, dec_ids = wp_and_dec_ids(root)

    paths = {}
    for e in files:
        p = e.get("path")
        if not p:
            f.error("file entry without path")
            continue
        if p in paths:
            f.error(f"duplicate registry entry: {p}")
        paths[p] = e
        for k in fs["required_fields"]:
            if e.get(k) in (None, "", []):
                f.error(f"{p}: required field {k!r} missing or empty")
        if e.get("status") not in fs["statuses"]:
            f.error(f"{p}: status {e.get('status')!r} not in {fs['statuses']}")
        if e.get("classification") not in fs["classifications"]:
            f.error(f"{p}: classification {e.get('classification')!r} invalid")
        if e.get("provenance") not in fs["provenance_values"]:
            f.error(f"{p}: provenance {e.get('provenance')!r} invalid")
        if e.get("status") == "deprecated" and not (e.get("replacement") or e.get("notes")):
            f.error(f"{p}: deprecated without replacement or notes")
        if excluded(p, rules):
            f.error(f"{p}: excluded/generated path registered as maintained source")
        full = root / p
        if e.get("status") in ("active", "deprecated"):
            if not full.exists():
                f.error(f"{p}: registry entry for a file that does not exist (stale)")
            elif e.get("entry_sha256") and sha(full) != e["entry_sha256"] and p != ".ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml":  # a file cannot hold its own hash
                f.warn(f"{p}: file changed since its entry was written (entry may be stale; review then `refresh`)")
        for t in e.get("tests") or []:
            if not (root / t).exists():
                f.error(f"{p}: test {t} does not exist")
        for imp in e.get("internal_imports") or []:
            cand = imp.replace(".", "/")
            if not ((root / (cand + ".py")).exists() or (root / cand / "__init__.py").exists()):
                f.warn(f"{p}: internal import {imp} no longer resolves to a file")

    for rel in maintained_files(root, profile):
        if rel not in paths:
            f.error(f"unregistered maintained file: {rel}")

    fids = {x.get("id") for x in feats}
    for e in paths.values():
        for fid in e.get("features") or []:
            if fid not in fids:
                f.error(f"{e['path']}: references unknown feature {fid}")

    seen = set()
    for ft in feats:
        fid = ft.get("id", "?")
        if fid in seen:
            f.error(f"duplicate feature id {fid}")
        seen.add(fid)
        if not re.match(es["id_pattern"], str(fid)):
            f.error(f"feature {fid}: id does not match {es['id_pattern']}")
        for k in es["required_fields"]:
            if k == "tests":
                if "tests" not in ft:
                    f.error(f"feature {fid}: required field 'tests' missing (use [] if none exist)")
                elif not ft["tests"]:
                    f.warn(f"feature {fid}: no tests linked (record the gap in known_limitations)")
            elif ft.get(k) in (None, "", []):
                f.error(f"feature {fid}: required field {k!r} missing or empty")
        if ft.get("status") not in es["statuses"]:
            f.error(f"feature {fid}: status {ft.get('status')!r} invalid")
        doc = ft.get("doc")
        dp = (fw / "DOCUMENTATION/features" / doc) if doc else None
        if dp is None or not dp.exists():
            f.error(f"feature {fid}: doc {doc!r} does not exist under DOCUMENTATION/features/")
        else:
            heads = set(cm.sections(dp.read_text(encoding="utf-8")))
            for h in schema["feature_doc_required_headings"]:
                if h not in heads:
                    f.error(f"feature {fid}: doc missing heading '## {h}'")
        for p in ft.get("files") or []:
            if p not in paths:
                f.error(f"feature {fid}: file {p} is not registered")
            else:
                if fid not in (paths[p].get("features") or []):
                    f.error(f"feature {fid}: file {p} does not list {fid} in its features (not bidirectional)")
                if paths[p].get("status") in ("active", "deprecated") and (root / p).exists() and paths[p].get("entry_sha256") != sha(root / p):
                    f.warn(f"feature {fid}: related file {p} changed since registered; feature doc may be stale")
        for p in ft.get("tests") or []:
            if not (root / p).exists():
                f.error(f"feature {fid}: test {p} does not exist")
        for w in ft.get("work_packages") or []:
            if wp_ids is not None and w not in wp_ids:
                f.error(f"feature {fid}: work package {w} not in GOV-04")
        for d in ft.get("decisions") or []:
            if dec_ids is not None and d not in dec_ids:
                f.error(f"feature {fid}: decision {d} not in GOV-02")
        for ev in ft.get("evidence") or []:
            if not (root / ev).exists():
                f.error(f"feature {fid}: evidence {ev} does not exist")

    if since:
        out = cm.git(root, "diff", "--name-status", "-M", since)
        if out is None:
            f.error(f"cannot diff against {since!r}")
        else:
            reg_touched = any(l.split("\t")[-1] == ".ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml" for l in out.splitlines())
            changed = {l.split("\t")[-1] for l in out.splitlines()}
            # Spec 10.3: behaviour changed but the feature document is stale. `refresh` re-hashes an entry without
            # proving anyone looked at the document, so staleness is judged on the change set, not on the hash.
            for ft in feats:
                doc = ft.get("doc")
                if not doc:
                    continue
                touched = sorted(x for x in (list(ft.get("files") or []) + list(ft.get("tests") or [])) if x in changed)
                if touched and f".ai-engineering/DOCUMENTATION/features/{doc}" not in changed:
                    f.error(f"feature {ft.get('id', '?')}: {touched[0]} changed but its feature doc {doc} was not updated "
                            "in this change set (update the document, or record why none is needed in the task report)")
            for line in out.splitlines():
                parts = line.split("\t")
                st, name = parts[0][0], parts[-1]
                if excluded(name, rules) or name.startswith(".ai-engineering/DOCUMENTATION/"):
                    continue
                if st in "ADR" and not reg_touched:
                    f.error(f"change set {st} {name} without a FILE_REGISTRY.yml update")
    return f


def cmd_trace(fw: Path, key: str) -> int:
    root, _, _, files, feats = load_all(fw)
    paths = {e["path"]: e for e in files or []}
    if key in paths:
        e = paths[key]
        print(f"{key}: features={e.get('features', [])} tests={e.get('tests', [])}")
        for ft in feats or []:
            if key in (ft.get("files") or []):
                print(f"  {ft['id']} {ft['name']}  WPs={ft.get('work_packages', [])} doc={ft['doc']}")
        return 0
    found = False
    for ft in feats or []:
        if key == ft["id"] or key in (ft.get("work_packages") or []):
            found = True
            print(f"{ft['id']} {ft['name']}: files={ft['files']} tests={ft['tests']} WPs={ft.get('work_packages', [])} doc={ft['doc']}")
    if not found:
        print(f"no registry entry, feature or work-package link for {key!r}", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--framework-dir", type=Path, default=FW)
    ap.add_argument("--strict", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--since")
    s = sub.add_parser("scan")
    s.add_argument("--write", action="store_true")
    r = sub.add_parser("refresh")
    r.add_argument("paths", nargs="+")
    t = sub.add_parser("trace")
    t.add_argument("key")
    a = ap.parse_args(argv)
    fw = a.framework_dir.resolve()
    try:
        if a.cmd == "check":
            return check(fw, a.since).report(a.strict)
        if a.cmd == "scan":
            return cmd_scan(fw, a.write)
        if a.cmd == "refresh":
            return cmd_refresh(fw, a.paths)
        return cmd_trace(fw, a.key)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR cannot run check: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
