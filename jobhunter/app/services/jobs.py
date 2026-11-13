"""Jobs service — pending jobs and check-state over pipeline.md."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from jobhunter.app.result import Err, Ok, Result

logger = logging.getLogger(__name__)


def get_pending_jobs(pipeline_path: str = "data/pipeline.md") -> Result[list[dict]]:
    """Parse pipeline.md and return unchecked jobs ranked by recency (newest first)."""
    path = Path(pipeline_path)
    if not path.exists():
        return Ok([])

    text = path.read_text(encoding="utf-8")
    jobs: list[dict] = []

    # Match: - [ ] URL | Company | Title [Location]
    pattern = r"- \[ \] (https?://\S+)\s*\|\s*([^|]+)\s*\|\s*(.+?)(?:\s*\[([^\]]*)\])?\s*$"
    for match in re.finditer(pattern, text, re.MULTILINE):
        url, company, title, location = match.groups()
        jobs.append(
            {
                "url": url,
                "company": company.strip(),
                "title": title.strip(),
                "location": (location or "").strip(),
                "source": "pipeline",
            }
        )

    jobs.sort(key=lambda j: j.get("date_posted") or "0000-00-00", reverse=True)
    return Ok(jobs)


def mark_checked(url: str, pipeline_path: str = "data/pipeline.md") -> Result[None]:
    """Mark a job as checked in pipeline.md ([ ] -> [x])."""
    path = Path(pipeline_path)
    if not path.exists():
        return Ok(None)

    text = path.read_text(encoding="utf-8")
    escaped_url = re.escape(url)
    new_text = re.sub(
        rf"- \[ \] {escaped_url}",
        f"- [x] {url}",
        text,
    )
    if new_text == text:
        logger.warning(f"URL not found in pipeline.md: {url}")
        return Err(error=f"URL not found: {url}", code="not_found")

    path.parent.mkdir(parents=True, exist_ok=True)
    import os
    import tempfile

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

    return Ok(None)
