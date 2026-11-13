#!/usr/bin/env python3
"""Static checks for the agent adapters (spec 6.1, roadmap Phase E).

    python .ai-engineering/SCRIPTS/adapters/check_adapters.py check [--strict] [--today YYYY-MM-DD]

Standard library only (YAML is read through SCRIPTS/memory/check_memory.py). Exit codes: 0 ok,
1 findings (errors; warnings too with --strict), 2 usage or environment error.

WHAT THIS PROVES: the adapter entry files exist, are thin, point at real canonical files, copy or
weaken no policy, do not load the same content twice, and that no CLI is recorded as conformant
without an evidence record.
WHAT THIS DOES NOT PROVE: that Kiro, Gemini CLI or OpenCode actually load or follow anything. Only
a live session can (QUALITY/adapter_conformance.md). The last output line always states the live
status so that a static pass cannot be mistaken for it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

FW = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FW / "SCRIPTS" / "memory"))
import check_memory as cm  # noqa: E402

ROOT = FW.parent
MARKER = "AEF-ADAPTER-MARKER: root-entry/1"
ENTRY, GEMINI = "AGENTS.md", "GEMINI.md"
MAX_ENTRY_LINES, MAX_ENTRY_BYTES, MAX_GEMINI_LINES = 60, 4096, 20
STALE_DAYS = 90
STATUSES = ("not_run", "passed", "failed", "partial")
IMPORT_LINE = "@./AGENTS.md"
# Canonical files the entry file must name, in this order for the first five (UNIVERSAL_AGENT section 1.1).
ORDERED_REFS = [
    ".ai-engineering/CORE/engineering_constitution.md",
    ".ai-engineering/CORE/universal_standards.md",
    ".ai-engineering/CORE/evidence_and_claims.md",
    ".ai-engineering/CORE/definition_of_done.md",
    ".ai-engineering/AGENTS/UNIVERSAL_AGENT.md",
]
OTHER_REFS = [
    ".ai-engineering/AGENTS/IMPLEMENTER.md", ".ai-engineering/AGENTS/REVIEWER.md",
    ".ai-engineering/AGENTS/HANDOFF_AND_RESUME.md", ".ai-engineering/WORKFLOW/handoff_protocol.md",
    ".ai-engineering/CONFIG/project_profile.yml", ".ai-engineering/CONFIG/project_contract_map.yml",
    ".ai-engineering/CONFIG/framework.yml", ".ai-engineering/MEMORY/", ".ai-engineering/EVIDENCE/",
]
ADAPTER_SECTIONS = [
    "## 1. Canonical instructions", "## 2. Project profile and contract map", "## 3. Role",
    "## 4. Bootstrap or resume", "## 5. Where state, evidence and handoffs go",
    "## 6. Verified loading mechanism", "## 7. How to confirm the contract loaded",
    "## 8. Known caveats", "## 9. Conformance status",
]
# Text that would turn a pointer file into a policy file (constitution 6: an adapter "cannot contain policy").
WEAKENING = [
    (r"\b(skip|ignore|bypass|waive|relax|exempt)\w*\s+(the\s+|a\s+|any\s+|all\s+|this\s+|these\s+)?"
     r"(required\s+|quality\s+|validation\s+)?(gate|gates|test|tests|review|evidence|handoff|approval)s?\b",
     "weakens a gate, test, review, evidence or approval requirement"),
    (r"\b(cheap|cheaper|weaker|smaller|lighter|free)\b[^.\n]{0,25}\bmodels?\b[^.\n]{0,30}"
     r"\b(may|can|need not|does not need|do not need|is allowed|are allowed|exempt)\b",
     "grants a model-specific exemption"),
    (r"\b(done|complete|completed|finished)\s+(when|once|if)\b", "defines completion (only definition_of_done.md may)"),
]
CHECKLIST = re.compile(r"^\s*[-*]\s+\[[ xX]\]")
FENCE = re.compile(r"^\s*(```|~~~)")


def rd(path: Path, f: cm.Findings, label: str):
    """Read UTF-8 text without a BOM; report problems. Returns text or None."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        f.error(f"{label}: cannot read ({e})")
        return None
    if raw.startswith(b"\xef\xbb\xbf"):
        f.error(f"{label}: starts with a UTF-8 BOM (remove it; Windows editors add one)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        f.error(f"{label}: not valid UTF-8")
        return None
    if b"\r\n" in raw and re.search(rb"(?<!\r)\n", raw):
        f.warn(f"{label}: mixed CRLF and LF line endings")
    return text


def canon_lines(fw: Path) -> set[str]:
    out: set[str] = set()
    for sub in ("CORE", "AGENTS"):
        for p in (fw / sub).glob("*.md"):
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                out.add(norm(ln))
    return out


def norm(ln: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", ln)).strip()


def policy_free(text: str, label: str, canon: set[str], f: cm.Findings) -> None:
    for i, ln in enumerate(text.splitlines(), 1):
        n = norm(ln)
        if len(n) >= 80 and n in canon:
            f.error(f"{label}:{i}: copies a canonical line verbatim (point to the file instead of copying it)")
        if CHECKLIST.match(ln):
            f.error(f"{label}:{i}: contains a checklist item (adapters define no completion criteria)")
        for pat, why in WEAKENING:
            if re.search(pat, ln, re.I):
                f.error(f"{label}:{i}: {why}")


def no_symlink(paths, root: Path, f: cm.Findings) -> None:
    for p in paths:
        if p.is_symlink():
            f.error(f"{p.relative_to(root).as_posix()}: is a symlink (Kiro is reported not to follow them; Windows needs "
                    "elevated rights). Use a real file")


def check_entry(root: Path, fw: Path, f: cm.Findings, canon: set[str]) -> str | None:
    p = root / ENTRY
    if not p.is_file():
        f.error(f"{ENTRY}: missing (Kiro and OpenCode read this file at the repository root)")
        return None
    text = rd(p, f, ENTRY)
    if text is None:
        return None
    if len(text.splitlines()) > MAX_ENTRY_LINES or len(text.encode()) > MAX_ENTRY_BYTES:
        f.error(f"{ENTRY}: not thin (limit {MAX_ENTRY_LINES} lines / {MAX_ENTRY_BYTES} bytes); it loads into every prompt")
    if text.count(MARKER) != 1:
        f.error(f"{ENTRY}: marker line '{MARKER}' must appear exactly once (conformance test C1 depends on it)")
    for tok in re.findall(r"`([^`\s]+)`", text):
        if "/" not in tok or any(c in tok for c in "<>*") or tok.startswith("http"):
            continue
        if not (root / tok).exists():
            f.error(f"{ENTRY}: references '{tok}', which does not exist")
    pos = []
    for ref in ORDERED_REFS:
        i = text.find(ref)
        if i < 0:
            f.error(f"{ENTRY}: does not point to {ref}")
        pos.append(i)
    found = [i for i in pos if i >= 0]
    if found != sorted(found):
        f.error(f"{ENTRY}: canonical files are not listed in UNIVERSAL_AGENT section 1.1 order")
    for ref in OTHER_REFS:
        if ref not in text:
            f.error(f"{ENTRY}: does not point to {ref}")
    policy_free(text, ENTRY, canon, f)
    return text


def gemini_names(root: Path, f: cm.Findings) -> list[str]:
    p = root / ".gemini" / "settings.json"
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        f.warn(f".gemini/settings.json: cannot parse ({e}); duplicate-load check skipped")
        return []
    val = (data.get("context") or {}).get("fileName", data.get("contextFileName"))
    return [val] if isinstance(val, str) else [str(x) for x in (val or [])]


def check_gemini(root: Path, f: cm.Findings, canon: set[str]) -> None:
    p = root / GEMINI
    if not p.is_file():
        f.error(f"{GEMINI}: missing (Gemini CLI does not read AGENTS.md by default)")
        return
    text = rd(p, f, GEMINI)
    if text is None:
        return
    if len(text.splitlines()) > MAX_GEMINI_LINES:
        f.error(f"{GEMINI}: not thin (limit {MAX_GEMINI_LINES} lines)")
    imports, in_fence = [], False
    for ln in text.splitlines():
        if FENCE.match(ln):
            in_fence = not in_fence
        elif not in_fence and re.match(r"^@\S+\s*$", ln):
            imports.append(ln.strip())
    if imports != [IMPORT_LINE]:
        f.error(f"{GEMINI}: must import exactly '{IMPORT_LINE}' on its own line outside code fences (found {imports or 'none'})")
    names = gemini_names(root, f)
    if ENTRY in names and imports:
        f.error(f".gemini/settings.json loads {ENTRY} through the filename list while {GEMINI} also imports it: "
                "the content would load twice. Use one mechanism")
    policy_free(text, GEMINI, canon, f)


def check_other_surfaces(root: Path, canon: set[str], f: cm.Findings) -> None:
    for p in sorted((root / ".kiro" / "steering").glob("*.md")) if (root / ".kiro" / "steering").is_dir() else []:
        f.warn(f"{p.relative_to(root).as_posix()}: a second instruction surface exists for Kiro; it must stay a pointer file")
        t = rd(p, f, p.relative_to(root).as_posix())
        if t is not None:
            policy_free(t, p.relative_to(root).as_posix(), canon, f)
    for name in ("opencode.json", "opencode.jsonc"):
        p = root / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            f.warn(f"{name}: cannot parse as plain JSON (comments?); 'instructions' paths not checked")
            continue
        for ins in data.get("instructions", []) or []:
            if str(ins).startswith("http"):
                f.warn(f"{name}: remote instruction {ins} is outside the repository and cannot be reviewed with it")
            elif not (list(root.glob(ins)) if any(c in ins for c in "*?[") else [root / ins] if (root / ins).exists() else []):
                f.error(f"{name}: instruction '{ins}' matches no file")
    if (root / "CLAUDE.md").is_file():
        f.warn("CLAUDE.md exists: OpenCode uses it only when AGENTS.md is absent; confirm it adds no rules of its own")


def adapter_status(text: str):
    m = re.search(r"\*\*Status:\*\*\s*(\S+)", text)
    return m.group(1) if m else None


def check_adapter_docs(root: Path, fw: Path, f: cm.Findings, canon: set[str], today: dt.date) -> dict[str, str]:
    statuses: dict[str, str] = {}
    try:
        targets = cm.load_yaml(fw / "CONFIG/model_profiles.yml").get("supported_cli_targets") or []
    except (OSError, ValueError) as e:
        f.error(f"CONFIG/model_profiles.yml: cannot read ({e})")
        return statuses
    adir = fw / "AGENTS" / "adapters"
    for extra in sorted(adir.glob("*.md")) if adir.is_dir() else []:
        if extra.stem not in targets:
            f.warn(f"AGENTS/adapters/{extra.name}: not listed in model_profiles.yml supported_cli_targets")
    for t in targets:
        rel = f"AGENTS/adapters/{t}.md"
        p = adir / f"{t}.md"
        if not p.is_file():
            f.error(f"{rel}: missing adapter document for supported target '{t}'")
            statuses[t] = "not_run"
            continue
        no_symlink([p], root, f)
        text = rd(p, f, rel)
        if text is None:
            continue
        for h in ADAPTER_SECTIONS:
            if not re.search(r"^" + re.escape(h) + r"\s*$", text, re.M):
                f.error(f"{rel}: missing section '{h}'")
        if not re.search(r"\*\*Adapter protocol:\*\*\s*1\b", text):
            f.error(f"{rel}: missing '**Adapter protocol:** 1'")
        m = re.search(r"\*\*Verified on:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
        if not m:
            f.error(f"{rel}: missing '**Verified on:** YYYY-MM-DD' (loading mechanisms must be verified, spec 17 Phase E)")
        else:
            try:
                age = (today - dt.date.fromisoformat(m.group(1))).days
                if age > STALE_DAYS:
                    f.warn(f"{rel}: mechanism last verified {age} days ago; re-verify against the official documentation")
                if age < 0:
                    f.error(f"{rel}: 'Verified on' date is in the future")
            except ValueError:
                f.error(f"{rel}: 'Verified on' is not a valid date")
        if not re.search(r"\*\*Sources:\*\*[^\n]*https://", text):
            f.error(f"{rel}: no official https:// source recorded under '**Sources:**'")
        st = adapter_status(text)
        if st not in STATUSES:
            f.error(f"{rel}: '**Status:**' must be one of {STATUSES} (found {st!r})")
            st = "not_run"
        statuses[t] = st
        if st == "passed":
            check_evidence(root, rel, t, text, f)
        policy_free(text, rel, canon, f)
    return statuses


def check_evidence(root: Path, rel: str, target: str, text: str, f: cm.Findings) -> None:
    m = re.search(r"\*\*Evidence:\*\*\s*`?(\.ai-engineering/EVIDENCE/FW-E/\S+?\.md)`?", text)
    if not m:
        f.error(f"{rel}: Status passed but no '**Evidence:**' path under .ai-engineering/EVIDENCE/FW-E/ (fail closed)")
        return
    ev = root / m.group(1)
    if not ev.is_file():
        f.error(f"{rel}: Status passed but evidence file {m.group(1)} does not exist")
        return
    body = ev.read_text(encoding="utf-8", errors="replace")
    for needle, why in ((f"gate_id: ADAPTER-{target.upper()}", "gate_id for this CLI"), ("label: live-verification", "label live-verification"),
                        ("status: passed", "status passed"),
                        ("network:", "a network field"), ("provider_or_service:", "a provider_or_service field")):
        if needle not in body:
            f.error(f"{rel}: evidence {m.group(1)} lacks {why}")


def check_framework_status(fw: Path, statuses: dict[str, str], f: cm.Findings) -> str:
    derived = ("not_run" if not any(s in ("passed", "partial") for s in statuses.values())
               else "passed" if statuses and all(s == "passed" for s in statuses.values()) else "partial")
    try:
        impl = cm.load_yaml(fw / "CONFIG/framework.yml").get("implementation_status") or {}
    except (OSError, ValueError) as e:
        f.error(f"CONFIG/framework.yml: cannot read ({e})")
        return derived
    declared = impl.get("phase_E_live_cli_conformance")
    if declared != derived:
        f.error(f"framework.yml phase_E_live_cli_conformance is {declared!r} but the adapter documents imply {derived!r}")
    return derived


def run(root: Path, fw: Path, today: dt.date) -> tuple[cm.Findings, dict[str, str]]:
    f = cm.Findings()
    canon = canon_lines(fw)
    surfaces = [root / ENTRY, root / GEMINI, root / ".gemini" / "settings.json", root / "opencode.json"]
    steering = root / ".kiro" / "steering"
    if steering.is_dir():
        surfaces += sorted(steering.glob("*.md"))
    no_symlink(surfaces, root, f)
    check_entry(root, fw, f, canon)
    check_gemini(root, f, canon)
    check_other_surfaces(root, canon, f)
    statuses = check_adapter_docs(root, fw, f, canon, today)
    check_framework_status(fw, statuses, f)
    return f, statuses


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true")
    c.add_argument("--today", help="override today's date (tests)")
    a = ap.parse_args(argv)
    try:
        today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
        f, statuses = run(ROOT, FW, today)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    rc = f.report(strict=a.strict)
    live = " ".join(f"{k}={v}" for k, v in statuses.items()) or "none"
    print(f"LIVE CLI CONFORMANCE: {live}  (a static pass is not evidence that any CLI loads the contract)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
