"""Service layer with FAKE AI, PDF and Telegram (no network). Mocked: results are not live-AI verification."""
import json
import os
from pathlib import Path

import pytest
import yaml

from jobhunter_ui.service import ActionError, Workspace
from utils import queue_exporter

EXAMPLE_CV = (Path(__file__).parent.parent / "jobhunter_ui" / "static" / "cv.example.md").read_text(encoding="utf-8")
URL = "https://example.com/jobs/123"


class FakeTailor:
    def __init__(self, cv_path, output_dir):
        self.out = Path(output_dir)

    def tailor(self, job):
        p = self.out / "jane_acme_engineer-cv.md"
        p.parent.mkdir(exist_ok=True)
        p.write_text("# tailored for " + job["company"], encoding="utf-8")
        FakeTailor.seen = job
        return {"success": True, "output_path": str(p), "content": "# tailored", "subtitle": "Engineer"}


class FakeCover:
    def __init__(self, cv_path, output_dir):
        self.out = Path(output_dir)

    def generate(self, job, evaluation=None):
        p = self.out / "acme-engineer-cover.md"
        p.write_text("Dear team", encoding="utf-8")
        return {"success": True, "output_path": str(p), "content": "Dear team"}


def fake_pdf(md_content, output_path, **kw):
    Path(output_path).parent.mkdir(exist_ok=True)
    Path(output_path).write_bytes(b"%PDF-1.4 fake")
    return {"success": True, "output_path": output_path}


class FakeTG:
    def __init__(self): FakeTG.sent = []
    def send_document(self, path, caption=""):
        FakeTG.sent.append(path); return True


def make_ws(tmp_path, monkeypatch, *, ai=True, cv=True, desc="Great job description " * 5, **over):
    monkeypatch.chdir(tmp_path)
    for k in ("OpenRouter", "OpenRouter2", "OpenRouter3", "OpenRouter4", "GOOGLE_AI_API_KEY",
              "GOOGLE_AI_API_KEY2", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(k, raising=False)
    if ai:
        monkeypatch.setenv("GOOGLE_AI_API_KEY", "AIzaRealLookingKey123456")
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "profile.yml").write_text(yaml.safe_dump(
        {"candidate": {"full_name": "Jane Example", "short_name": "Jane Example"},
         "evaluation": {"auto_cv_threshold": 3.5, "german_filter": "accept_all"}}), encoding="utf-8")
    if cv:
        (tmp_path / "cv.md").write_text(EXAMPLE_CV, encoding="utf-8")
    ev = {"success": True, "url": URL, "company": "Acme", "title": "Engineer", "global_score": 4.2,
          "recommendation": "apply", "german_required": False, "german_level_required": "none",
          "scores": {"skills_match": 4, "education_match": 4, "location": 4, "language": 5, "growth": 4},
          "evaluated_at": "2026-10-01T10:00:00", "date_posted": "2026-09-30", "summary": "s"}
    (tmp_path / "data" / "evaluations.json").write_text(json.dumps([ev]), encoding="utf-8")
    (tmp_path / "data" / "jd_cache.json").write_text(json.dumps({URL: {"description": desc, "title": "Engineer", "company": "Acme"}}), encoding="utf-8")
    kw = dict(tailor_factory=FakeTailor, cover_factory=FakeCover, telegram_factory=FakeTG, pdf_cv=fake_pdf, pdf_cover=fake_pdf)
    kw.update(over)
    return Workspace(tmp_path, **kw)


def jid(ws): return ws.list_jobs()["jobs"][0]["id"]


def test_tailored_cv_creates_files_and_updates_record(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    d = ws.create_cv(jid(ws), "tailored")
    assert d["artifacts"]["cv"]["kind"] == "tailored" and d["artifacts"]["cv"]["pdf"].endswith("-cv.pdf")
    assert (tmp_path / d["artifacts"]["cv"]["pdf"]).read_bytes().startswith(b"%PDF")
    assert FakeTailor.seen["description"].startswith("Great job")
    rec = json.loads((tmp_path / "data/evaluations.json").read_text())[0]
    assert rec["cv_pdf_path"].endswith("-cv.pdf") and rec["tailored_at"] and rec["global_score"] == 4.2
    assert d["warnings"] == []


def test_missing_description_warns(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, desc="", jd_fetcher=lambda u: "")
    assert any("description" in w for w in ws.create_cv(jid(ws), "tailored")["warnings"])


def test_base_cv_needs_no_ai(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, ai=False)
    d = ws.create_cv(jid(ws), "base")
    assert d["artifacts"]["cv"]["kind"] == "base" and d["artifacts"]["cv"]["pdf"] == "output/base-cv.pdf"


def test_base_cv_prefers_existing_cv_pdf(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, ai=False)
    (tmp_path / "cv.pdf").write_bytes(b"%PDF-mine")
    assert ws.create_cv(jid(ws), "base")["artifacts"]["cv"]["pdf"] == "cv.pdf"
    assert (tmp_path / "cv.pdf").read_bytes() == b"%PDF-mine"  # original never modified


def test_errors_are_plain_and_actionable(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, ai=False)
    with pytest.raises(ActionError) as e: ws.create_cv(jid(ws), "tailored")
    assert e.value.code == "no_ai"
    with pytest.raises(ActionError) as e: ws.create_cover(jid(ws))
    assert e.value.code == "no_ai"
    with pytest.raises(ActionError) as e: ws.create_cv(jid(ws), "weird")
    assert e.value.code == "bad_mode"
    with pytest.raises(ActionError) as e: ws.create_cv("0" * 12, "base")
    assert e.value.code == "not_found"
    sub = tmp_path / "x"
    sub.mkdir()
    ws2 = make_ws(sub, monkeypatch, cv=False)
    with pytest.raises(ActionError) as e: ws2.create_cv(jid(ws2), "base")
    assert e.value.code == "no_cv"


def test_ai_failure_is_reported_and_state_untouched(tmp_path, monkeypatch):
    class Bad(FakeTailor):
        def tailor(self, job): return {"success": False, "error": "rate limited"}
    ws = make_ws(tmp_path, monkeypatch, tailor_factory=Bad)
    before = (tmp_path / "data/evaluations.json").read_text()
    with pytest.raises(ActionError) as e: ws.create_cv(jid(ws), "tailored")
    assert e.value.code == "ai_failed" and "rate limited" in e.value.message
    assert (tmp_path / "data/evaluations.json").read_text() == before
    assert not ws._busy  # lock released after failure


def test_pdf_failure_keeps_text_and_warns(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, pdf_cv=lambda **k: {"success": False, "error": "no pango"})
    d = ws.create_cv(jid(ws), "tailored")
    assert d["artifacts"]["cv"]["md"] and not d["artifacts"]["cv"]["pdf"] and any("PDF" in w for w in d["warnings"])


def test_cover_and_queue_export_end_to_end(tmp_path, monkeypatch):
    """After one-click CV + letter, the ORIGINAL queue exporter emits the job (contract preserved)."""
    ws = make_ws(tmp_path, monkeypatch)
    i = jid(ws)
    ws.create_cv(i, "tailored")
    d = ws.create_cover(i)
    assert d["artifacts"]["cover"]["pdf"].endswith("-cover.pdf")
    out = tmp_path / "data/application_queue.jsonl"
    summary = queue_exporter.export_queue(output_path=out, evaluations_path=tmp_path / "data/evaluations.json",
                                          pipeline_path=tmp_path / "data/pipeline.md",
                                          profile_path=tmp_path / "config/profile.yml")
    assert summary["exported"] == 1, summary
    row = json.loads(out.read_text().splitlines()[0])
    assert row["cv_pdf"].endswith("-cv.pdf") and row["cover_letter_pdf"].endswith("-cover.pdf")


def test_without_clicking_queue_skips_job(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    summary = queue_exporter.export_queue(output_path=tmp_path / "q.jsonl", evaluations_path=tmp_path / "data/evaluations.json",
                                          pipeline_path=tmp_path / "data/pipeline.md", profile_path=tmp_path / "config/profile.yml")
    assert summary["exported"] == 0 and summary["skipped"] == 1


def test_status_note_roundtrip_and_validation(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    i = jid(ws)
    d = ws.set_status(i, "applied", "sent on Monday")
    assert d["status"] == "applied" and d["note"] == "sent on Monday"
    assert ws.list_jobs(status="applied")["shown"] == 1 and ws.list_jobs(status="new")["shown"] == 0
    with pytest.raises(ActionError): ws.set_status(i, "bogus")
    with pytest.raises(ActionError): ws.set_status(i, None, "x" * 2001)


def test_filters(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    assert ws.list_jobs(min_score=4.5)["shown"] == 0 and ws.list_jobs(min_score=4.0)["shown"] == 1
    assert ws.list_jobs(q="acme")["shown"] == 1 and ws.list_jobs(q="zzz")["shown"] == 0
    assert ws.list_jobs(rec=["skip"])["shown"] == 0 and ws.list_jobs(only_ready=True)["shown"] == 0


def test_save_cv_validates_and_backs_up(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    with pytest.raises(ActionError) as e: ws.save_cv("just some words")
    assert e.value.code == "bad_format"
    assert ws.save_cv(EXAMPLE_CV + "\n* extra")["ok"] is True
    assert (tmp_path / "cv.md.bak").read_text(encoding="utf-8") == EXAMPLE_CV
    with pytest.raises(ActionError): ws.save_cv("x" * 300_000)


def test_cv_status_flags_missing_sections(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    assert ws.cv_status()["ok"] is True
    (tmp_path / "cv.md").write_text("# **A**\n\n## **EDUCATION**\n\nx\n", encoding="utf-8")
    st = ws.cv_status()
    assert st["ok"] is False and "EXPERIENCE" in st["missing"]


def test_keys_saved_without_leaking_and_unknown_rejected(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, ai=False)
    (tmp_path / ".env").write_text("# my notes\nOTHER=1\nOpenRouter=old\n", encoding="utf-8")
    st = ws.save_keys({"GOOGLE_AI_API_KEY": "AIzaNewSecretValue99", "OpenRouter": ""})
    blob = json.dumps(st)
    assert "AIzaNewSecretValue99" not in blob and st["ai"]["configured"] is True
    env = (tmp_path / ".env").read_text()
    assert "# my notes" in env and "OTHER=1" in env and "GOOGLE_AI_API_KEY=AIzaNewSecretValue99" in env and "OpenRouter=" not in env
    for bad in ({"EVIL": "x"}, {"GOOGLE_AI_API_KEY": "a b"}, {"GOOGLE_AI_API_KEY": "a\nb=c"}):
        with pytest.raises(ActionError): ws.save_keys(bad)


def test_placeholder_keys_do_not_count(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch, ai=False)
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "AIza-your-first-key")
    assert ws.ai_configured() is False


def test_profile_save_validates_and_backs_up(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    st = ws.save_profile({"auto_cv_threshold": "4", "german_filter": "reject_b1_plus", "create_cv": True, "email": "a@b.c"})
    assert st["profile"]["auto_cv_threshold"] == 4.0 and st["profile"]["create_cv"] is True
    assert (tmp_path / "config/profile.yml.bak").exists()
    for bad in ({"auto_cv_threshold": 9}, {"auto_cv_threshold": "x"}, {"german_filter": "nope"}, {"email": "a\nb"}):
        with pytest.raises(ActionError): ws.save_profile(bad)


def test_servable_blocks_traversal_and_private_files(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    (tmp_path / "output").mkdir(exist_ok=True)
    (tmp_path / "output/ok.pdf").write_bytes(b"x")
    (tmp_path / ".env").write_text("OpenRouter=secret")
    assert ws.servable("output/ok.pdf")
    for bad in (".env", "../.env", "output/../.env", "data/evaluations.json", "config/profile.yml", "/etc/passwd", "output/missing.pdf"):
        assert ws.servable(bad) is None, bad
    outside = tmp_path.parent / "outside.txt"; outside.write_text("x")
    try:
        os.symlink(outside, tmp_path / "output/link.txt")
        assert ws.servable("output/link.txt") is None
    except OSError:
        pass


def test_telegram_requires_setup_and_artifacts(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    with pytest.raises(ActionError) as e: ws.send_telegram(jid(ws))
    assert e.value.code == "no_telegram"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:RealTokenValue"); monkeypatch.setenv("TELEGRAM_CHAT_ID", "98765")
    with pytest.raises(ActionError) as e: ws.send_telegram(jid(ws))
    assert e.value.code == "nothing_to_send"
    ws.create_cv(jid(ws), "tailored")
    assert len(ws.send_telegram(jid(ws))["sent"]) == 1


def test_concurrent_click_is_rejected(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    ws._busy.add(f"cv:{jid(ws)}")
    with pytest.raises(ActionError) as e: ws.create_cv(jid(ws), "base")
    assert e.value.status == 409
