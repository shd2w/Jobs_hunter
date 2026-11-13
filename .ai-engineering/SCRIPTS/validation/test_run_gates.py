"""Tests for run_gates.py. Run:  python -I .ai-engineering/SCRIPTS/validation/test_run_gates.py
Each test copies the repository (tracked files + .ai-engineering) into a throw-away Git repo,
swaps in trivial project commands (so no real test suite is invoked) and checks one behaviour.
Label: automated-test. The browser/UI test uses a generated PNG, not a real browser."""
import contextlib
import io
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
sys.path.insert(0, str(HERE))
import run_gates as rg  # noqa: E402

REAL_FW = HERE.parents[1]
REAL_ROOT = REAL_FW.parent
TASK = "WP-00-01"

REVIEW_OK = """# Review Report

- **Reviewer label:** other-cli / model-b
- **Date:** 2026-11-10
- **Commit reviewed:** abc1234
- **Scope:** WP-00-01 diff

## Findings
- Severity: minor
- File: utils/x.py line 3 - naming
- Required action: none

## Independent checks run
Separate context; independently re-ran the test suite and inspected the actual diff.

## Verdict
approved
"""


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def png(path: Path):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"\x00\xff\x00\x00" * 4
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "repo"
        for rel in git("ls-files", cwd=REAL_ROOT).splitlines():
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REAL_ROOT / rel, dst)
        shutil.copytree(REAL_FW, self.root / ".ai-engineering", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "EVIDENCE"))
        self.fw = self.root / ".ai-engineering"
        cp = self.fw / "CONFIG/command_profiles.yml"
        cp.write_text(self._insert_commands(cp.read_text(encoding="utf-8")), encoding="utf-8")
        git("init", "-q", "-b", "main", cwd=self.root)
        git("config", "user.email", "t@example.invalid", cwd=self.root)
        git("config", "user.name", "t", cwd=self.root)
        self.commit("init")

    def _insert_commands(self, t):
        extra = '''  always_fail:
    run: "python -c \\"import sys; sys.exit(3)\\""
    status: exists
  leaky:
    run: "python -c \\"print('key sk-abcdefghijklmnopqrstuvwxyz123456 end')\\""
    status: exists
  fast_tests:
    run: "python -c \\"print('1 passed')\\""
    status: exists
'''
        t = t.replace('run: "python -m pytest -q"\n    status: exists', 'run: "python -c \\"print(\'1 passed\')\\""\n    status: exists', 1)
        return t.replace("\nplatform_variants:", "\n" + extra + "\nplatform_variants:", 1)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, msg):
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "--allow-empty", "-m", msg, cwd=self.root)

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = rg.main(["--framework-dir", str(self.fw), *args])
        return rc, out.getvalue() + err.getvalue()

    def records(self, area=None):
        d = self.fw / "EVIDENCE" / TASK
        out = []
        for p in sorted(d.rglob("*.md")) if d.is_dir() else []:
            if area and p.parent.name != area:
                continue
            out.append(rg.read_record(p)[0] | {"_file": p})
        return out


class RunTests(Base):
    def test_unknown_command_is_usage_error(self):
        self.assertEqual(self.call("run", "nope", "--task", TASK)[0], 2)

    def test_passing_command_records_passed_with_gate_alias(self):
        rc, out = self.call("run", "tests_all", "--task", TASK)
        self.assertEqual(rc, 0, out)
        r = self.records("validation")[0]
        self.assertEqual((r["gate_id"], r["status"], r["label"], r["exit_code"]), ("G1", "passed", "automated-test", 0))
        self.assertEqual(len(r["commit"]), 40)

    def test_failing_command_records_failed(self):
        rc, _ = self.call("run", "always_fail", "--task", TASK)
        r = self.records("validation")[0]
        self.assertEqual((rc, r["status"], r["exit_code"]), (1, "failed", 3))

    def test_unavailable_command_is_never_passed(self):
        rc, out = self.call("run", "dependency_consistency", "--task", TASK)
        r = self.records("validation")[0]
        self.assertEqual((rc, r["status"], r["label"]), (1, "unavailable", "unavailable"))
        self.assertIn("NOT executed", r["_file"].read_text())

    def test_owner_machine_only_command_is_unavailable(self):
        rc, _ = self.call("run", "source_check_live", "--task", TASK)
        self.assertEqual((rc, self.records("validation")[0]["status"]), (1, "unavailable"))

    def test_secrets_in_output_are_redacted(self):
        self.call("run", "leaky", "--task", TASK)
        r = self.records("validation")[0]
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", r["_file"].read_text())
        self.assertGreaterEqual(r["redactions"], 1)

    def test_records_pass_schema_validation(self):
        self.call("run", "tests_all", "--task", TASK)
        self.call("run", "dependency_consistency", "--task", TASK)
        self.assertEqual(self.call("validate-evidence", str(self.fw / "EVIDENCE" / TASK))[0], 0)


class EvidenceValidationTests(Base):
    def write(self, **over):
        self.call("run", "tests_all", "--task", TASK)
        p = self.records("validation")[0]["_file"]
        t = p.read_text()
        for k, v in over.items():
            t = re.sub(rf'^{k}: .*$', f'{k}: {v}', t, count=1, flags=re.M)
        p.write_text(t)
        return p

    def errs(self, p):
        rc, out = self.call("validate-evidence", str(p))
        return rc, out

    def test_mocked_cannot_be_passed(self):
        rc, out = self.errs(self.write(label='"mocked"'))
        self.assertEqual(rc, 1)
        self.assertIn("mocked", out)

    def test_unavailable_label_cannot_be_passed(self):
        self.assertEqual(self.errs(self.write(label='"unavailable"'))[0], 1)

    def test_unknown_commit_rejected(self):
        rc, out = self.errs(self.write(commit='"' + "0" * 40 + '"'))
        self.assertEqual(rc, 1)
        self.assertIn("not in this repository", out)

    def test_missing_required_field(self):
        rc, out = self.errs(self.write(verdict_rationale='""'))
        self.assertEqual(rc, 1)
        self.assertIn("verdict_rationale", out)

    def test_secret_in_record_rejected(self):
        p = self.write()
        p.write_text(p.read_text() + "\napi_key = abcd1234abcd1234abcd1234\n")
        self.assertEqual(self.errs(p)[0], 1)

    def test_status_skipped_needs_skipped_label(self):
        self.assertEqual(self.errs(self.write(status='"skipped"'))[0], 1)

    def test_windows_style_backslashes_round_trip(self):
        self.call("run", "tests_all", "--task", TASK)
        p = self.records("validation")[0]["_file"]
        t = p.read_text().replace('command: "', 'command: "C:\\\\Python\\\\python.exe -m pytest -q ', 1)
        p.write_text(t)
        self.assertIn("C:\\Python\\python.exe", rg.read_record(p)[0]["command"])
        self.assertEqual(self.errs(p)[0], 0)


class CloseCheckTests(Base):
    def test_gate_never_run_is_not_closable(self):
        rc, out = self.call("close-check", "--task", TASK, "--require", "G1")
        self.assertEqual(rc, 1)
        self.assertIn("no evidence record", out)

    def test_passed_gate_closes(self):
        self.call("run", "tests_all", "--task", TASK)
        self.assertEqual(self.call("close-check", "--task", TASK, "--require", "G1")[0], 0)

    def test_failed_unavailable_and_skipped_never_close(self):
        self.call("run", "always_fail", "--task", TASK, "--gate", "GX")
        self.call("run", "dependency_consistency", "--task", TASK, "--gate", "GY")
        rc, out = self.call("close-check", "--task", TASK, "--require", "GX,GY")
        self.assertEqual(rc, 1)
        self.assertIn("status is failed", out)
        self.assertIn("status is unavailable", out)

    def test_baseline_never_closes_a_gate(self):
        self.call("baseline", "--task", TASK)
        rc, out = self.call("close-check", "--task", TASK, "--require", "G1")
        self.assertEqual(rc, 1)
        self.assertIn("no evidence record", out)

    def test_evidence_goes_stale_when_source_changes(self):
        self.call("run", "tests_all", "--task", TASK)
        (self.root / "utils/dedup.py").write_text((self.root / "utils/dedup.py").read_text() + "\n# edit\n")
        rc, out = self.call("close-check", "--task", TASK, "--require", "G1")
        self.assertEqual(rc, 1)
        self.assertIn("stale", out)

    def test_framework_files_do_not_make_evidence_stale(self):
        self.call("run", "tests_all", "--task", TASK)
        (self.fw / "MEMORY/KNOWN_ISSUES.md").write_text("x\n")
        self.assertEqual(self.call("close-check", "--task", TASK, "--require", "G1")[0], 0)

    def test_summary_lists_freshness(self):
        self.call("run", "tests_all", "--task", TASK)
        rc, out = self.call("summary", "--task", TASK)
        self.assertEqual(rc, 0)
        self.assertIn("| G1 | passed |", out)


class MustKeepTests(Base):
    def test_unchanged_passes(self):
        rc, out = self.call("mustkeep", "--base", "HEAD", "--task", TASK)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.records("validation")[0]["gate_id"], "G2")

    def test_shrink_over_limit_stops(self):
        p = self.root / "agents/evaluator.py"
        lines = p.read_text().splitlines(keepends=True)
        p.write_text("".join(lines[: len(lines) // 2]))
        rc, out = self.call("mustkeep", "--base", "HEAD", "--task", TASK)
        self.assertEqual(rc, 1)
        self.assertIn("STOP AND ASK", out)
        self.assertEqual(self.records("validation")[0]["status"], "failed")

    def test_small_change_is_reported_but_passes(self):
        p = self.root / "utils/filters.py"
        p.write_text(p.read_text() + "# one more line\n")
        rc, out = self.call("mustkeep", "--base", "HEAD", "--task", TASK)
        self.assertEqual(rc, 0)
        self.assertIn("utils/filters.py", out)

    def test_deleted_file_stops(self):
        (self.root / "utils/telegram.py").unlink()
        rc, out = self.call("mustkeep", "--base", "HEAD", "--task", TASK)
        self.assertEqual(rc, 1)
        self.assertIn("DELETED", out)

    def test_directory_entries_are_expanded(self):
        (self.root / "scanners/workday.py").unlink()
        self.assertEqual(self.call("mustkeep", "--base", "HEAD", "--task", TASK)[0], 1)

    def test_bad_base_is_usage_error(self):
        self.assertEqual(self.call("mustkeep", "--base", "nonexistent", "--task", TASK)[0], 2)


class ProtectedTests(Base):
    def test_clean_passes(self):
        self.assertEqual(self.call("protected", "--base", "HEAD", "--task", TASK)[0], 0)

    def test_governance_change_fails(self):
        p = self.root / "docs/governance/02_decision_log_and_scope.md"
        p.write_text(p.read_text() + "\nx\n")
        rc, out = self.call("protected", "--base", "HEAD", "--task", TASK)
        self.assertEqual(rc, 1)
        self.assertIn("02_decision_log_and_scope.md", out)

    def test_new_untracked_file_in_core_fails(self):
        (self.fw / "CORE/extra.md").write_text("x\n")
        self.assertEqual(self.call("protected", "--base", "HEAD", "--task", TASK)[0], 1)


class ReviewTests(Base):
    def review(self, text):
        p = self.root / "review.md"
        p.write_text(text)
        return p

    def test_valid_approved_review(self):
        self.assertEqual(self.call("validate-review", str(self.review(REVIEW_OK)))[0], 0)

    def test_approved_with_open_major_fails(self):
        t = REVIEW_OK.replace("- Severity: minor", "- Severity: major")
        rc, out = self.call("validate-review", str(self.review(t)))
        self.assertEqual(rc, 1)
        self.assertIn("critical/major", out)

    def test_missing_independence_statement_fails(self):
        t = REVIEW_OK.replace("independently re-ran", "re-ran").replace("Independent checks run", "Checks run").replace("Separate context; ", "")
        self.assertEqual(self.call("validate-review", str(self.review(t)))[0], 1)

    def test_invalid_verdict_fails(self):
        self.assertEqual(self.call("validate-review", str(self.review(REVIEW_OK.replace("approved\n", "looks fine\n"))))[0], 1)

    def test_placeholder_fails(self):
        self.assertEqual(self.call("validate-review", str(self.review(REVIEW_OK + "\n<fill me in>\n")))[0], 1)

    def test_task_writes_review_gate_record(self):
        rc, _ = self.call("validate-review", str(self.review(REVIEW_OK)), "--task", TASK)
        r = self.records("review")[0]
        self.assertEqual((rc, r["gate_id"], r["status"]), (0, "REVIEW", "passed"))
        self.assertEqual(self.call("close-check", "--task", TASK, "--require", "REVIEW")[0], 0)

    def test_conditional_verdict_does_not_close_review_gate(self):
        t = REVIEW_OK.replace("approved\n", "approved-with-conditions\n")
        rc, _ = self.call("validate-review", str(self.review(t)), "--task", TASK)
        self.assertEqual((rc, self.records("review")[0]["status"]), (1, "failed"))
        self.assertEqual(self.call("close-check", "--task", TASK, "--require", "REVIEW")[0], 1)


class UiTests(Base):
    def args(self, **kw):
        img = self.tmp / "s.png"
        png(img)
        base = {"--task": TASK, "--viewport": "390x844", "--image": str(img), "--workflow": "queue-export",
                "--result": "passed", "--tool": "manual"}
        base.update(kw)
        return [x for kv in base.items() for x in kv]

    def test_unapproved_tool_refused(self):
        rc, out = self.call("record-ui", *self.args(**{"--tool": "playwright"}))
        self.assertEqual(rc, 2)
        self.assertIn("not project-approved", out)

    def test_manual_screenshot_recorded_and_valid(self):
        rc, out = self.call("record-ui", *self.args())
        self.assertEqual(rc, 0, out)
        r = self.records("browser")[0]
        self.assertEqual((r["label"], r["gate_id"], r["viewport"]), ("screenshot-evidence", "UI-390x844", "390x844"))
        self.assertTrue((self.root / r["image_path"]).exists())
        self.assertEqual(self.call("validate-evidence", str(self.fw / "EVIDENCE" / TASK))[0], 0)

    def test_failed_result_exits_nonzero_and_does_not_close(self):
        self.assertEqual(self.call("record-ui", *self.args(**{"--result": "failed"}))[0], 1)
        self.assertEqual(self.call("close-check", "--task", TASK, "--require", "UI-390x844")[0], 1)

    def test_bad_viewport_and_missing_image(self):
        self.assertEqual(self.call("record-ui", *self.args(**{"--viewport": "mobile"}))[0], 2)
        self.assertEqual(self.call("record-ui", *self.args(**{"--image": str(self.tmp / "nope.png")}))[0], 2)

    def test_deleted_screenshot_invalidates_record(self):
        self.call("record-ui", *self.args())
        (self.root / self.records("browser")[0]["image_path"]).unlink()
        self.assertEqual(self.call("validate-evidence", str(self.fw / "EVIDENCE" / TASK))[0], 1)


class DocsGateAndBaselineTests(Base):
    def test_docs_gate_fails_on_stale_state_then_passes_when_fixed(self):
        rc, _ = self.call("docs-gate", "--task", TASK)
        self.assertEqual(rc, 1)                                   # state head_commit is not in the copy's history
        head = git("rev-parse", "HEAD", cwd=self.root)
        sp = self.fw / "MEMORY/PROJECT_STATE.yml"
        sp.write_text(re.sub(r"\b[0-9a-f]{40}\b", head, sp.read_text()))
        self.commit("fix state")
        rc, out = self.call("docs-gate", "--task", TASK)
        self.assertEqual(rc, 0, out)

    def test_docs_gate_fails_on_unregistered_file(self):
        (self.root / "utils/new_util.py").write_text('"""x"""\n')
        rc, out = self.call("docs-gate", "--task", TASK)
        self.assertEqual(rc, 1)
        self.assertIn("unregistered maintained file", out)

    def test_baseline_records_tests_and_git_state(self):
        rc, _ = self.call("baseline", "--task", TASK)
        gates = {r["gate_id"] for r in self.records("baseline")}
        self.assertEqual((rc, gates), (0, {"G1", "BASELINE-GIT"}))


if __name__ == "__main__":
    unittest.main(verbosity=1)
