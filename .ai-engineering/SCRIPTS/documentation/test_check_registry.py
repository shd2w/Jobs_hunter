"""Tests for check_registry.py. Run:  python -I .ai-engineering/SCRIPTS/documentation/test_check_registry.py
Each test copies the repository (tracked files + .ai-engineering) into a throw-away Git repo,
introduces ONE deliberate violation and asserts the checker reports it. Label: automated-test."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_registry as cr  # noqa: E402

REAL_FW = HERE.parents[1]
REAL_ROOT = REAL_FW.parent


def run(*a, cwd):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "repo"
        tracked = run("git", "ls-files", cwd=REAL_ROOT).splitlines()
        for rel in tracked:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REAL_ROOT / rel, dst)
        shutil.copytree(REAL_FW, self.root / ".ai-engineering", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
        run("git", "init", "-q", "-b", "main", cwd=self.root)
        run("git", "config", "user.email", "t@example.invalid", cwd=self.root)
        run("git", "config", "user.name", "t", cwd=self.root)
        self.commit("init")
        self.fw = self.root / ".ai-engineering"
        self.freg = self.fw / "DOCUMENTATION/FILE_REGISTRY.yml"
        self.ftreg = self.fw / "DOCUMENTATION/FEATURE_REGISTRY.yml"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, msg):
        run("git", "add", "-A", cwd=self.root)
        run("git", "commit", "-q", "--allow-empty", "-m", msg, cwd=self.root)

    def errors(self, since=None):
        return [m for s, m in cr.check(self.fw, since).items if s == "error"]

    def warns(self):
        return [m for s, m in cr.check(self.fw).items if s == "warn"]

    def edit(self, path, old, new, count=1):
        t = path.read_text(encoding="utf-8")
        self.assertIn(old, t)
        path.write_text(t.replace(old, new, count), encoding="utf-8")


class RegistryTests(Base):
    def test_baseline_has_no_errors(self):
        self.assertEqual(self.errors(), [])

    def test_unregistered_new_file(self):
        (self.root / "utils/new_util.py").write_text('"""New."""\n')
        self.assertTrue(any("unregistered maintained file: utils/new_util.py" in m for m in self.errors()))

    def test_entry_for_deleted_file(self):
        (self.root / "utils/telegram.py").unlink()
        self.assertTrue(any("utils/telegram.py" in m and "does not exist" in m for m in self.errors()))

    def test_missing_required_field(self):
        t = self.freg.read_text(encoding="utf-8")
        t = re.sub(r'(  - path: "utils/dedup.py"\n    type: "py"\n)    purpose: "[^"]*"\n', r"\1", t, count=1)
        self.freg.write_text(t, encoding="utf-8")
        self.assertTrue(any("utils/dedup.py" in m and "'purpose'" in m for m in self.errors()))

    def test_generated_path_registered(self):
        self.freg.write_text(self.freg.read_text(encoding="utf-8") + '''  - path: "__pycache__/x.pyc"
    type: "pyc"
    purpose: "cache"
    component: "x"
    classification: "S0"
    status: "active"
    provenance: "generated-unreviewed"
    entry_sha256: "00"
''', encoding="utf-8")
        self.assertTrue(any("excluded/generated path registered" in m for m in self.errors()))

    def test_runtime_data_is_not_a_maintained_file(self):
        (self.root / "data").mkdir()
        (self.root / "data/jobs.json").write_text("[]")
        self.assertEqual(self.errors(), [])

    def test_changed_file_warns_only(self):
        p = self.root / "utils/dedup.py"
        p.write_text(p.read_text() + "\n# change\n")
        self.assertEqual(self.errors(), [])
        self.assertTrue(any("utils/dedup.py" in m and "changed since" in m for m in self.warns()))

    def test_refresh_clears_stale_warning(self):
        p = self.root / "utils/dedup.py"
        p.write_text(p.read_text() + "\n# change\n")
        self.assertEqual(cr.cmd_refresh(self.fw, ["utils/dedup.py"]), 0)
        self.assertFalse([m for m in self.warns() if "utils/dedup.py" in m])

    def test_scan_write_adds_skeleton_and_never_overwrites(self):
        (self.root / "utils/new_util.py").write_text('"""New helper."""\nimport os\n')
        before = self.freg.read_text(encoding="utf-8")
        cr.cmd_scan(self.fw, True)
        after = self.freg.read_text(encoding="utf-8")
        self.assertIn('path: "utils/new_util.py"', after)
        self.assertIn('provenance: "generated-unreviewed"', after)
        self.assertTrue(after.startswith(before.rstrip("\n")[:2000]))   # existing entries untouched
        self.assertEqual(self.errors(), [])


class FeatureTests(Base):
    def test_unknown_work_package(self):
        self.edit(self.ftreg, '"WP-01-07"', '"WP-99-99"')
        self.assertTrue(any("WP-99-99" in m for m in self.errors()))

    def test_unknown_decision(self):
        self.edit(self.ftreg, '"DEC-033"', '"DEC-999"')
        self.assertTrue(any("DEC-999" in m for m in self.errors()))

    def test_missing_test_file(self):
        (self.root / "tests/test_dedup.py").unlink()
        errs = self.errors()
        self.assertTrue(any("test_dedup.py" in m and "does not exist" in m for m in errs), errs)

    def test_feature_file_not_registered(self):
        self.edit(self.ftreg, '"utils/filters.py"', '"utils/ghost.py"')
        self.assertTrue(any("utils/ghost.py is not registered" in m for m in self.errors()))

    def test_not_bidirectional(self):
        t = self.freg.read_text(encoding="utf-8")
        m = re.search(r'(  - path: "utils/filters.py".*?\n)(    features: \[[^\]]*\]\n)', t, re.S)
        self.assertIsNotNone(m, "filters.py entry must carry a features field")
        self.freg.write_text(t.replace(m.group(2), "", 1), encoding="utf-8")
        self.assertTrue(any("not bidirectional" in x for x in self.errors()))

    def test_feature_doc_missing(self):
        (self.fw / "DOCUMENTATION/features/F-01_scan-filter-dedup.md").unlink()
        self.assertTrue(any("F-01" in m and "does not exist" in m for m in self.errors()))

    def test_feature_doc_missing_heading(self):
        self.edit(self.fw / "DOCUMENTATION/features/F-02_ai-scoring-evaluation.md", "## Security and privacy", "## Security")
        self.assertTrue(any("F-02" in m and "Security and privacy" in m for m in self.errors()))

    def test_feature_without_tests_warns_not_errors(self):
        self.assertTrue(any("F-03" in m and "no tests" in m for m in self.warns()))
        self.assertFalse(any("F-03" in m and "no tests" in m for m in self.errors()))


class ChangeSetTests(Base):
    def test_added_file_without_registry_update(self):
        (self.root / "utils/new_util.py").write_text('"""New."""\n')
        self.commit("add file only")
        self.assertTrue(any("change set A utils/new_util.py" in m for m in self.errors(since="HEAD~1")))

    def test_added_file_with_registry_update_passes_change_set_rule(self):
        (self.root / "utils/new_util.py").write_text('"""New."""\n')
        cr.cmd_scan(self.fw, True)
        self.commit("add file and registry")
        self.assertFalse([m for m in self.errors(since="HEAD~1") if "change set" in m])

    def test_deleted_file_without_registry_update(self):
        (self.root / "utils/telegram.py").unlink()
        self.commit("delete only")
        self.assertTrue(any("change set D utils/telegram.py" in m for m in self.errors(since="HEAD~1")))


class TraceTests(Base):
    def test_trace_file_feature_and_wp(self):
        import contextlib
        import io
        for key, expect in (("agents/cv_tailor.py", "F-04"), ("F-04", "agents/cv_tailor.py"), ("WP-09-01", "F-04")):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cr.cmd_trace(self.fw, key)
            self.assertEqual(rc, 0, key)
            self.assertIn(expect, out.getvalue(), key)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertNotEqual(cr.cmd_trace(self.fw, "no/such/file.py"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
