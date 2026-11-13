"""Deterministic job ranking over stored evaluations (pure functions, no I/O)."""
from __future__ import annotations

import hashlib

DIMENSIONS = ("skills_match", "education_match", "location", "language", "growth")
# Same weights as the evaluator prompt (agents/evaluator.py): 30/20/20/20/10.
DEFAULT_WEIGHTS = {"skills_match": 0.30, "education_match": 0.20, "location": 0.20,
                   "language": 0.20, "growth": 0.10}


def job_id(url: str) -> str:
    return hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:12]


def parse_weights(raw) -> dict[str, float]:
    """Accept dict or 'skills_match:30,location:10' text. Unknown/negative values are ignored.
    Falls back to defaults when nothing usable or all zero."""
    out: dict[str, float] = {}
    if isinstance(raw, str):
        pairs = []
        for part in raw.split(","):
            if ":" in part:
                k, v = part.split(":", 1)
                pairs.append((k.strip(), v.strip()))
        raw = dict(pairs)
    for k, v in (raw or {}).items():
        if k in DIMENSIONS:
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f >= 0 and f == f and f != float("inf"):
                out[k] = f
    if not out or sum(out.values()) <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: out.get(k, 0.0) for k in DIMENSIONS}


def is_default(weights: dict[str, float]) -> bool:
    tot = sum(weights.values()) or 1
    return all(abs(weights.get(k, 0) / tot - DEFAULT_WEIGHTS[k]) < 1e-9 for k in DIMENSIONS)


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def score_of(ev: dict, weights: dict[str, float]) -> float:
    """Score on the 1-5 scale. German-rejected jobs always score 0 (as the original pipeline does).
    Default weights -> the stored global_score (original behaviour); custom weights -> recomputed."""
    if ev.get("recommendation") == "skip_german":
        return 0.0
    stored = _num(ev.get("global_score"))
    if is_default(weights):
        return round(max(0.0, min(5.0, stored)), 1) if stored is not None else 0.0
    scores = ev.get("scores") or {}
    num = den = 0.0
    for k, w in weights.items():
        s = _num(scores.get(k))
        if s is not None and w > 0:
            num += s * w
            den += w
    if den == 0:
        return round(stored, 1) if stored is not None else 0.0
    return round(max(0.0, min(5.0, num / den)), 1)


def tier(score: float, threshold: float) -> str:
    if score >= max(threshold, 4.0):
        return "top"
    if score >= threshold:
        return "good"
    if score > 0:
        return "weak"
    return "excluded"


def rank(evals: list[dict], weights: dict[str, float] | None = None, threshold: float = 3.5) -> list[dict]:
    """Return one row per URL (latest evaluation wins), ranked best first.
    Order: score desc, skills_match desc, date_posted desc, evaluated_at desc, url (stable)."""
    weights = parse_weights(weights) if weights is not None else dict(DEFAULT_WEIGHTS)
    latest: dict[str, dict] = {}
    for ev in evals:
        if not isinstance(ev, dict) or not ev.get("success", True):
            continue
        url = ev.get("url") or ""
        if not url:
            continue
        prev = latest.get(url)
        if prev is None or str(ev.get("evaluated_at", "")) >= str(prev.get("evaluated_at", "")):
            latest[url] = ev
    rows = []
    for url, ev in latest.items():
        sc = score_of(ev, weights)
        rows.append({"id": job_id(url), "url": url, "ev": ev, "score": sc,
                     "original_score": _num(ev.get("global_score")),
                     "tier": tier(sc, threshold)})
    rows.sort(key=lambda r: r["url"])
    rows.sort(key=lambda r: str(r["ev"].get("evaluated_at", "")), reverse=True)
    rows.sort(key=lambda r: str(r["ev"].get("date_posted", "") or ""), reverse=True)
    rows.sort(key=lambda r: _num((r["ev"].get("scores") or {}).get("skills_match")) or 0, reverse=True)
    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def compute_domain_score(scores: dict) -> float:
    """Recompute the global score deterministically from dimension scores.

    The model's global_score is ignored; the total is the weighted average of
    the five dimension scores (skills 30%, education 20%, location 20%,
    language 20%, growth 10%), clamped to 1-5.

    Returns 0.0 if no usable dimension scores are present.
    """
    total = 0.0
    weight_sum = 0.0
    for dim, weight in DEFAULT_WEIGHTS.items():
        try:
            val = float(scores.get(dim, 0))
            if val > 0:
                total += val * weight
                weight_sum += weight
        except (ValueError, TypeError):
            continue
    if weight_sum == 0:
        return 0.0
    return round(max(1.0, min(5.0, total / weight_sum)), 1)
