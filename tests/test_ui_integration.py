"""REAL original CVTailor, CoverLetterWriter and WeasyPrint PDF code; only the AI network call (SmartRouter) is faked."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_ui_service import EXAMPLE_CV, URL, make_ws, jid

weasyprint = pytest.importorskip("weasyprint")

PATCH = {"subtitle": "Backend Engineer | Working-Student Candidate", "objective": "Student engineer.",
         "skills_order": ["Tools", "Languages"],
         "experience_bullets": {"Student Assistant": ["Maintained a Python data pipeline", "Wrote tests for nightly runs"]},
         "projects_to_keep": ["Budget Tracker"], "projects_to_remove": []}


class FakeRouter:
    calls = []
    def __init__(self, *a, **k): pass
    def generate(self, system_prompt, user_prompt, **k):
        FakeRouter.calls.append(user_prompt)
        body = "```json\n" + json.dumps(PATCH) + "\n```" if "CV tailoring" in system_prompt else "Dear Acme team,\n\nI would like to apply.\n\nKind regards,\nJane"
        return SimpleNamespace(success=True, content=body, model_used="fake-model", error="")


def real_ws(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.cv_tailor.SmartRouter", FakeRouter)
    monkeypatch.setattr("agents.cover_letter.SmartRouter", FakeRouter)
    return make_ws(tmp_path, monkeypatch, tailor_factory=None, cover_factory=None, pdf_cv=None, pdf_cover=None)


def test_real_tailor_and_pdf_pipeline(tmp_path, monkeypatch):
    ws = real_ws(tmp_path, monkeypatch)
    d = ws.create_cv(jid(ws), "tailored")
    pdf = tmp_path / d["artifacts"]["cv"]["pdf"]
    assert pdf.read_bytes()[:5] == b"%PDF-" and pdf.stat().st_size > 1500
    text = (tmp_path / d["artifacts"]["cv"]["md"]).read_text(encoding="utf-8")
    assert "Backend Engineer" in text and "Maintained a Python data pipeline" in text
    # facts the AI must never change stay byte-identical (education + languages sections)
    for fixed in ("**B.Sc. in Computer Science**", "*2022 – 2026 (Expected)*", "* **German:** Intermediate"):
        assert fixed in text
    assert "Great job description" in FakeRouter.calls[-1]  # JD text reaches the model
    assert (tmp_path / "cv.md").read_text(encoding="utf-8") == EXAMPLE_CV  # original CV untouched


def test_real_cover_letter_pdf(tmp_path, monkeypatch):
    ws = real_ws(tmp_path, monkeypatch)
    d = ws.create_cover(jid(ws))
    assert (tmp_path / d["artifacts"]["cover"]["pdf"]).read_bytes()[:5] == b"%PDF-"
    assert "Dear Acme team" in (tmp_path / d["artifacts"]["cover"]["md"]).read_text(encoding="utf-8")


def test_real_base_cv_pdf(tmp_path, monkeypatch):
    ws = real_ws(tmp_path, monkeypatch)
    d = ws.create_cv(jid(ws), "base")
    assert (tmp_path / d["artifacts"]["cv"]["pdf"]).read_bytes()[:5] == b"%PDF-"
