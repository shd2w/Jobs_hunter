"""
run_evaluate.py -- Evaluate jobs from the pipeline.

Picks jobs from pipeline.md, evaluates with AI, and optionally
generates tailored CVs (markdown + PDF) and cover letters for high-scoring matches.
Sends Telegram notifications for all evaluations.

Usage:
    python run_evaluate.py --next          Evaluate the next unchecked job
    python run_evaluate.py --all           Evaluate all unchecked jobs
    python run_evaluate.py --url <URL>     Evaluate a specific job URL
    python run_evaluate.py --batch N       Evaluate next N unchecked jobs
"""

import argparse
import asyncio
import logging
import re
import sys
import warnings
from pathlib import Path

import yaml
from dotenv import load_dotenv

from agents.evaluator import Evaluator
from utils.jd_fetcher import fetch_jd, fetch_jd_playwright
from utils.telegram import TelegramNotifier
from utils.jd_cache import JDCache
from utils.utf8_logging import get_utf8_stream_handler

# Domain-scoring weights (mirrors the evaluation prompt dimensions).
DOMAIN_WEIGHTS = {
    "skills_match": 0.30,
    "education_match": 0.20,
    "location": 0.20,
    "language": 0.20,
    "growth": 0.10,
}


def compute_domain_score(scores: dict) -> float:
    """Recompute the global score deterministically from dimension scores.

    The model's global_score is ignored; the total is the weighted average of
    the five dimension scores (skills 30%, education 20%, location 20%,
    language 20%, growth 10%), clamped to 1-5.

    Returns 0.0 if no usable dimension scores are present.
    """
    total = 0.0
    weight_sum = 0.0
    for dim, weight in DOMAIN_WEIGHTS.items():
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


# Setup logging — use UTF-8 safe handler so job titles containing chars
# like \ufeff (BOM) do not crash logging on Windows cp1252 consoles.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[get_utf8_stream_handler(sys.stdout)],
)
logger = logging.getLogger("evaluate")

logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(logs_dir / "evaluate.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
logging.getLogger().addHandler(file_handler)


def load_profile() -> dict:
    """Load profile.yml for threshold config."""
    path = Path("config/profile.yml")
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f) or {}

    # Deprecation warnings for auto_cv_threshold / create_cv (DEC-019).
    ev = profile.get("evaluation", {}) or {}
    if ev.get("auto_cv_threshold") is not None:
        warnings.warn(
            "DEC-019: 'auto_cv_threshold' is deprecated; CV creation is no longer "
            "automatic. Use --create-cv only with --url.",
            DeprecationWarning,
            stacklevel=2,
        )
    if ev.get("create_cv") is not None:
        warnings.warn(
            "DEC-019: 'create_cv' is deprecated; CV creation is no longer automatic. "
            "Use --create-cv only with --url.",
            DeprecationWarning,
            stacklevel=2,
        )

    return profile


def get_pending_jobs(pipeline_path: str = "data/pipeline.md") -> list[dict]:
    """Parse pipeline.md and return unchecked jobs ranked by recency (newest first)."""
    path = Path(pipeline_path)
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    jobs = []

    # Look up date_posted from JD cache to prioritize freshest postings
    jd_dates = {}
    try:
        from utils.jd_cache import JDCache
        cache = JDCache()
        for url, entry in cache._cache.items():
            if entry.get("date_posted"):
                jd_dates[url] = str(entry["date_posted"])[:10]
    except Exception:
        pass

    # Match: - [ ] URL | Company | Title [Location]
    pattern = r"- \[ \] (https?://\S+)\s*\|\s*([^|]+)\s*\|\s*(.+?)(?:\s*\[([^\]]*)\])?\s*$"
    for match in re.finditer(pattern, text, re.MULTILINE):
        url = match.group(1).strip()
        company = match.group(2).strip()
        title = match.group(3).strip()
        location = match.group(4).strip() if match.group(4) else ""
        date_posted = jd_dates.get(url, "")
        jobs.append({
            "url": url,
            "company": company,
            "title": title,
            "location": location,
            "date_posted": date_posted,
        })

    # Rank offers by recency: newest released first, followed by uncatalogued dates
    jobs.sort(key=lambda j: j.get("date_posted") or "0000-00-00", reverse=True)
    return jobs


def mark_job_checked(url: str, pipeline_path: str = "data/pipeline.md"):
    """Mark a job as checked in pipeline.md ([ ] -> [x])."""
    path = Path(pipeline_path)
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    escaped_url = re.escape(url)
    text = re.sub(
        rf"- \[ \] {escaped_url}",
        f"- [x] {url}",
        text,
    )
    path.write_text(text, encoding="utf-8")


def log_below_threshold(evaluation: dict, threshold: float):
    """Log below-threshold jobs to data/below_threshold.md for review."""
    path = Path("data/below_threshold.md")

    if not path.exists():
        path.write_text(
            "# Jobs Below Threshold\n\n"
            "These jobs scored below the auto-apply threshold. "
            "Review them to decide if you want to lower the threshold.\n\n"
            "| Score | Company | Title | German? | Recommendation | URL |\n"
            "|-------|---------|-------|---------|----------------|-----|\n",
            encoding="utf-8",
        )

    score = evaluation.get("global_score", "?")
    company = evaluation.get("company", "?")
    title = evaluation.get("title", "?")
    german = "Yes" if evaluation.get("german_required") else "No"
    recommendation = evaluation.get("recommendation", "?")
    url = evaluation.get("url", "")

    row = f"| {score} | {company} | {title} | {german} | {recommendation} | [link]({url}) |\n"

    with open(path, "a", encoding="utf-8") as f:
        f.write(row)


async def evaluate_job(
    job: dict,
    evaluator: Evaluator,
    threshold: float,
    telegram: TelegramNotifier,
    jd_cache: JDCache | None = None,
    german_policy: str = "accept_all",
) -> dict:
    """Evaluate a single job (no automatic CV/cover letter creation per DEC-019)."""

    logger.info(f"Evaluating: {job['company']} -- {job['title']}")

    # 1. Get JD text: cache -> httpx -> playwright
    if not job.get("description"):
        # Check cache first (populated during scanning — critical for Indeed)
        if jd_cache:
            cached = jd_cache.get(job["url"])
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
        logger.info(f"Fetching JD from {job['url']}")
        result = await fetch_jd(job["url"])

        if not result.success:
            logger.info("Static fetch failed, trying Playwright...")
            result = await fetch_jd_playwright(job["url"])

        if result.is_expired:
            logger.warning(f"Job appears expired: {job['url']}")
            mark_job_checked(job["url"])
            return {
                "success": False,
                "error": "Job posting expired",
                "company": job["company"],
                "title": job["title"],
            }

        if result.success:
            job["description"] = result.text
            # Extract company + clean title from page title (LinkedIn: "Company hiring Role")
            if result.title:
                hiring_match = re.match(r"^(.+?)\s+hiring\s+(.+)", result.title)
                if hiring_match:
                    if job.get("company") in ("Unknown", ""):
                        job["company"] = hiring_match.group(1).strip()
                        logger.info(f"Company from page title: {job['company']}")
                    if job.get("title") in ("Unknown", ""):
                        job["title"] = hiring_match.group(2).strip()
                elif job.get("title") in ("Unknown", ""):
                    job["title"] = result.title
        else:
            logger.warning(f"Could not fetch JD: {result.error}")

    # 2. Evaluate
    evaluation = evaluator.evaluate(job)

    if not evaluation.get("success"):
        logger.error(f"Evaluation failed: {evaluation.get('error')}")
        mark_job_checked(job["url"])
        return evaluation

    # WP-01-03: Deterministic total score — recompute from dimension scores,
    # ignore the model's global_score.
    score = compute_domain_score(evaluation.get("scores", {}))
    evaluation["global_score"] = score
    if score == 0:
        logger.warning(f"No usable dimension scores from AI for {job['company']} - {job['title']}, defaulting to 0")

    # Update job dict with AI-extracted company/title if originally missing
    if not job.get("company") or job["company"] == "Unknown":
        job["company"] = evaluation.get("company", "Unknown")
    if not job.get("title") or job["title"] == "Unknown":
        job["title"] = evaluation.get("title", "Unknown")

    # Pass date_posted to evaluation for Telegram display
    if job.get("date_posted"):
        evaluation["date_posted"] = job["date_posted"]

    # --- German Language Auto-Rejection ---
    german_level = evaluation.get("german_level_required", "none")
    german_required = evaluation.get("german_required", False)

    should_reject = False
    if german_policy == "reject_b1_plus":
        should_reject = german_level in ("B2+", "B1")
    elif german_policy == "reject_b2_plus_only":
        should_reject = german_level == "B2+"
    elif german_policy == "reject_unless_bilingual":
        # Accept German-requiring jobs IF the JD also mentions English
        if german_level in ("B2+", "B1") or german_required:
            jd_lower = job.get("description", "").lower()
            english_signals = [
                "english", "englisch", "fluent in english", "good english",
                "very good english", "excellent english", "english required",
                "working language: english", "english is a must",
                "gute englischkenntnisse", "sehr gute englischkenntnisse",
                "flie\u00dfend englisch", "b2 english",
            ]
            # Check word-boundary matches for short CEFR codes (avoid matching "C1 certification" etc.)
            has_english = any(signal in jd_lower for signal in english_signals)
            if not has_english:
                has_english = bool(re.search(r'\b(c1|c2)\b.*\b(english|englisch)\b', jd_lower)) or \
                              bool(re.search(r'\b(english|englisch)\b.*\b(c1|c2)\b', jd_lower))
            if has_english:
                should_reject = False
                logger.info(
                    f"[DE] BILINGUAL: German {german_level} + English found "
                    f"-> keeping job (policy={german_policy})"
                )
            else:
                should_reject = True
    # accept_all: never auto-reject

    if should_reject:
        original_score = score
        score = 0
        evaluation["global_score"] = 0
        evaluation["recommendation"] = "skip_german"
        logger.info(
            f"[DE] AUTO-SKIP: German {german_level} required "
            f"(policy={german_policy}) | "
            f"Original score: {original_score}/5 | Company: {job['company']}"
        )
    else:
        logger.info(
            f"Score: {score}/5 | Company: {job['company']} | "
            f"Recommendation: {evaluation.get('recommendation')} | "
            f"German: {german_level}"
        )

    # 3. Send Telegram notification for every evaluation
    telegram.notify_evaluation(evaluation)

    # 3b. Update Excel database
    try:
        from utils.excel_export import update_job_entry
        update_job_entry(evaluation)
    except Exception as e:
        logger.debug(f"Excel export skipped: {e}")

    # Log evaluation for review — no automatic document creation per DEC-019.
    # CVs and cover letters are created explicitly via --url --create-cv only.
    log_below_threshold(evaluation, threshold)

    # 4b. Append to JSON evaluations store (canonical input for the UAA
    # queue exporter). This is the persistence hook that connects
    # run_evaluate.py -> run_export_queue.py -> application_queue.jsonl.
    try:
        from utils.evaluation_store import append_evaluation
        append_evaluation(evaluation)
    except Exception as e:
        logger.debug(f"JSON evaluation store skipped: {e}")

    # 5. Mark as checked in pipeline
    mark_job_checked(job["url"])

    return evaluation


async def run_evaluate(
    mode: str = "next",
    url: str | None = None,
    batch_size: int = 1,
    threshold_override: float | None = None,
    german_policy: str | None = None,
    create_cv_override: bool | None = None,
):
    """Main evaluation runner."""
    load_dotenv()
    profile = load_profile()
    threshold = threshold_override if threshold_override is not None else profile.get("evaluation", {}).get("auto_cv_threshold", 3.5)
    german_policy_resolved = german_policy if german_policy else profile.get("evaluation", {}).get("german_filter", "accept_all")

    evaluator = Evaluator()
    telegram = TelegramNotifier()
    jd_cache = JDCache()

    if mode == "url" and url:
        job = {"url": url, "company": "Unknown", "title": "Unknown"}
        result = await evaluate_job(job, evaluator, threshold, telegram, jd_cache, german_policy=german_policy_resolved)
        return [result]

    # Get pending jobs
    pending = get_pending_jobs()
    if not pending:
        logger.info("No pending jobs in pipeline.md")
        return []

    logger.info(f"Found {len(pending)} pending jobs")

    if mode == "next":
        jobs_to_evaluate = pending[:1]
    elif mode == "batch":
        jobs_to_evaluate = pending[:batch_size]
    else:  # "all"
        jobs_to_evaluate = pending

    results = []
    for i, job in enumerate(jobs_to_evaluate):
        logger.info(f"\n{'='*60}")
        logger.info(f"Job {i+1}/{len(jobs_to_evaluate)}")
        logger.info(f"{'='*60}")

        result = await evaluate_job(job, evaluator, threshold, telegram, jd_cache, german_policy=german_policy_resolved)
        results.append(result)

        # Rate limit delay between evaluations
        if i < len(jobs_to_evaluate) - 1:
            logger.info("Waiting 3s before next evaluation (rate limit)...")
            await asyncio.sleep(3)

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("EVALUATION SUMMARY")
    logger.info(f"{'='*60}")
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    high_score = [r for r in successful if r.get("global_score", 0) >= threshold]
    below = [r for r in successful if r.get("global_score", 0) < threshold]

    logger.info(f"  Evaluated:    {len(successful)}")
    logger.info(f"  Failed:       {len(failed)}")
    logger.info(f"  Score >= {threshold}: {len(high_score)} (Cover letter generated)")
    logger.info(f"  Score < {threshold}:  {len(below)} (logged to below_threshold.md)")

    for r in successful:
        marker = "[+]" if r.get("global_score", 0) >= threshold else "[ ]"
        logger.info(
            f"  {marker} {r.get('company', '?')} -- {r.get('title', '?')} "
            f"-> {r.get('global_score', '?')}/5 [{r.get('recommendation', '?')}]"
        )

    # Send summary to Telegram
    if results:
        summary_text = (
            f"Evaluation Batch Complete\n"
            f"Total: {len(successful)} evaluated, {len(failed)} failed\n"
            f"Above threshold: {len(high_score)} (Cover letter generated)\n"
            f"Below threshold: {len(below)}"
        )
        telegram.send_message(summary_text)

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate jobs from pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--next", action="store_true", help="Evaluate next unchecked job")
    group.add_argument("--all", action="store_true", help="Evaluate all unchecked jobs")
    group.add_argument("--url", type=str, help="Evaluate a specific job URL")
    group.add_argument("--batch", type=int, help="Evaluate next N unchecked jobs")
    parser.add_argument("--threshold", type=float, default=None, help="Override auto_cv_threshold (e.g. --threshold 4.0)")
    parser.add_argument("--german-policy", type=str, choices=["reject_b1_plus", "reject_b2_plus_only", "reject_unless_bilingual", "accept_all"], default=None, help="Override German filter policy for this run")
    parser.add_argument("--create-cv", action="store_true", help="Create tailored CV (only valid with --url)")
    args = parser.parse_args()

    # DEC-019: --create-cv is valid only with --url.
    if args.create_cv and not args.url:
        parser.error("--create-cv requires --url")

    if args.url:
        asyncio.run(run_evaluate(mode="url", url=args.url, threshold_override=args.threshold, german_policy=args.german_policy))
    elif args.all:
        asyncio.run(run_evaluate(mode="all", threshold_override=args.threshold, german_policy=args.german_policy))
    elif args.batch:
        asyncio.run(run_evaluate(mode="batch", batch_size=args.batch, threshold_override=args.threshold, german_policy=args.german_policy))
    else:
        asyncio.run(run_evaluate(mode="next", threshold_override=args.threshold, german_policy=args.german_policy))


if __name__ == "__main__":
    main()
