"""Tests for install_framework.py. Run: python -I .ai-engineering/SCRIPTS/bootstrap/test_install_framework.py
Installs the framework into throw-away toy projects (not JobHunter) and drives the real checkers there.
Label: automated-test. Linux only; says nothing about Windows, macOS or any real second project."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FW = HERE.parents[1]
INSTALL = HERE / "install_framework.py"


def sh(cwd, *cmd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


class Toy(unittest.TestCase):
    DIRNAME = "toy"

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aef-install-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.toy = self.tmp / self.DIRNAME
        self.toy.mkdir()
        (self.toy / "app.py").write_text('"""Tiny calculator used by the install tests."""\n\n\ndef add(a, b):\n    return a + b\n', encoding="utf-8")
        for c in (("init", "-q", "-b", "main"), ("config", "user.email", "t@t"), ("config", "user.name", "t"), ("add", "-A"), ("commit", "-q", "-m", "toy")):
            sh(self.toy, "git", *c)

    def install(self, *extra):
        return sh(self.toy, sys.executable, str(INSTALL), "--target", str(self.toy), "--name", "Toy Project", *extra)

    def tool(self, rel, *args):
        return sh(self.toy, sys.executable, "-I", str(self.toy / ".ai-engineering/SCRIPTS" / rel), *args)

    def fill_purposes(self):
        reg = self.toy / ".ai-engineering/DOCUMENTATION/FILE_REGISTRY.yml"
        reg.write_text(reg.read_text(encoding="utf-8").replace("purpose: null", 'purpose: "written by a person in the test"'), encoding="utf-8")


class InstallTests(Toy):
    def test_fresh_install_passes_state_and_adapter_checks(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        for rel in ("AGENTS.md", "GEMINI.md", ".ai-engineering/CORE/engineering_constitution.md", ".ai-engineering/CONFIG/project_profile.yml",
                    ".ai-engineering/MEMORY/PROJECT_STATE.yml", ".ai-engineering/SCRIPTS/validation/run_gates.py"):
            self.assertTrue((self.toy / rel).exists(), rel)
        self.assertEqual(self.tool("memory/check_memory.py", "state")[0], 0)
        rc, out = self.tool("adapters/check_adapters.py", "check")
        self.assertEqual(rc, 0, out)
        self.assertIn("kiro=not_run", out)

    def test_nothing_is_guessed_and_framework_tests_are_not_copied(self):
        self.install()
        prof = (self.toy / ".ai-engineering/CONFIG/project_profile.yml").read_text(encoding="utf-8")
        self.assertIn("type: pending_owner", prof)
        self.assertNotIn("python", prof.lower().split("languages:")[1].split("\n")[0])
        self.assertEqual(list((self.toy / ".ai-engineering").rglob("test_*.py")), [])
        self.assertFalse((self.toy / ".ai-engineering/SCRIPTS/stress").exists())
        agents = (self.toy / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("docs/governance", agents)
        self.assertNotIn("JobHunter", agents)

    def test_registry_refuses_to_invent_purposes_then_passes_when_a_person_writes_them(self):
        (self.toy / "helper.py").write_text("def f():\n    return 1\n", encoding="utf-8")        # no docstring: nothing to derive a purpose from
        sh(self.toy, "git", "add", "-A")
        sh(self.toy, "git", "commit", "-q", "-m", "helper")
        self.install()
        rc, out = self.tool("documentation/check_registry.py", "check")
        self.assertEqual(rc, 1, out)
        self.assertIn("helper.py: required field 'purpose'", out)
        self.assertNotIn("app.py: required field 'purpose'", out)               # app.py has a docstring, so its purpose was derived
        self.fill_purposes()
        rc, out = self.tool("documentation/check_registry.py", "check")
        self.assertEqual(rc, 0, out)

    def test_refuses_to_overwrite_an_installation(self):
        self.install()
        rc, out = self.install()
        self.assertEqual(rc, 1)
        self.assertIn("already exists", out)

    def test_force_keeps_project_state_and_configuration(self):
        self.install()
        prof = self.toy / ".ai-engineering/CONFIG/project_profile.yml"
        prof.write_text(prof.read_text(encoding="utf-8").replace("type: pending_owner", "type: web-service"), encoding="utf-8")
        (self.toy / ".ai-engineering/CORE/definition_of_done.md").write_text("tampered", encoding="utf-8")
        rc, out = self.install("--force")
        self.assertEqual(rc, 0, out)
        self.assertIn("type: web-service", prof.read_text(encoding="utf-8"))
        self.assertNotEqual((self.toy / ".ai-engineering/CORE/definition_of_done.md").read_text(encoding="utf-8"), "tampered")
        self.assertIn("KEPT existing CONFIG/project_profile.yml", out)

    def test_existing_agent_files_are_never_overwritten(self):
        (self.toy / "AGENTS.md").write_bytes(b"# Our own rules\r\nUse tabs.\r\n")
        (self.toy / "GEMINI.md").write_text("# mine\n", encoding="utf-8")
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.toy / "AGENTS.md").read_bytes(), b"# Our own rules\r\nUse tabs.\r\n")
        self.assertEqual((self.toy / "GEMINI.md").read_text(encoding="utf-8"), "# mine\n")
        self.assertTrue((self.toy / "AGENTS.md.aef-proposed").exists())
        self.assertIn("merge AGENTS.md.aef-proposed", out)
        rc, out = self.tool("adapters/check_adapters.py", "check")            # their files lack the pointers: must be flagged
        self.assertEqual(rc, 1, out)
        self.assertIn("does not point to", out)

    def test_target_must_be_a_directory(self):
        rc, out = sh(self.tmp, sys.executable, str(INSTALL), "--target", str(self.tmp / "missing"), "--name", "x")
        self.assertEqual(rc, 2)

    def test_start_gate_fails_closed_without_a_task_board(self):
        self.install()
        rc, out = self.tool("memory/check_memory.py", "start", "--task", "WP-00-01")
        self.assertEqual(rc, 1, out)
        self.assertIn("task board", out)

    def test_gates_work_outside_the_original_project(self):
        self.install()
        cp = self.toy / ".ai-engineering/CONFIG/command_profiles.yml"
        t = cp.read_text(encoding="utf-8")
        t = t.replace('run: null\n    status: "unavailable_until:configured"', 'run: "python -c \\"print(\'1 passed\')\\""\n    status: exists')
        cp.write_text(t, encoding="utf-8")
        gates = self.toy / ".ai-engineering/SCRIPTS/validation/run_gates.py"
        self.assertEqual(sh(self.toy, sys.executable, "-I", str(gates), "run", "tests_all", "--task", "FW-X", "--area", "validation")[0], 0)
        rc, out = sh(self.toy, sys.executable, "-I", str(gates), "close-check", "--task", "FW-X", "--require", "G1")
        self.assertEqual(rc, 0, out)
        rc, out = sh(self.toy, sys.executable, "-I", str(gates), "close-check", "--task", "FW-X", "--require", "G1,G12")
        self.assertEqual(rc, 1, out)


class UnusualPathTests(Toy):
    DIRNAME = "toy project \u00e9\u00e8 \u65e5\u672c"

    def test_install_and_checks_in_a_path_with_spaces_and_non_ascii_characters(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.tool("memory/check_memory.py", "state")[0], 0)
        self.assertEqual(self.tool("adapters/check_adapters.py", "check")[0], 0)
        self.fill_purposes()
        rc, out = self.tool("documentation/check_registry.py", "check")
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
