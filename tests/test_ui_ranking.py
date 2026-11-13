"""Ranking is pure and deterministic. Synthetic data only."""
from jobhunter_ui import ranking as R


def ev(url, score, skills=3, rec="apply", date="2026-01-01", at="2026-01-02", **kw):
    return {"url": url, "success": True, "global_score": score, "recommendation": rec, "date_posted": date,
            "evaluated_at": at, "scores": {"skills_match": skills, "education_match": 3, "location": 3,
                                           "language": 3, "growth": 3}, **kw}


def test_orders_by_score_then_skills_then_recency():
    rows = R.rank([ev("https://a/1", 4.0, skills=3), ev("https://a/2", 4.0, skills=5),
                   ev("https://a/3", 4.5), ev("https://a/4", 4.0, skills=5, date="2026-02-01")])
    assert [r["url"] for r in rows] == ["https://a/3", "https://a/4", "https://a/2", "https://a/1"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4]


def test_german_rejected_scores_zero_and_ranks_last():
    rows = R.rank([ev("https://a/1", 4.9, rec="skip_german"), ev("https://a/2", 2.0)])
    assert rows[-1]["url"] == "https://a/1" and rows[-1]["score"] == 0 and rows[-1]["tier"] == "excluded"


def test_latest_evaluation_per_url_wins_and_failures_ignored():
    rows = R.rank([ev("https://a/1", 2.0, at="2026-01-01"), ev("https://a/1", 4.0, at="2026-03-01"),
                   {**ev("https://a/2", 5.0), "success": False}, {"success": True, "global_score": 5}])
    assert len(rows) == 1 and rows[0]["score"] == 4.0


def test_custom_weights_rerank_but_default_keeps_original_scores():
    a = ev("https://a/a", 4.0, skills=1); a["scores"]["growth"] = 5
    b = ev("https://a/b", 3.0, skills=5); b["scores"]["growth"] = 1
    assert [r["url"] for r in R.rank([a, b])] == ["https://a/a", "https://a/b"]
    only_skills = R.parse_weights({"skills_match": 100})
    rows = R.rank([a, b], only_skills)
    assert [r["url"] for r in rows] == ["https://a/b", "https://a/a"] and rows[0]["score"] == 5.0


def test_parse_weights_rejects_garbage():
    d = R.DEFAULT_WEIGHTS
    assert R.parse_weights("") == d and R.parse_weights({"skills_match": -1}) == d
    assert R.parse_weights({"skills_match": 0, "growth": 0}) == d
    assert R.parse_weights("skills_match:abc,bogus:5") == d
    w = R.parse_weights("skills_match:50,growth:50")
    assert w["skills_match"] == 50 and w["location"] == 0


def test_tiers_and_missing_scores():
    assert R.tier(4.2, 3.5) == "top" and R.tier(3.6, 3.5) == "good" and R.tier(2.0, 3.5) == "weak"
    rows = R.rank([{"url": "https://a/x", "success": True}])
    assert rows[0]["score"] == 0.0


def test_job_id_stable():
    assert R.job_id("https://a/1") == R.job_id("https://a/1") != R.job_id("https://a/2")
    assert len(R.job_id("x")) == 12
