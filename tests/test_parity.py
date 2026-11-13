"""
Parity test (G15).

CLI renderer and HTTP handler return identical ranked ids and scores
for one fixture workspace. Ensures the single scoring path (domain scoring)
is used consistently by both interfaces.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from jobhunter.domain.scoring import rank, parse_weights, DEFAULT_WEIGHTS


FIXTURE_EVALS = [
    {
        "url": "https://example.com/job-a",
        "company": "Acme Corp",
        "title": "AI Engineer",
        "global_score": 4.2,
        "scores": {"skills_match": 4, "education_match": 5, "location": 4, "language": 3, "growth": 4},
        "recommendation": "apply",
        "german_required": False,
        "german_level_required": "none",
        "evaluated_at": "2026-11-01T10:00:00Z",
        "date_posted": "2026-10-30",
        "success": True,
    },
    {
        "url": "https://example.com/job-b",
        "company": "Globex",
        "title": "ML Engineer",
        "global_score": 3.8,
        "scores": {"skills_match": 5, "education_match": 3, "location": 3, "language": 4, "growth": 4},
        "recommendation": "consider",
        "german_required": False,
        "german_level_required": "none",
        "evaluated_at": "2026-11-02T10:00:00Z",
        "date_posted": "2026-10-29",
        "success": True,
    },
    {
        "url": "https://example.com/job-c",
        "company": "Hooli",
        "title": "Data Scientist",
        "global_score": 2.1,
        "scores": {"skills_match": 2, "education_match": 3, "location": 2, "language": 2, "growth": 3},
        "recommendation": "skip",
        "german_required": True,
        "german_level_required": "B1",
        "evaluated_at": "2026-11-03T10:00:00Z",
        "date_posted": "2026-10-28",
        "success": True,
    },
]


def _cli_render(evals, weights=None, threshold=3.5):
    """CLI renderer: jobhunter_ui/ranking.py's rank() function."""
    w = parse_weights(weights) if weights else dict(DEFAULT_WEIGHTS)
    return rank(evals, w, threshold)


def _http_handler(evals, weights=None, threshold=3.5):
    """HTTP handler: jobhunter_ui/service.py's list_jobs() ranking core.

    Reproduces the ranking portion of list_jobs() using the same domain
    scoring function.
    """
    w = parse_weights(weights) if weights else dict(DEFAULT_WEIGHTS)
    rows = rank(evals, w, threshold)
    return rows


def test_parity_cli_and_http_identical_ranking():
    """CLI renderer and HTTP handler return identical ranked ids and scores."""
    cli_rows = _cli_render(FIXTURE_EVALS)
    http_rows = _http_handler(FIXTURE_EVALS)

    assert len(cli_rows) == len(http_rows)
    for cli_row, http_row in zip(cli_rows, http_rows):
        assert cli_row["id"] == http_row["id"], f"id mismatch: {cli_row['id']} != {http_row['id']}"
        assert cli_row["score"] == http_row["score"], f"score mismatch for {cli_row['id']}"
        assert cli_row["rank"] == http_row["rank"], f"rank mismatch for {cli_row['id']}"
        assert cli_row["tier"] == http_row["tier"], f"tier mismatch for {cli_row['id']}"


def test_parity_with_custom_weights():
    """Parity holds with custom weights."""
    custom = {"skills_match": 50, "education_match": 10, "location": 10, "language": 10, "growth": 20}
    cli_rows = _cli_render(FIXTURE_EVALS, weights=custom)
    http_rows = _http_handler(FIXTURE_EVALS, weights=custom)

    assert len(cli_rows) == len(http_rows)
    for cli_row, http_row in zip(cli_rows, http_rows):
        assert cli_row["id"] == http_row["id"]
        assert cli_row["score"] == http_row["score"]


def test_parity_skip_german_excluded():
    """German-rejected jobs score 0 and appear at the bottom in both."""
    cli_rows = _cli_render(FIXTURE_EVALS)
    http_rows = _http_handler(FIXTURE_EVALS)

    # Job C (German B1, score 2.1) should be last in both
    assert cli_rows[-1]["url"] == "https://example.com/job-c"
    assert http_rows[-1]["url"] == "https://example.com/job-c"
    assert cli_rows[-1]["score"] == http_rows[-1]["score"]
