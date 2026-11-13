"""Evaluation service — evaluates a job against the candidate profile."""

from __future__ import annotations

import logging
from typing import Optional

from agents.evaluator import Evaluator
from jobhunter.app.result import Err, Ok, Result
from run_evaluate import compute_domain_score, load_profile
from utils.jd_cache import JDCache
from utils.jd_fetcher import fetch_jd, fetch_jd_playwright

logger = logging.getLogger(__name__)


class EvaluationService:
    """Evaluates a job posting against the candidate's profile.

    Wraps the existing evaluate_job logic with Result[T] error handling.
    """

    def __init__(
        self,
        evaluator: Optional[Evaluator] = None,
        jd_cache: Optional[JDCache] = None,
        german_policy: str = "accept_all",
    ):
        self.evaluator = evaluator or Evaluator()
        self.jd_cache = jd_cache or JDCache()
        self.german_policy = german_policy
        self.profile = load_profile()

    def evaluate(self, job: dict) -> Result[dict]:
        """Evaluate a single job.

        Returns Ok(evaluation) on success, Err(error) on failure.
        """
        url = job.get("url", "")
        logger.info(f"Evaluating: {job.get('company', '?')} -- {job.get('title', '?')}")

        # 1. Get JD text: cache -> httpx -> playwright
        if not job.get("description"):
            if self.jd_cache:
                cached = self.jd_cache.get(url)
                if cached:
                    job["description"] = cached.get("description", "")
                    if job.get("title") in ("Unknown", "") and cached.get("title"):
                        job["title"] = cached["title"]
                    if job.get("company") in ("Unknown", "") and cached.get("company"):
                        job["company"] = cached["company"]
                    if not job.get("date_posted") and cached.get("date_posted"):
                        job["date_posted"] = cached["date_posted"]
                    logger.info("JD loaded from cache (%d chars)", len(job["description"]))

        if not job.get("description"):
            logger.info(f"Fetching JD from {url}")
            result = fetch_jd(url)
            if not result.success:
                result = fetch_jd_playwright(url)

            if getattr(result, "is_expired", False):
                logger.warning(f"Job appears expired: {url}")
                return Err(error="Job posting expired", code="expired")

            if result.success:
                job["description"] = result.text
                if result.title:
                    import re as _re

                    hiring_match = _re.match(r"^(.+?)\s+hiring\s+(.+)", result.title)
                    if hiring_match:
                        if job.get("company") in ("Unknown", ""):
                            job["company"] = hiring_match.group(1).strip()
                        if job.get("title") in ("Unknown", ""):
                            job["title"] = hiring_match.group(2).strip()
                    elif job.get("title") in ("Unknown", ""):
                        job["title"] = result.title
            else:
                logger.warning(f"Could not fetch JD: {getattr(result, 'error', 'unknown')}")
                return Err(error=f"Could not fetch JD: {getattr(result, 'error', 'unknown')}", code="fetch_failed")

        # 2. Evaluate
        evaluation = self.evaluator.evaluate(job)

        if not evaluation.get("success"):
            logger.error(f"Evaluation failed: {evaluation.get('error')}")
            return Err(error=evaluation.get("error", "evaluation failed"), code="eval_failed")

        # WP-01-03: Deterministic total score — recompute from dimension scores
        score = compute_domain_score(evaluation.get("scores", {}))
        evaluation["global_score"] = score
        if score == 0:
            logger.warning(
                f"No usable dimension scores from AI for {job.get('company')} - {job.get('title')}, defaulting to 0"
            )

        # Update job dict with AI-extracted company/title if originally missing
        if not job.get("company") or job["company"] == "Unknown":
            job["company"] = evaluation.get("company", "Unknown")
        if not job.get("title") or job["title"] == "Unknown":
            job["title"] = evaluation.get("title", "Unknown")

        # Pass date_posted to evaluation
        if job.get("date_posted"):
            evaluation["date_posted"] = job["date_posted"]

        # German Language Auto-Rejection
        german_level = evaluation.get("german_level_required", "none")
        german_required = evaluation.get("german_required", False)

        should_reject = False
        if self.german_policy == "reject_b1_plus":
            should_reject = german_level in ("B2+", "B1")
        elif self.german_policy == "reject_b2_plus_only":
            should_reject = german_level == "B2+"
        elif self.german_policy == "reject_unless_bilingual":
            if german_level in ("B2+", "B1") or german_required:
                jd_lower = job.get("description", "").lower()
                english_signals = [
                    "english", "englisch", "fluent in english", "good english",
                    "very good english", "excellent english", "english required",
                    "working language: english", "english is a must",
                    "gute englischkenntnisse", "sehr gute englischkenntnisse",
                    "flie\u00dfend englisch", "b2 english",
                ]
                has_english = any(signal in jd_lower for signal in english_signals)
                if not has_english:
                    import re as _re

                    has_english = bool(
                        _re.search(r"\b(c1|c2)\b.*\b(english|englisch)\b", jd_lower)
                    ) or bool(
                        _re.search(r"\b(english|englisch)\b.*\b(c1|c2)\b", jd_lower)
                    )
                if has_english:
                    should_reject = False
                    logger.info(
                        f"[DE] BILINGUAL: German {german_level} + English found "
                        f"-> keeping job (policy={self.german_policy})"
                    )
                else:
                    should_reject = True

        if should_reject:
            original_score = score
            score = 0
            evaluation["global_score"] = 0
            evaluation["recommendation"] = "skip_german"
            logger.info(
                f"[DE] AUTO-SKIP: German {german_level} required "
                f"(policy={self.german_policy}) | "
                f"Original score: {original_score}/5 | Company: {job.get('company')}"
            )
        else:
            logger.info(
                f"Score: {score}/5 | Company: {job.get('company')} | "
                f"Recommendation: {evaluation.get('recommendation')} | "
                f"German: {german_level}"
            )

        return Ok(evaluation)
