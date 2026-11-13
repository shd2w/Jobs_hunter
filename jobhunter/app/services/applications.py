"""Applications service — application queue over evaluations.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from jobhunter.app.result import Err, Ok, Result

logger = logging.getLogger(__name__)


class ApplicationsService:
    """Manages the application queue from evaluations."""

    def __init__(self, evaluations_path: str = "data/evaluations.json"):
        self.evaluations_path = Path(evaluations_path)

    def export_queue(self, output_path: str = "data/application_queue.jsonl") -> Result[None]:
        """Export evaluated jobs to the application queue (JSONL).

        Only jobs with a score >= threshold and recommendation != skip_german
        are included.
        """
        if not self.evaluations_path.exists():
            return Err(error="No evaluations found", code="no_evaluations")

        try:
            data = json.loads(self.evaluations_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return Err(error=f"Failed to read evaluations: {exc}", code="read_failed")

        if not isinstance(data, list):
            return Err(error="Evaluations file is not a list", code="invalid_format")

        profile = _load_profile()
        threshold = float(profile.get("evaluation", {}).get("auto_cv_threshold", 3.5))

        queue_lines: list[str] = []
        for ev in data:
            if not isinstance(ev, dict) or not ev.get("success", True):
                continue
            score = float(ev.get("global_score", 0) or 0)
            recommendation = ev.get("recommendation", "")
            if score < threshold or recommendation == "skip_german":
                continue
            line = {
                "url": ev.get("url", ""),
                "company": ev.get("company", ""),
                "title": ev.get("title", ""),
                "score": score,
                "recommendation": recommendation,
                "cv_pdf_path": ev.get("cv_pdf_path", ""),
                "cover_letter_pdf_path": ev.get("cover_letter_pdf_path", ""),
            }
            queue_lines.append(json.dumps(line, ensure_ascii=False))

        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(queue_lines) + ("\n" if queue_lines else ""), encoding="utf-8")
        except OSError as exc:
            return Err(error=f"Failed to write queue: {exc}", code="write_failed")

        logger.info(f"Exported {len(queue_lines)} jobs to {output_path}")
        return Ok(None)


def _load_profile() -> dict:
    path = Path("config/profile.yml")
    if not path.exists():
        return {}
    try:
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}
