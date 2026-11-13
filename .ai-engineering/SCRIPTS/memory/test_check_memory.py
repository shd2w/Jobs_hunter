"""Tests for check_memory.py. Run:  python -I .ai-engineering/SCRIPTS/memory/test_check_memory.py
Each test builds a throw-away Git repository holding a copy of the framework and the
governance documents, introduces ONE deliberate violation and asserts it is detected.
All results are 'automated-test' evidence; the CLI-switch scenario is a SIMULATION
(two sequential script invocations), not a run through two real coding CLIs."""
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_memory as cm  # noqa: E402

REAL_FW = HERE.parents[1]
REAL_ROOT = REAL_FW.parent
GOOD_HANDOFF = """# Handoff Record

## Identification
- **Task:** WP-00-01 - Reproducible installs
- **Work package:** WP-00-01
- **Date/time:** 2026-11-10T10:00:00+02:00
- **Agent:** test-cli / model-a
- **Trigger:** quota reached

## Repository state
- **Branch:** {branch}
- **Base branch:** phase/00-foundations
- **HEAD commit:** {head}
- **Git status summary:**
  ```
  {status}
  ```

## File changes
### Committed
- none

### Uncommitted (staged)
- none

### Uncommitted (unstaged)
- none

### Untracked
{untracked}

## Implementation progress
### Completed steps
1. Baseline captured: `.ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt`

### Remaining scope
1. Lock file

## Validation state
### Baseline (pre-change)
- **Command:** python -m pytest -q
- **Result:** 1 passed
- **Evidence:** `.ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt`

### Gate status
| Gate | Status | Evidence |
|---|---|---|
| G1 | passed | `.ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt` |
| G7 | unavailable | install command not defined until WP-00-01 merges |

## Last verified checkpoint
- **What was verified:** baseline
- **What was NOT verified:** lock install
- **Verification evidence:** `.ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt`

## Blockers and open items
- none

## Unresolved questions
- none

## Pending decisions
- PCD-018: assumed accepted (default)

## Required approvals
- none

## Failed approaches
1. **Approach:** none
   **Result:** n/a
   **Why it failed:** n/a
   **Evidence:** n/a

## Documentation status
### Updated
- none

### Still pending
- registry

## Exact next actions
1. Run `python -m pytest -q`
   **Expected outcome:** 1 passed

## Recovery instructions
tree clean, nothing interrupted
"""


def run(*a, cwd):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "repo"
        self.root.mkdir()
        shutil.copytree(REAL_FW, self.root / ".ai-engineering",
                        ignore=shutil.ignore_patterns("__pycache__", "EVIDENCE", "handoffs"))
        shutil.copytree(REAL_ROOT / "docs" / "governance", self.root / "docs" / "governance")
        shutil.copy(REAL_ROOT / "docs" / "PROMPT.md", self.root / "docs" / "PROMPT.md")
        (self.root / ".ai-engineering/EVIDENCE/WP-00-01/baseline").mkdir(parents=True)
        (self.root / ".ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt").write_text("1 passed\n")
        (self.root / ".ai-engineering/MEMORY/handoffs").mkdir(exist_ok=True)
        run("git", "init", "-q", "-b", "wp/WP-00-01-x", cwd=self.root)
        run("git", "config", "user.email", "t@example.invalid", cwd=self.root)
        run("git", "config", "user.name", "t", cwd=self.root)
        self.commit("init")
        self.fw = self.root / ".ai-engineering"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, msg):
        run("git", "add", "-A", cwd=self.root)
        run("git", "commit", "-q", "--allow-empty", "-m", msg, cwd=self.root)

    def head(self):
        return run("git", "rev-parse", "HEAD", cwd=self.root)

    def state_findings(self):
        return [m for s, m in cm.check_state(self.fw).items if s == "error"]

    def set_state(self, old, new):
        p = self.fw / "MEMORY/PROJECT_STATE.yml"
        t = p.read_text()
        self.assertIn(old, t)
        p.write_text(t.replace(old, new))

    def handoff(self, **kw):
        d = self.fw / "MEMORY/handoffs/WP-00-01"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "20261110-100000_test-cli.md"
        body = GOOD_HANDOFF.format(
            branch=kw.get("branch", "wp/WP-00-01-x"), head=kw.get("head", self.head()),
            status=kw.get("status", ""), untracked=kw.get("untracked", "- none"))
        for a, b in kw.get("replace", []):
            self.assertIn(a, body)
            body = body.replace(a, b)
        f.write_text(body)
        return f

    def hf_errors(self, f, git=True):
        return [m for s, m in cm.check_handoff(self.fw, f, git).items if s == "error"]


class StateTests(Base):
    def test_valid_state_passes(self):
        self.set_state("branch: docs/governance-suite", "branch: wp/WP-00-01-x")
        self.set_state("head_commit: 00d6a5f5b9b8e0ba4be9d2a9ab91ffe55e0ed072", f"head_commit: {self.head()}")
        self.set_state("  commit: 00d6a5f5b9b8e0ba4be9d2a9ab91ffe55e0ed072", f"  commit: {self.head()}")
        self.assertEqual(self.state_findings(), [])

    def test_unknown_head_commit_detected(self):
        self.assertTrue(any("not a commit" in m for m in self.state_findings()))

    def test_stale_task_reference(self):
        self.set_state("active_task: null ", "active_task: WP-99-99 ")
        self.assertTrue(any("stale task reference WP-99-99" in m for m in self.state_findings()))

    def test_active_task_disagrees_with_current_task(self):
        self.set_state("active_task: null ", "active_task: WP-00-01 ")
        self.assertTrue(any("CURRENT_TASK.md says" in m for m in self.state_findings()))

    def test_stale_handoff_directory(self):
        (self.fw / "MEMORY/handoffs/WP-98-98").mkdir()
        self.assertTrue(any("WP-98-98" in m for m in self.state_findings()))

    def test_missing_required_key(self):
        self.set_state("project: JobHunter\n", "")
        self.assertTrue(any("missing required key 'project'" in m for m in self.state_findings()))

    def test_suite_document_changed(self):
        p = self.root / "docs/governance/02_decision_log_and_scope.md"
        p.write_text(p.read_text() + "\nextra\n")
        errs = self.state_findings()
        self.assertTrue(any("GOV-02" in m and "changed" in m for m in errs))

    def test_missing_index_file(self):
        (self.fw / "MEMORY/KNOWN_ISSUES.md").unlink()
        self.assertTrue(any("known_issues" in m for m in self.state_findings()))


class HandoffTests(Base):
    def test_valid_handoff_passes_with_git(self):
        self.assertEqual(self.hf_errors(self.handoff()), [])

    def test_template_matches_schema(self):
        t = (self.fw / "WORKFLOW/handoff_template.md").read_text()
        schema = cm.load_yaml(self.fw / "QUALITY/checkpoint_schema.yml")
        self.assertEqual(list(cm.sections(t)), schema["handoff"]["required_sections"])

    def test_unfilled_template_rejected(self):
        d = self.fw / "MEMORY/handoffs/WP-00-01"
        d.mkdir(parents=True)
        f = d / "20261110-100000_x.md"
        shutil.copy(self.fw / "WORKFLOW/handoff_template.md", f)
        errs = self.hf_errors(f, git=False)
        self.assertTrue(any("placeholder" in m for m in errs))

    def test_missing_section(self):
        f = self.handoff(replace=[("## Recovery instructions\ntree clean, nothing interrupted\n", "")])
        self.assertTrue(any("missing section '## Recovery instructions'" in m for m in self.hf_errors(f)))

    def test_missing_field(self):
        f = self.handoff(replace=[("- **Trigger:** quota reached", "- **Trigger:** ")])
        self.assertTrue(any("'Trigger' missing" in m for m in self.hf_errors(f)))

    def test_secret_detected(self):
        f = self.handoff(replace=[("- none\n\n## Unresolved", "- api_key = abcd1234abcd1234abcd1234\n\n## Unresolved")])
        self.assertTrue(any("secret" in m for m in self.hf_errors(f)))

    def test_passed_gate_without_evidence(self):
        f = self.handoff(replace=[("| G1 | passed | `.ai-engineering/EVIDENCE/WP-00-01/baseline/t.txt` |", "| G1 | passed | n/a |")])
        self.assertTrue(any("without evidence" in m for m in self.hf_errors(f)))

    def test_skipped_counted_as_passed_style_status_rejected(self):
        f = self.handoff(replace=[("| G7 | unavailable |", "| G7 | mostly-passed |")])
        self.assertTrue(any("mostly-passed" in m for m in self.hf_errors(f)))

    def test_missing_evidence_file(self):
        (self.fw / "EVIDENCE/WP-00-01/baseline/t.txt").unlink()
        self.assertTrue(any("evidence path does not exist" in m for m in self.hf_errors(self.handoff())))

    def test_stale_work_package(self):
        f = self.handoff(replace=[("**Work package:** WP-00-01", "**Work package:** WP-77-77")])
        self.assertTrue(any("WP-77-77" in m for m in self.hf_errors(f)))

    def test_handoff_disagrees_with_git_head(self):
        f = self.handoff()
        self.commit("later commit by someone else")
        errs = self.hf_errors(f)
        self.assertTrue(any("!= actual HEAD" in m for m in errs), errs)

    def test_handoff_wrong_branch(self):
        errs = self.hf_errors(self.handoff(branch="wp/WP-00-02-other"))
        self.assertTrue(any("handoff branch" in m for m in errs))

    def test_unexpected_user_change(self):
        f = self.handoff()
        (self.root / "agents").mkdir()
        (self.root / "agents/new.py").write_text("x=1\n")
        errs = self.hf_errors(f)
        self.assertTrue(any("unexpected change not in handoff" in m and "agents/new.py" in m for m in errs), errs)

    def test_claimed_change_not_in_git(self):
        f = self.handoff(untracked="- agents/ghost.py: new module")
        errs = self.hf_errors(f)
        self.assertTrue(any("ghost.py" in m for m in errs), errs)

    def test_declared_untracked_file_accepted(self):
        (self.root / "agents").mkdir()
        (self.root / "agents/new.py").write_text("x=1\n")
        f = self.handoff(untracked="- agents/new.py: new module", status="?? agents/new.py")
        self.assertEqual(self.hf_errors(f), [])

    def test_simulated_cli_switch_resume(self):
        """SIMULATION of spec 6.2/9.3: agent A hands off dirty; user commits; agent B must detect, reconcile, pass."""
        (self.root / "agents").mkdir()
        (self.root / "agents/new.py").write_text("x=1\n")
        f = self.handoff(untracked="- agents/new.py: new module", status="?? agents/new.py")
        self.assertEqual(self.hf_errors(f), [])                      # A leaves a valid handoff
        self.commit("owner commits A's work by hand")
        self.assertTrue(self.hf_errors(f))                           # B's cold check refuses to trust it
        f2 = self.handoff(head=self.head())                          # B re-verifies and rewrites it
        self.assertEqual(self.hf_errors(f2), [])


class CliTests(Base):
    def test_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cm.main(["--framework-dir", str(self.fw), "state"]), 1)   # head_commit unknown in copy
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cm.main(["--framework-dir", str(self.tmp / "nope"), "state"]), 2)


class SubsetParserTests(unittest.TestCase):
    def test_subset_parser_reads_state_files_like_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed: parity not checkable (reported as skipped, not passed)")
        for rel in ("MEMORY/PROJECT_STATE.yml", "QUALITY/checkpoint_schema.yml"):
            t = (REAL_FW / rel).read_text(encoding="utf-8")
            self.assertEqual(cm.parse_yaml_subset(t), yaml.safe_load(t), rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
