"""Phase F stress suite: the 15 scenarios of spec section 16, run against the REAL enforcement scripts.

    python -I .ai-engineering/SCRIPTS/stress/test_scenarios.py [-v]

Each test copies the working tree into a throw-away Git repository (the source need not be a Git
repository), stages ONE scenario by driving the scripts through their command lines, and asserts the
framework detects the violation, or, for the happy path, accepts the legitimate work. Label: automated-test.

WHAT THIS PROVES: the scripts catch these deliberately introduced violations on this machine.
WHAT IT DOES NOT PROVE: that a real agent follows the protocol, that real CLIs load the adapters
(QUALITY/adapter_conformance.md), anything on Windows or macOS, or that evidence records are authentic:
an agent that writes a forged record by hand is caught only by independent review.
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_FW = HERE.parents[1]
REAL_ROOT = REAL_FW.parent
sys.path.insert(0, str(REAL_FW / "SCRIPTS" / "memory"))
import check_memory as cm  # noqa: E402

RG = ".ai-engineering/SCRIPTS/validation/run_gates.py"
CM = ".ai-engineering/SCRIPTS/memory/check_memory.py"
CR = ".ai-engineering/SCRIPTS/documentation/check_registry.py"
CA = ".ai-engineering/SCRIPTS/adapters/check_adapters.py"
T = "WP-00-01"

REVIEW_OK = """# Review Report

- **Reviewer label:** other-cli / model-b
- **Date:** 2026-11-12
- **Commit reviewed:** abc1234
- **Scope:** WP-00-01 diff

## Findings
- Severity: minor
- File: utils/hello.py line 1 - naming
- Required action: none

## Independent checks run
Separate context; independently re-ran the test suite and inspected the actual diff.

## Verdict
approved
"""

LIVE_OK = """---
task_id: "FW-F"
gate_id: "G20"
label: "live-verification"
status: "passed"
agent_label: "cli-x / model-y"
commit: "{commit}"
command: "python run_check_sources.py"
environment: "Windows 11; python 3.12; network: home broadband"
network: "home broadband, 2026-11-12"
provider_or_service: "openrouter.ai (real API)"
machine_or_os: "Windows 11"
verdict_rationale: "real call returned HTTP 200"
output_ref: "inline below"
timestamp: "2026-11-12T10:00:00+02:00"
---

HTTP 200 from the real service.
"""


def git(*a, cwd):
    return subprocess.run(["git", "-c", "core.quotepath=off", *a], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout.strip()


def png(path: Path):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"\x00\xff\x00\x00" * 4
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Scenario(unittest.TestCase):
    REPO_DIRNAME = "repo"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aef-stress-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / self.REPO_DIRNAME
        shutil.copytree(REAL_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", ".git", ".pytest_cache"))
        shutil.rmtree(self.root / ".ai-engineering" / "EVIDENCE", ignore_errors=True)
        self.fw = self.root / ".ai-engineering"
        self.t_out, self.t_rc, self.r_rc = self.tmp / "t_out.txt", self.tmp / "t_rc.txt", self.tmp / "r_rc.txt"
        script = self.tmp / "_t.py"
        script.write_text("import sys,pathlib\nd=pathlib.Path(sys.argv[1])\n"
                          "sys.stdout.buffer.write((d/'t_out.txt').read_bytes())\n"
                          "sys.exit(int((d/sys.argv[2]).read_text()))\n")
        self.set_tests("5 passed", 0)
        self.r_rc.write_text("0")
        self.edit_cmd(f'run: "python -m pytest -q"\n    status: exists', f'run: "python {script.as_posix()} {self.tmp.as_posix()} t_rc.txt"\n    status: exists')
        extra = (f'  regression_test:\n    run: "python {script.as_posix()} {self.tmp.as_posix()} r_rc.txt"\n    status: exists\n')
        self.edit_cmd("\nplatform_variants:", "\n" + extra + "\nplatform_variants:")
        git("init", "-q", "-b", "main", cwd=self.root)
        git("config", "user.email", "t@example.invalid", cwd=self.root)
        git("config", "user.name", "t", cwd=self.root)
        self.commit("init")
        self.sync_state()
        self.base = git("rev-parse", "HEAD", cwd=self.root)

    # ---- plumbing
    def edit_cmd(self, old, new):
        p = self.fw / "CONFIG/command_profiles.yml"
        t = p.read_text(encoding="utf-8")
        assert t.count(old) == 1, old
        p.write_text(t.replace(old, new), encoding="utf-8")

    def set_tests(self, out, rc):
        self.t_out.write_bytes(out.encode("utf-8") if isinstance(out, str) else out)
        self.t_rc.write_text(str(rc))

    def commit(self, msg="change"):
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "--allow-empty", "-m", msg, cwd=self.root)

    def sync_state(self):
        head = git("rev-parse", "HEAD", cwd=self.root)
        sp = self.fw / "MEMORY/PROJECT_STATE.yml"
        sp.write_text(re.sub(r"\b[0-9a-f]{40}\b", head, sp.read_text(encoding="utf-8")), encoding="utf-8")
        self.commit("sync state")

    def run_py(self, script, *args, env=None, cwd=None):
        e = dict(os.environ, **(env or {}))
        r = subprocess.run([sys.executable, "-I", str(self.root / script), *args], cwd=cwd or self.root, env=e,
                           capture_output=True, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout + r.stderr

    def rg(self, *a, **k):
        return self.run_py(RG, *a, **k)

    def records(self, area, task=T):
        d = self.fw / "EVIDENCE" / task / area
        return sorted(d.glob("*.md")) if d.is_dir() else []

    def set_current_task(self, extra=""):
        (self.fw / "MEMORY/CURRENT_TASK.md").write_text(f"# Current Task\n\n**Task:** {T}\n**Status:** in_progress\n{extra}\n", encoding="utf-8")

    def ok(self, rc_out, needle=None):
        rc, out = rc_out
        self.assertEqual(rc, 0, out)
        if needle:
            self.assertIn(needle, out)
        return out

    def bad(self, rc_out, needle):
        rc, out = rc_out
        self.assertNotEqual(rc, 0, out)
        self.assertIn(needle, out)
        return out


# ===================================================================== 1
class S01SimpleFeature(Scenario):
    def test_s01_successful_feature_task_is_accepted_end_to_end(self):
        self.bad(self.run_py(CM, "start", "--task", T), "PCD-018")           # default must be recorded first
        self.set_current_task("PCD impact: PCD-018 interim default used (assumed accepted)\n")
        self.ok(self.run_py(CM, "start", "--task", T))
        sp = self.fw / "MEMORY/PROJECT_STATE.yml"                      # starting a task updates the state record too
        st = sp.read_text(encoding="utf-8")
        for k, v in (("active_task", "WP-00-01"), ("task_status", "in_progress"), ("phase", '"00"')):
            st = re.sub(rf"^{k}: .*$", f"{k}: {v}", st, flags=re.M)
        sp.write_text(st, encoding="utf-8")
        self.commit("start task")
        self.ok(self.rg("baseline", "--task", T))
        (self.root / "utils/hello.py").write_text('"""Greeting helper used by the S01 stress scenario."""\n\n\ndef hello():\n    return "hi"\n', encoding="utf-8")
        self.commit("add hello")
        self.ok(self.run_py(CR, "scan", "--write"))
        self.sync_state()
        self.ok(self.rg("run", "tests_all", "--task", T, "--area", "validation"))
        self.ok(self.rg("mustkeep", "--base", self.base, "--task", T))
        self.ok(self.rg("protected", "--base", self.base, "--task", T))
        self.ok(self.rg("docs-gate", "--task", T))
        review = self.tmp / "review.md"
        review.write_text(REVIEW_OK, encoding="utf-8")
        self.ok(self.rg("validate-review", str(review), "--task", T))
        self.ok(self.rg("close-check", "--task", T, "--require", "G1,G2,PROTECTED,DOCS,REVIEW", "--base", self.base))


# ===================================================================== 2
class S02DefectRegression(Scenario):
    def test_s02_regression_test_must_fail_before_and_pass_after(self):
        self.r_rc.write_text("1")
        self.assertEqual(self.rg("run", "regression_test", "--task", T, "--area", "baseline", "--gate", "REG")[0], 1)
        self.r_rc.write_text("0")
        self.ok(self.rg("run", "regression_test", "--task", T, "--area", "validation", "--gate", "REG"))
        self.ok(self.rg("close-check", "--task", T, "--require", "REG"))

    def test_s02_missing_failing_before_evidence_blocks(self):
        self.ok(self.rg("run", "regression_test", "--task", T, "--area", "validation", "--gate", "REG"))
        self.bad(self.rg("close-check", "--task", T, "--require", "REG"), "failing")

    def test_s02_test_that_never_failed_does_not_count(self):
        self.ok(self.rg("run", "regression_test", "--task", T, "--area", "baseline", "--gate", "REG"))
        self.ok(self.rg("run", "regression_test", "--task", T, "--area", "validation", "--gate", "REG"))
        self.bad(self.rg("close-check", "--task", T, "--require", "REG"), "failing")


# ===================================================================== 3
class S03SkippedTests(Scenario):
    def test_s03_code_written_but_tests_never_run(self):
        (self.root / "utils/hello.py").write_text('"""x"""\n', encoding="utf-8")
        self.bad(self.rg("close-check", "--task", T, "--require", "G1"), "no evidence record")

    def test_s03_tests_run_then_code_changed_is_stale(self):
        self.ok(self.rg("run", "tests_all", "--task", T, "--area", "validation"))
        (self.root / "utils/late_change.py").write_text('"""late"""\n', encoding="utf-8")
        self.bad(self.rg("close-check", "--task", T, "--require", "G1"), "stale")


# ===================================================================== 4
class S04SkippedReportedAsPassed(Scenario):
    def write_record(self, name, **over):
        rec = dict(task_id=T, gate_id="G1", label="automated-test", status="passed", agent_label="a", commit=self.base,
                   command="x", environment="e", verdict_rationale="r", output_ref="inline", timestamp="2026-11-12T10:00:00+00:00")
        rec.update(over)
        d = self.fw / "EVIDENCE" / T / "validation"
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_text("---\n" + "\n".join(f'{k}: "{v}"' for k, v in rec.items()) + "\n---\n\nbody\n", encoding="utf-8")
        return p

    def test_s04_skipped_label_cannot_be_passed(self):
        p = self.write_record("a.md", label="skipped")
        self.bad(self.rg("validate-evidence", str(p)), "skipped can never be passed")

    def test_s04_unavailable_status_needs_unavailable_label(self):
        p = self.write_record("b.md", status="unavailable")
        self.bad(self.rg("validate-evidence", str(p)), "must carry label")

    def test_s04_passed_status_contradicting_a_failing_exit_code(self):
        p = self.write_record("c.md", exit_code="3")
        self.bad(self.rg("validate-evidence", str(p)), "exit_code")

    def test_s04_unavailable_command_is_recorded_not_passed(self):
        rc, out = self.rg("run", "secret_pii_scan", "--task", T, "--area", "validation")
        self.assertEqual(rc, 1, out)
        self.bad(self.rg("close-check", "--task", T, "--require", "G12"), "not closable")


# ===================================================================== 5 / 6
HANDOFF = Path(REAL_FW / "SCRIPTS/memory/test_check_memory.py")


def good_handoff(head, branch="main", status="?? scratch_probe.txt", untracked="- scratch_probe.txt: probe file"):
    src = HANDOFF.read_text(encoding="utf-8")
    m = re.search(r'GOOD_HANDOFF = """(.*?)"""', src, re.S)
    return m.group(1).format(branch=branch, head=head, status=status, untracked=untracked)


class S05_06Handoff(Scenario):
    def write_handoff(self, **kw):
        d = self.fw / "MEMORY/handoffs/WP-00-01"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "20261112-101500_cli-a.md"
        p.write_text(good_handoff(git("rev-parse", "HEAD", cwd=self.root), **kw), encoding="utf-8")
        return p

    def test_s05_quota_interruption_with_dirty_tree_then_switch(self):
        ev = self.fw / "EVIDENCE/WP-00-01/baseline"
        ev.mkdir(parents=True)
        (ev / "t.txt").write_text("baseline output", encoding="utf-8")        # the handoff cites it; the checker verifies it exists
        self.commit("baseline evidence")
        (self.root / "scratch_probe.txt").write_text("probe", encoding="utf-8")
        p = self.write_handoff()
        self.ok(self.run_py(CM, "handoff", str(p), "--against-git"))        # outgoing agent
        self.ok(self.run_py(CM, "handoff", str(p), "--against-git"))        # incoming agent re-runs the same check

    def test_s06_handoff_with_wrong_head(self):
        (self.root / "scratch_probe.txt").write_text("probe", encoding="utf-8")
        p = self.write_handoff()
        p.write_text(p.read_text(encoding="utf-8").replace(git("rev-parse", "HEAD", cwd=self.root), "0" * 40), encoding="utf-8")
        self.bad(self.run_py(CM, "handoff", str(p), "--against-git"), "HEAD")

    def test_s06_handoff_hides_a_dirty_file(self):
        p = self.write_handoff(status="", untracked="- none")
        (self.root / "scratch_probe.txt").write_text("probe", encoding="utf-8")
        self.bad(self.run_py(CM, "handoff", str(p), "--against-git"), "scratch_probe.txt")

    def test_s06_handoff_claims_a_change_git_does_not_show(self):
        p = self.write_handoff(status="", untracked="- ghost_file.txt: claimed")
        self.bad(self.run_py(CM, "handoff", str(p), "--against-git"), "ghost_file.txt")


# ===================================================================== 7 / 8
class S07_08Documentation(Scenario):
    def test_s07_undocumented_new_source_file(self):
        (self.root / "utils/secret_helper.py").write_text('"""x"""\n', encoding="utf-8")
        self.bad(self.rg("docs-gate", "--task", T), "unregistered maintained file")

    def feature_source(self):
        reg = cm.load_yaml(self.fw / "DOCUMENTATION/FEATURE_REGISTRY.yml")
        ft = next(f for f in reg["features"] if f.get("files"))
        return ft["id"], ft["files"][0], ft["doc"]

    def test_s08_feature_source_changed_but_feature_doc_not_updated(self):
        fid, src, doc = self.feature_source()
        p = self.root / src
        p.write_text(p.read_text(encoding="utf-8") + "\n# behaviour change\n", encoding="utf-8")
        self.commit("change feature source")
        self.run_py(CR, "refresh", src)
        self.commit("refresh registry hash only")
        self.bad(self.run_py(CR, "check", "--since", self.base), f"feature {fid}")

    def test_s08_updating_the_feature_doc_clears_it(self):
        fid, src, doc = self.feature_source()
        p = self.root / src
        p.write_text(p.read_text(encoding="utf-8") + "\n# behaviour change\n", encoding="utf-8")
        d = self.fw / "DOCUMENTATION/features" / doc
        d.write_text(d.read_text(encoding="utf-8") + "\nChanged behaviour recorded.\n", encoding="utf-8")
        self.commit("change feature source and doc")
        self.run_py(CR, "refresh", src, f".ai-engineering/DOCUMENTATION/features/{doc}")
        self.commit("refresh")
        rc, out = self.run_py(CR, "check", "--since", self.base)
        self.assertNotIn(f"ERROR feature {fid}", out)
        self.assertNotIn("ERROR change set", out)


# ===================================================================== 9
class S09UiValidation(Scenario):
    VIEW = '    status: pending_owner       # not defined by the suite; proposal below is NOT active'
    ACTIVE = '    status: active\n    active: {desktop: "1920x1080", tablet: "820x1180", mobile: "390x844"}'

    def touch_ui(self):
        p = self.root / "jobhunter_ui/server.py"
        p.write_text(p.read_text(encoding="utf-8") + "\n# ui change\n", encoding="utf-8")
        self.commit("ui change")

    def define_viewports(self):
        pp = self.fw / "CONFIG/project_profile.yml"
        t = pp.read_text(encoding="utf-8")
        self.assertEqual(t.count(self.VIEW), 1)
        pp.write_text(t.replace(self.VIEW, self.ACTIVE), encoding="utf-8")
        self.commit("owner defines viewports")

    def shot(self, vp, result="passed"):
        img = self.tmp / f"{vp}.png"
        png(img)
        return self.rg("record-ui", "--task", T, "--viewport", vp, "--image", str(img), "--workflow", "scan-and-rank",
                       "--result", result, "--tool", "manual")

    def test_s09_ui_change_without_ui_evidence(self):
        self.touch_ui()
        self.bad(self.rg("close-check", "--task", T, "--require", "G1", "--base", self.base), "UI")

    def test_s09_viewports_not_defined_is_unavailable_not_passed(self):
        self.touch_ui()
        self.bad(self.rg("close-check", "--task", T, "--require", "UI"), "viewports")

    def test_s09_only_desktop_screenshot(self):
        self.define_viewports()
        self.touch_ui()
        self.shot("1920x1080")
        self.bad(self.rg("close-check", "--task", T, "--require", "UI"), "390x844")

    def test_s09_broken_mobile_viewport(self):
        self.define_viewports()
        self.touch_ui()
        self.shot("1920x1080")
        self.shot("820x1180")
        self.shot("390x844", "failed")
        self.bad(self.rg("close-check", "--task", T, "--require", "UI"), "390x844")

    def test_s09_all_viewports_passed(self):
        self.define_viewports()
        self.touch_ui()
        for vp in ("1920x1080", "820x1180", "390x844"):
            self.shot(vp)
        self.ok(self.rg("close-check", "--task", T, "--require", "UI"))


# ===================================================================== 10
class S10Approvals(Scenario):
    def approval(self, op, task=T, **over):
        d = self.fw / "MEMORY/approvals" / task
        d.mkdir(parents=True, exist_ok=True)
        fields = dict(operation=op, task_id=task, approved_by="owner", owner_message_ref="chat 2026-11-12 'yes, add httpx'",
                      scope="add one dependency")
        fields.update(over)
        (d / f"{op}.md").write_text("---\n" + "\n".join(f'{k}: "{v}"' for k, v in fields.items()) + "\n---\n", encoding="utf-8")

    def add_dependency(self):
        p = self.root / "requirements.txt"
        p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\nsomenewlib>=1.0\n", encoding="utf-8")
        self.commit("add dependency")

    def test_s10_new_dependency_without_approval(self):
        self.add_dependency()
        self.bad(self.rg("approvals", "--base", self.base, "--task", T), "add_dependency_or_external_service")

    def test_s10_approval_record_clears_it(self):
        self.add_dependency()
        self.approval("add_dependency_or_external_service")
        self.ok(self.rg("approvals", "--base", self.base, "--task", T))

    def test_s10_approval_for_another_operation_or_task_does_not_transfer(self):
        self.add_dependency()
        self.approval("production_deploy_or_release")
        self.approval("add_dependency_or_external_service", task="WP-00-02")
        self.bad(self.rg("approvals", "--base", self.base, "--task", T), "add_dependency_or_external_service")

    def test_s10_approval_without_owner_message_reference(self):
        self.add_dependency()
        self.approval("add_dependency_or_external_service", owner_message_ref="")
        self.bad(self.rg("approvals", "--base", self.base, "--task", T), "owner_message_ref")

    def test_s10_history_rewrite(self):
        git("commit", "-q", "--amend", "-m", "rewritten", cwd=self.root)
        self.bad(self.rg("approvals", "--base", self.base, "--task", T), "force_push_or_history_rewrite")

    def test_s10_mass_deletion(self):
        for p in sorted((self.root / "tests").glob("test_*.py"))[:20]:
            p.unlink()
        self.commit("delete many")
        self.bad(self.rg("approvals", "--base", self.base, "--task", T), "delete_or_overwrite")

    def test_s10_clean_change_needs_no_approval(self):
        (self.root / "utils/ok.py").write_text('"""x"""\n', encoding="utf-8")
        self.commit("ordinary")
        self.ok(self.rg("approvals", "--base", self.base, "--task", T))


# ===================================================================== 11
class S11UnresolvedDecision(Scenario):
    def wp_row(self, wp, status=None, deps=None):
        p = self.root / "docs/governance/04_work_packages.md"
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if ln.startswith(f"| {wp} |"):
                cells = ln.split("|")
                if status:
                    cells[-2] = f" {status} "
                if deps is not None:
                    cells[5] = f" {deps} "
                lines[i] = "|".join(cells)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_s11_unknown_work_package(self):
        self.bad(self.run_py(CM, "start", "--task", "WP-99-99"), "not in")

    def test_s11_blocked_package_cannot_start(self):
        self.bad(self.run_py(CM, "start", "--task", "WP-00-02"), "blocked")

    def test_s11_unmerged_dependency(self):
        self.wp_row("WP-00-02", status="ready_for_implementation")
        self.bad(self.run_py(CM, "start", "--task", "WP-00-02"), "WP-00-01")

    def test_s11_non_blocking_pcd_requires_recorded_default(self):
        self.bad(self.run_py(CM, "start", "--task", T), "PCD-018")
        self.set_current_task("PCD impact: PCD-018 interim default used\n")
        self.ok(self.run_py(CM, "start", "--task", T))

    def test_s11_blocking_pcd_requires_guarded_behaviour_out_of_scope(self):
        self.wp_row("WP-03-01", status="ready_for_implementation", deps="-")
        self.bad(self.run_py(CM, "start", "--task", "WP-03-01"), "PCD-005")
        (self.fw / "MEMORY/CURRENT_TASK.md").write_text("# Current Task\n\n**Task:** WP-03-01\nPCD out of scope: PCD-005 (hosted database)\n", encoding="utf-8")
        self.ok(self.run_py(CM, "start", "--task", "WP-03-01"))


# ===================================================================== 12
class S12PreexistingFailure(Scenario):
    OLD = "FAILED tests/test_old.py::test_a - boom\n1 failed, 5 passed\n"

    def run_baseline_and_after(self, after):
        self.set_tests(self.OLD, 1)
        self.assertEqual(self.rg("run", "tests_all", "--task", T, "--area", "baseline")[0], 1)
        self.set_tests(after, 1 if "FAILED" in after or "ERROR" in after else 0)
        self.rg("run", "tests_all", "--task", T, "--area", "validation")

    def test_s12_preexisting_failure_is_classified_not_hidden(self):
        self.run_baseline_and_after(self.OLD)
        out = self.ok(self.rg("regressions", "--task", T), "pre-existing")
        self.assertIn("tests/test_old.py::test_a", out)
        self.bad(self.rg("close-check", "--task", T, "--require", "G1,REGRESSIONS"), "KNOWN_ISSUES")
        k = self.fw / "MEMORY/KNOWN_ISSUES.md"
        k.write_text(k.read_text(encoding="utf-8") + "\n## KI-900 - old failure\n- tests/test_old.py::test_a fails on the baseline\n", encoding="utf-8")
        self.ok(self.rg("close-check", "--task", T, "--require", "G1,REGRESSIONS"))

    def test_s12_new_failure_is_a_regression(self):
        self.run_baseline_and_after(self.OLD + "FAILED tests/test_new.py::test_b - boom\n")
        self.bad(self.rg("regressions", "--task", T), "introduced")
        self.bad(self.rg("close-check", "--task", T, "--require", "G1,REGRESSIONS"), "not closable")

    def test_s12_failure_that_cannot_be_classified_is_not_passed(self):
        self.run_baseline_and_after(self.OLD)
        self.set_tests("something went wrong\n", 1)
        self.rg("run", "tests_all", "--task", T, "--area", "validation")
        self.bad(self.rg("regressions", "--task", T), "cannot classify")

    def test_s12_collection_error_counts_as_a_failure_id(self):
        self.run_baseline_and_after(self.OLD + "ERROR tests/test_x.py - ModuleNotFoundError: httpx\n")
        self.bad(self.rg("regressions", "--task", T), "tests/test_x.py")

    def test_s12_two_records_in_the_same_second_the_later_one_is_current(self):
        """Deterministic (no timing): the -1 suffix must outrank the plain name, whatever the timestamp digits are."""
        sys.path.insert(0, str(REAL_FW / "SCRIPTS" / "validation"))
        import run_gates as rg_mod
        d = self.fw / "EVIDENCE" / T / "validation"
        d.mkdir(parents=True)
        for name, status in (("G1_tests_all_20261112-130721.md", "failed"), ("G1_tests_all_20261112-130721-1.md", "passed")):
            (d / name).write_text("---\n" + "\n".join(f'{k}: "{v}"' for k, v in dict(
                task_id=T, gate_id="G1", label="automated-test", status=status, agent_label="a", commit=self.base, command="x",
                environment="e", verdict_rationale="r", output_ref="i", timestamp="2026-11-12T13:07:21+00:00").items()) + "\n---\n\nb\n", encoding="utf-8")
        latest = rg_mod.latest_by_gate(rg_mod.closing_records(rg_mod.collect(self.fw, T)))
        self.assertEqual(latest["G1"]["status"], "passed")

    def test_s12_fixed_failure_is_reported(self):
        self.run_baseline_and_after("6 passed\n")
        self.ok(self.rg("regressions", "--task", T), "fixed")


# ===================================================================== 13
class S13FakeLive(Scenario):
    def live(self, name, **repl):
        d = self.fw / "EVIDENCE" / "FW-F" / "validation"
        d.mkdir(parents=True, exist_ok=True)
        text = LIVE_OK.format(commit=self.base)
        for k, v in repl.items():
            text = re.sub(rf'^{k}: ".*"$', f'{k}: "{v}"', text, flags=re.M)
        p = d / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_s13_proper_live_record_is_accepted(self):
        self.ok(self.rg("validate-evidence", str(self.live("ok.md"))))

    def test_s13_live_without_provider(self):
        self.bad(self.rg("validate-evidence", str(self.live("a.md", provider_or_service=""))), "provider_or_service")

    def test_s13_live_without_network_statement(self):
        self.bad(self.rg("validate-evidence", str(self.live("b.md", network=""))), "network")

    def test_s13_live_against_a_mock_provider(self):
        self.bad(self.rg("validate-evidence", str(self.live("c.md", provider_or_service="local mock server"))), "mock")

    def test_s13_live_command_run_with_a_mock_flag(self):
        self.bad(self.rg("validate-evidence", str(self.live("d.md", command="python run_check_sources.py --offline-fixtures"))), "fixture")

    def test_s13_live_with_a_demo_project_label(self):
        p = self.live("e.md")
        p.write_text(p.read_text(encoding="utf-8").replace('machine_or_os:', 'project_label: "Demo"\nmachine_or_os:'), encoding="utf-8")
        self.bad(self.rg("validate-evidence", str(p)), "Demo")

    def test_s13_mocked_label_cannot_be_passed(self):
        p = self.live("f.md", label="mocked")
        self.bad(self.rg("validate-evidence", str(p)), "mocked")


# ===================================================================== 14
class S14MissingService(Scenario):
    def test_s14_owner_machine_only_check_is_unavailable(self):
        rc, out = self.rg("run", "source_check_live", "--task", T, "--area", "validation")
        self.assertEqual(rc, 1, out)
        self.assertIn("UNAVAILABLE", out)
        self.bad(self.rg("close-check", "--task", T, "--require", "source_check_live"), "not closable")

    def test_s14_missing_executable_is_failed_not_passed(self):
        self.edit_cmd('run: "python run_health.py"', 'run: "definitely-not-installed-tool --x"')
        rc, out = self.rg("run", "health_check", "--task", T, "--area", "validation")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAILED", out)


# ===================================================================== 15
class S15Portability(Scenario):
    REPO_DIRNAME = "repo with spaces \u00fc"

    def test_s15_unicode_filename_is_registered_under_its_real_name(self):
        (self.root / "utils/caf\u00e9.py").write_text('"""Cafe helper."""\n', encoding="utf-8")
        rc, out = self.run_py(CR, "scan")
        self.assertIn("utils/caf\u00e9.py", out)
        self.assertNotIn("\\303", out)

    def test_s15_unicode_filename_does_not_break_the_docs_gate_after_registration(self):
        (self.root / "utils/caf\u00e9.py").write_text('"""Cafe helper."""\n', encoding="utf-8")
        self.run_py(CR, "scan", "--write")
        self.commit("add cafe")
        self.sync_state()
        self.ok(self.rg("docs-gate", "--task", T))

    def test_s15_crlf_checkout_does_not_make_the_registry_stale(self):
        for rel in ("README.md", "utils/filters.py", ".ai-engineering/CORE/definition_of_done.md"):
            p = self.root / rel
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        rc, out = self.run_py(CR, "check")
        for rel in ("README.md", "utils/filters.py", ".ai-engineering/CORE/definition_of_done.md"):
            self.assertNotIn(f"WARN  {rel}: file changed", out)

    def test_s15_crlf_state_and_handoff_files_parse(self):
        for rel in (".ai-engineering/MEMORY/PROJECT_STATE.yml", ".ai-engineering/MEMORY/CURRENT_TASK.md"):
            p = self.root / rel
            p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.commit("crlf")
        self.sync_state()
        rc, out = self.run_py(CM, "state")
        self.assertEqual(rc, 0, out)

    def test_s15_command_output_that_is_not_utf8_is_still_recorded(self):
        self.set_tests(b"caf\xe9 \xff\xfe 5 passed\n", 0)
        rc, out = self.rg("run", "tests_all", "--task", T, "--area", "validation")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.records("validation"))

    def test_s15_legacy_console_encoding(self):
        self.set_tests("\u2713 5 passed\n", 0)
        rc, out = self.rg("run", "tests_all", "--task", T, "--area", "validation", env={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
        self.assertEqual(rc, 0, out)

    def test_s15_every_script_compiles_and_shows_help_on_this_platform(self):
        for script in (RG, CM, CR, CA):
            rc, out = self.run_py(script, "--help")
            self.assertEqual(rc, 0, f"{script}: {out}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
