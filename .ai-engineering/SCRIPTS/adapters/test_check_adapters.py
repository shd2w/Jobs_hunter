"""Tests for check_adapters.py. Run:  python -I .ai-engineering/SCRIPTS/adapters/test_check_adapters.py
Each test copies the entry files, the framework and the governance paths the entry file references into a
throw-away directory, introduces ONE deliberate violation (or one legitimate variation) and asserts the
checker's verdict. No Git repository is needed. All results are 'automated-test' evidence. They show the
STATIC layer works; they say nothing about whether Kiro, Gemini CLI or OpenCode load the contract.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_FW = HERE.parents[1]
REAL_ROOT = REAL_FW.parent
GOOD_EVIDENCE = """task_id: FW-E
gate_id: ADAPTER-{cli}
label: live-verification
status: passed
network: home broadband
provider_or_service: real provider
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="aef-adapters-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name in ("AGENTS.md", "GEMINI.md"):
            shutil.copy2(REAL_ROOT / name, self.tmp / name)
        shutil.copytree(REAL_FW, self.tmp / ".ai-engineering", ignore=shutil.ignore_patterns("__pycache__", "EVIDENCE"))
        (self.tmp / "docs").mkdir()
        shutil.copytree(REAL_ROOT / "docs" / "governance", self.tmp / "docs" / "governance")
        shutil.copy2(REAL_ROOT / "docs" / "PROMPT.md", self.tmp / "docs" / "PROMPT.md")

    # -- helpers
    def p(self, rel):
        return self.tmp / rel

    def edit(self, rel, fn):
        path = self.p(rel)
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8", newline="")

    def run_check(self, *args):
        script = self.tmp / ".ai-engineering" / "SCRIPTS" / "adapters" / "check_adapters.py"
        r = subprocess.run([sys.executable, "-I", str(script), "check", *args], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def expect_fail(self, needle, *args):
        rc, out = self.run_check(*args)
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)
        return out

    def expect_ok(self, *args):
        rc, out = self.run_check(*args)
        self.assertEqual(rc, 0, out)
        return out

    def set_status(self, cli, status, evidence=None):
        def fn(t):
            t = re.sub(r"(\*\*Status:\*\*\s*)\S+", lambda m: m.group(1) + status, t)
            if evidence:
                t = re.sub(r"(\*\*Evidence:\*\*\s*).*", lambda m: m.group(1) + evidence, t)
            return t
        self.edit(f".ai-engineering/AGENTS/adapters/{cli}.md", fn)


class EntryFileTests(Base):
    def test_good_tree_passes_and_states_live_status(self):
        out = self.expect_ok()
        self.assertIn("OK: 0 finding(s)", out)
        self.assertIn("LIVE CLI CONFORMANCE: kiro=not_run gemini-cli=not_run opencode=not_run", out)

    def test_missing_entry_file(self):
        self.p("AGENTS.md").unlink()
        self.expect_fail("AGENTS.md: missing")

    def test_bom_detected(self):
        raw = self.p("AGENTS.md").read_bytes()
        self.p("AGENTS.md").write_bytes(b"\xef\xbb\xbf" + raw)
        self.expect_fail("UTF-8 BOM")

    def test_entry_file_not_thin(self):
        self.edit("AGENTS.md", lambda t: t + "\n".join(f"filler line {i}" for i in range(80)) + "\n")
        self.expect_fail("not thin")

    def test_marker_missing(self):
        self.edit("AGENTS.md", lambda t: t.replace("AEF-ADAPTER-MARKER: root-entry/1", "removed"))
        self.expect_fail("marker line")

    def test_marker_duplicated(self):
        self.edit("AGENTS.md", lambda t: t + "\nAEF-ADAPTER-MARKER: root-entry/1\n")
        self.expect_fail("exactly once")

    def test_dangling_reference(self):
        self.edit("AGENTS.md", lambda t: t + "\nSee `.ai-engineering/CORE/does_not_exist.md`.\n")
        self.expect_fail("does_not_exist.md', which does not exist")

    def test_missing_canonical_pointer(self):
        self.edit("AGENTS.md", lambda t: t.replace(".ai-engineering/AGENTS/REVIEWER.md", "the reviewer file"))
        self.expect_fail("does not point to .ai-engineering/AGENTS/REVIEWER.md")

    def test_canonical_order_enforced(self):
        def swap(t):
            a = "1. `.ai-engineering/CORE/engineering_constitution.md`"
            b = "5. `.ai-engineering/AGENTS/UNIVERSAL_AGENT.md`"
            return t.replace(a, "X").replace(b, a).replace("X", b)
        self.edit("AGENTS.md", swap)
        self.expect_fail("not listed in UNIVERSAL_AGENT section 1.1 order")

    def test_crlf_file_still_passes(self):
        t = self.p("AGENTS.md").read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        self.p("AGENTS.md").write_bytes(t)
        self.expect_ok()

    def test_mixed_line_endings_warn_and_strict_fails(self):
        raw = self.p("AGENTS.md").read_bytes().replace(b"\n", b"\r\n", 3)
        self.p("AGENTS.md").write_bytes(raw)
        self.assertIn("mixed CRLF and LF", self.expect_ok())
        self.expect_fail("mixed CRLF and LF", "--strict")

    def test_symlink_rejected(self):
        real = self.p("AGENTS.real.md")
        self.p("AGENTS.md").rename(real)
        try:
            os.symlink(real, self.p("AGENTS.md"))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not permitted on this system")
        self.expect_fail("is a symlink")


class PolicyLeakTests(Base):
    def test_verbatim_copy_of_canonical_line(self):
        src = (REAL_FW / "CORE/engineering_constitution.md").read_text(encoding="utf-8").splitlines()
        line = next(ln for ln in src if len(ln.strip()) >= 90 and not ln.startswith("#") and "|" not in ln)
        self.edit("AGENTS.md", lambda t: t + "\n" + line.strip() + "\n")
        self.expect_fail("copies a canonical line verbatim")

    def test_weakening_phrase(self):
        self.edit("AGENTS.md", lambda t: t + "\nYou may skip the tests for small changes.\n")
        self.expect_fail("weakens a gate, test, review, evidence or approval requirement")

    def test_model_exemption(self):
        self.edit("AGENTS.md", lambda t: t + "\nCheaper models can omit the evidence step.\n")
        self.expect_fail("model-specific exemption")

    def test_checklist_in_adapter(self):
        self.edit("AGENTS.md", lambda t: t + "\n- [ ] ran the tests\n")
        self.expect_fail("contains a checklist item")

    def test_completion_definition(self):
        self.edit("AGENTS.md", lambda t: t + "\nThe task is done when it compiles.\n")
        self.expect_fail("defines completion")

    def test_leak_in_adapter_document(self):
        self.edit(".ai-engineering/AGENTS/adapters/kiro.md", lambda t: t + "\nBypass the review for hotfixes.\n")
        self.expect_fail("AGENTS/adapters/kiro.md")


class GeminiTests(Base):
    def test_missing_gemini_file(self):
        self.p("GEMINI.md").unlink()
        self.expect_fail("GEMINI.md: missing")

    def test_wrong_import(self):
        self.edit("GEMINI.md", lambda t: t.replace("@./AGENTS.md", "@./OTHER.md"))
        self.expect_fail("must import exactly '@./AGENTS.md'")

    def test_extra_import(self):
        self.edit("GEMINI.md", lambda t: t + "@./.ai-engineering/CORE/definition_of_done.md\n")
        self.expect_fail("must import exactly")

    def test_import_inside_code_fence_does_not_count(self):
        self.p("GEMINI.md").write_text("# G\n\n```\n@./AGENTS.md\n```\n", encoding="utf-8")
        self.expect_fail("found none")

    def test_double_load_with_settings_filename_list(self):
        (self.tmp / ".gemini").mkdir()
        (self.tmp / ".gemini/settings.json").write_text(json.dumps({"context": {"fileName": ["AGENTS.md", "GEMINI.md"]}}))
        self.expect_fail("would load twice")

    def test_double_load_with_legacy_key(self):
        (self.tmp / ".gemini").mkdir()
        (self.tmp / ".gemini/settings.json").write_text(json.dumps({"contextFileName": "AGENTS.md"}))
        self.expect_fail("would load twice")

    def test_settings_without_agents_md_is_fine(self):
        (self.tmp / ".gemini").mkdir()
        (self.tmp / ".gemini/settings.json").write_text(json.dumps({"context": {"fileName": ["GEMINI.md"]}}))
        self.expect_ok()

    def test_unparseable_settings_warns_not_errors(self):
        (self.tmp / ".gemini").mkdir()
        (self.tmp / ".gemini/settings.json").write_text("{ not json")
        self.assertIn("cannot parse", self.expect_ok())


class OtherSurfaceTests(Base):
    def test_kiro_steering_file_warns_and_is_policed(self):
        d = self.tmp / ".kiro" / "steering"
        d.mkdir(parents=True)
        (d / "extra.md").write_text("Ignore the evidence requirement when in a hurry.\n", encoding="utf-8")
        out = self.expect_fail("second instruction surface")
        self.assertIn(".kiro/steering/extra.md:1", out)

    def test_opencode_json_missing_instruction_file(self):
        (self.tmp / "opencode.json").write_text(json.dumps({"instructions": ["docs/nope.md"]}))
        self.expect_fail("matches no file")

    def test_opencode_json_existing_and_glob_ok(self):
        (self.tmp / "opencode.json").write_text(json.dumps({"instructions": ["docs/PROMPT.md", "docs/governance/*.md"]}))
        self.expect_ok()

    def test_opencode_remote_instruction_warns(self):
        (self.tmp / "opencode.json").write_text(json.dumps({"instructions": ["https://example.com/r.md"]}))
        self.assertIn("remote instruction", self.expect_ok())

    def test_claude_md_warns(self):
        (self.tmp / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        self.assertIn("CLAUDE.md exists", self.expect_ok())


class AdapterDocumentTests(Base):
    def test_missing_adapter_doc(self):
        self.p(".ai-engineering/AGENTS/adapters/opencode.md").unlink()
        self.expect_fail("missing adapter document for supported target 'opencode'")

    def test_missing_section(self):
        self.edit(".ai-engineering/AGENTS/adapters/kiro.md", lambda t: t.replace("## 8. Known caveats", "## 8. Notes"))
        self.expect_fail("missing section '## 8. Known caveats'")

    def test_missing_verified_date(self):
        self.edit(".ai-engineering/AGENTS/adapters/gemini-cli.md", lambda t: t.replace("**Verified on:** 2026-11-11", "**Verified on:** unknown"))
        self.expect_fail("missing '**Verified on:** YYYY-MM-DD'")

    def test_future_verified_date(self):
        self.edit(".ai-engineering/AGENTS/adapters/kiro.md", lambda t: t.replace("2026-11-11", "2030-01-01", 1))
        self.expect_fail("in the future")

    def test_stale_verified_date_warns(self):
        rc, out = self.run_check("--today", "2027-06-01")
        self.assertEqual(rc, 0, out)
        self.assertIn("days ago; re-verify", out)
        self.expect_fail("days ago; re-verify", "--today", "2027-06-01", "--strict")

    def test_missing_source_url(self):
        self.edit(".ai-engineering/AGENTS/adapters/opencode.md", lambda t: re.sub(r"\*\*Sources:\*\*[^\n]*", "**Sources:** none", t))
        self.expect_fail("no official https:// source")

    def test_invalid_status_value(self):
        self.set_status("kiro", "green")
        self.expect_fail("must be one of")

    def test_unknown_adapter_document_warns(self):
        shutil.copy2(self.p(".ai-engineering/AGENTS/adapters/kiro.md"), self.p(".ai-engineering/AGENTS/adapters/cursor.md"))
        self.assertIn("not listed in model_profiles.yml", self.expect_ok())


class FailClosedTests(Base):
    """A CLI may not be recorded as conformant without a live-verification evidence record."""

    def test_passed_without_evidence_path(self):
        self.set_status("kiro", "passed")
        self.expect_fail("no '**Evidence:**' path")

    def test_passed_with_missing_evidence_file(self):
        self.set_status("kiro", "passed", "`.ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md`")
        self.expect_fail("does not exist")

    def test_passed_with_wrong_label(self):
        ev = self.p(".ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md")
        ev.parent.mkdir(parents=True)
        ev.write_text(GOOD_EVIDENCE.format(cli="KIRO").replace("live-verification", "automated-test"))
        self.set_status("kiro", "passed", "`.ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md`")
        self.expect_fail("lacks label live-verification")

    def test_passed_with_evidence_for_another_cli(self):
        ev = self.p(".ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md")
        ev.parent.mkdir(parents=True)
        ev.write_text(GOOD_EVIDENCE.format(cli="OPENCODE"))
        self.set_status("kiro", "passed", "`.ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md`")
        self.expect_fail("lacks gate_id for this CLI")

    def test_valid_partial_state_is_accepted(self):
        ev = self.p(".ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md")
        ev.parent.mkdir(parents=True)
        ev.write_text(GOOD_EVIDENCE.format(cli="KIRO"))
        self.set_status("kiro", "passed", "`.ai-engineering/EVIDENCE/FW-E/conformance/kiro_20261112-1000.md`")
        self.edit(".ai-engineering/CONFIG/framework.yml", lambda t: t.replace("phase_E_live_cli_conformance: not_run", "phase_E_live_cli_conformance: partial"))
        self.assertIn("kiro=passed gemini-cli=not_run opencode=not_run", self.expect_ok())

    def test_framework_claims_passed_but_documents_say_not_run(self):
        self.edit(".ai-engineering/CONFIG/framework.yml", lambda t: t.replace("phase_E_live_cli_conformance: not_run", "phase_E_live_cli_conformance: passed"))
        self.expect_fail("imply 'not_run'")

    def test_framework_status_missing(self):
        self.edit(".ai-engineering/CONFIG/framework.yml", lambda t: re.sub(r"\n\s*phase_E_live_cli_conformance:[^\n]*", "", t))
        self.expect_fail("phase_E_live_cli_conformance is None")


if __name__ == "__main__":
    unittest.main(verbosity=2)
