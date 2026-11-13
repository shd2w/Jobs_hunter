"""
Unit tests for the Result[T] type and application services (WP-02-02).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jobhunter.app.result import Err, Ok, Result, err, ok, is_err, is_ok


class TestResultType:
    def test_ok_is_ok(self):
        r = Ok(value=42)
        assert is_ok(r)
        assert not is_err(r)
        assert r.value == 42

    def test_err_is_err(self):
        r = Err(error="something failed", code="fail")
        assert is_err(r)
        assert not is_ok(r)
        assert r.error == "something failed"
        assert r.code == "fail"

    def test_ok_helper(self):
        r = ok("hello")
        assert isinstance(r, Ok)
        assert r.value == "hello"

    def test_err_helper(self):
        r = err("boom", code="boom_code")
        assert isinstance(r, Err)
        assert r.error == "boom"
        assert r.code == "boom_code"

    def test_result_union(self):
        def divide(a: float, b: float) -> Result[float]:
            if b == 0:
                return err("division by zero", code="div_zero")
            return ok(a / b)

        r1 = divide(10, 2)
        assert is_ok(r1)
        assert r1.value == 5.0

        r2 = divide(10, 0)
        assert is_err(r2)
        assert r2.error == "division by zero"
        assert r2.code == "div_zero"


class TestJobsService:
    def test_get_pending_jobs_empty_file(self, tmp_path):
        from jobhunter.app.services.jobs import get_pending_jobs

        pipeline = tmp_path / "pipeline.md"
        pipeline.write_text("# Job Pipeline\n\n## Pending\n\n## Processed\n", encoding="utf-8")
        result = get_pending_jobs(str(pipeline))
        assert is_ok(result)
        assert result.value == []

    def test_get_pending_jobs_with_jobs(self, tmp_path):
        from jobhunter.app.services.jobs import get_pending_jobs

        pipeline = tmp_path / "pipeline.md"
        pipeline.write_text(
            "# Job Pipeline\n\n## Pending\n\n"
            "- [ ] https://example.com/job1 | Acme | AI Engineer [Remote]\n"
            "- [ ] https://example.com/job2 | Globex | ML Engineer [Berlin]\n"
            "- [x] https://example.com/job3 | Hooli | Senior Engineer [Munich]\n"
            "## Processed\n",
            encoding="utf-8",
        )
        result = get_pending_jobs(str(pipeline))
        assert is_ok(result)
        assert len(result.value) == 2
        assert result.value[0]["url"] == "https://example.com/job1"
        assert result.value[0]["company"] == "Acme"
        assert result.value[0]["title"] == "AI Engineer"
        assert result.value[0]["location"] == "Remote"

    def test_mark_checked(self, tmp_path):
        from jobhunter.app.services.jobs import get_pending_jobs, mark_checked

        pipeline = tmp_path / "pipeline.md"
        pipeline.write_text(
            "# Job Pipeline\n\n## Pending\n\n"
            "- [ ] https://example.com/job1 | Acme | AI Engineer [Remote]\n"
            "## Processed\n",
            encoding="utf-8",
        )

        # Mark as checked
        result = mark_checked("https://example.com/job1", str(pipeline))
        assert is_ok(result)

        # Verify it's marked
        result = get_pending_jobs(str(pipeline))
        assert is_ok(result)
        assert len(result.value) == 0


class TestEvaluationService:
    def test_evaluation_service_init(self):
        from jobhunter.app.services.evaluation import EvaluationService

        with patch("jobhunter.app.services.evaluation.Evaluator") as mock_eval:
            mock_eval.return_value = MagicMock()
            svc = EvaluationService()
            assert svc.evaluator is not None
            assert svc.jd_cache is not None
            assert svc.german_policy == "accept_all"

    def test_evaluation_service_custom_policy(self):
        from jobhunter.app.services.evaluation import EvaluationService

        with patch("jobhunter.app.services.evaluation.Evaluator") as mock_eval:
            mock_eval.return_value = MagicMock()
            svc = EvaluationService(german_policy="reject_b1_plus")
            assert svc.german_policy == "reject_b1_plus"


class TestApplicationsService:
    def test_export_queue_no_evaluations(self, tmp_path):
        from jobhunter.app.services.applications import ApplicationsService

        svc = ApplicationsService(evaluations_path=str(tmp_path / "evals.json"))
        result = svc.export_queue(output_path=str(tmp_path / "queue.jsonl"))
        assert is_err(result)
        assert result.code == "no_evaluations"

    def test_export_queue_with_evaluations(self, tmp_path):
        from jobhunter.app.services.applications import ApplicationsService

        import json

        evals = tmp_path / "evals.json"
        evals.write_text(
            json.dumps([
                {"url": "https://example.com/job1", "company": "Acme",
                 "title": "AI Engineer", "global_score": 4.0,
                 "recommendation": "apply", "success": True}
            ]),
            encoding="utf-8",
        )
        svc = ApplicationsService(evaluations_path=str(evals))
        output = tmp_path / "queue.jsonl"
        result = svc.export_queue(output_path=str(output))
        assert is_ok(result)

        content = output.read_text(encoding="utf-8")
        assert "AI Engineer" in content
        assert "Acme" in content


class TestHealthService:
    def test_health_check(self):
        from jobhunter.app.services.health import HealthService

        svc = HealthService()
        result = svc.check()
        assert is_ok(result)
        report = result.value
        assert "status" in report
        assert "checks" in report
        assert "python" in report["checks"]
        assert report["checks"]["python"]["ok"] is True
