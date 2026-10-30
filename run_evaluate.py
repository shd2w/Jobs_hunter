"""
run_evaluate.py -- Evaluate jobs from the pipeline.

Picks jobs from pipeline.md, evaluates with AI, and optionally
prepares ATS recommendations and cover letters without changing CVs.
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
from pathlib import Path

import yaml
from dotenv import load_dotenv

from agents.evaluator import Evaluator
from agents.cv_tailor import CVTailor
from agents.cover_letter import CoverLetterWriter
from utils.jd_fetcher import fetch_jd, fetch_jd_playwright
from utils.telegram import TelegramNotifier
from utils.pdf_generator import generate_cover_letter_pdf
from utils.jd_cache import JDCache
from utils.utf8_logging import get_utf8_stream_handler

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
        return yaml.safe_load(f) or {}


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
    cv_tailor: CVTailor | None,
    cover_writer: CoverLetterWriter,
    threshold: float,
    telegram: TelegramNotifier,
    jd_cache: JDCache | None = None,
    german_policy: str = "accept_all",
    create_cv: bool = False,
) -> dict:
    """Evaluate a job; legacy CV parameters cannot enable prohibited generation."""
    if create_cv:
        raise ValueError("CV creation is retired; use ATS keyword recommendations")

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

        if not result.success and not result.is_expired and result.error not in ("HTTP 401", "HTTP 403", "HTTP 429"):
            logger.info("Static fetch insufficient; trying permitted JS rendering...")
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
            logger.warning("Could not fetch JD; leaving job pending")
            return {"success": False, "error": "Description unavailable; retry after resolving source access", "url": job["url"], "company": job["company"], "title": job["title"]}

    # 2. Evaluate
    from jobhunter_app.evaluation_service import evaluate_prepared
    evaluation = evaluate_prepared(job, evaluator, german_policy)

    if not evaluation.get("success"):
        logger.error(f"Evaluation failed: {evaluation.get('error')}")
        return evaluation  # Retryable failures remain pending.

    score = evaluation.get("global_score", 0)

    import math
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not (1 <= score <= 5 or (score == 0 and evaluation.get("policy_rejected"))):
        return {"success": False, "error": "Invalid evaluation score; job remains pending", "url": job["url"]}
    evaluation["global_score"] = round(score, 1)

    # Update job dict with AI-extracted company/title if originally missing
    if not job.get("company") or job["company"] == "Unknown":
        job["company"] = evaluation.get("company", "Unknown")
    if not job.get("title") or job["title"] == "Unknown":
        job["title"] = evaluation.get("title", "Unknown")

    evaluation["description"] = job.get("description", "")
    evaluation["location"] = job.get("location", "")

    # Pass date_posted to evaluation for Telegram display
    if job.get("date_posted"):
        evaluation["date_posted"] = job["date_posted"]

    evaluation["threshold"] = threshold
    evaluation["classification"] = "rejected" if evaluation.get("policy_rejected") else "above_threshold" if evaluation["global_score"] >= threshold else "below_threshold"
    # Policy and scoring owned by the shared evaluation service.
    score = evaluation["global_score"]

    # 3. Send Telegram notification for every evaluation
    telegram.notify_evaluation(evaluation)

    # 3b. Update Excel database
    try:
        from utils.excel_export import update_job_entry
        update_job_entry(evaluation)
    except Exception as e:
        logger.debug(f"Excel export skipped: {e}")

    # CVs are read-only candidate inputs, never generated or modified.
    from jobhunter_app.matching import keyword_recommendations
    evaluation["ats_keywords"] = keyword_recommendations(job.get("description", ""), evaluator.cv_content)
    if score >= threshold:
        original_cv = profile_original_cv()
        if original_cv:
            evaluation["cv_path"] = str(original_cv)
            if original_cv.suffix.lower() == ".pdf":
                evaluation["cv_pdf_path"] = str(original_cv)

        cover_result = cover_writer.generate(job, evaluation)
        if cover_result.get("success"):
            logger.info(f"Cover letter: {cover_result['output_path']}")
            evaluation["cover_letter_path"] = cover_result["output_path"]
        else:
            logger.warning(f"Cover letter failed: {cover_result.get('error')}")

        # Generate cover letter PDF
        cover_pdf_path = None
        if cover_result.get("success"):
            cover_pdf_out = cover_result["output_path"].replace("-cover.md", "-cover.pdf")
            try:
                cl_pdf_result = generate_cover_letter_pdf(
                    md_content=cover_result.get("content", ""),
                    output_path=cover_pdf_out,
                    company=job.get("company", "Unknown"),
                    role=job.get("title", "Unknown"),
                )
                if cl_pdf_result.get("success"):
                    cover_pdf_path = cl_pdf_result["output_path"]
                    evaluation["cover_letter_pdf_path"] = cover_pdf_path
                    logger.info(f"Cover letter PDF: {cover_pdf_path}")
                else:
                    logger.warning(f"Cover letter PDF failed: {cl_pdf_result.get('error')}")
            except Exception as e:
                logger.warning(f"Cover letter PDF skipped (WeasyPrint not available): {e}")

        # Send cover letter via Telegram (PDF if available, otherwise markdown)
        if evaluation.get("cover_letter_path"):
            send_cover_path = cover_pdf_path or evaluation["cover_letter_path"]
            telegram.notify_cover_letter(evaluation, send_cover_path)
    else:
        if evaluation.get("recommendation") == "skip_german":
            logger.info(f"German required -> Skipping cover letter generation")
        else:
            logger.info(f"Score {score} < {threshold} -> Skipping cover letter generation")
        # Log below-threshold for review
        log_below_threshold(evaluation, threshold)

    # 4b. Append to JSON evaluations store (canonical input for the UAA
    # queue exporter). Persisted AFTER document generation so the record
    # carries the generated cv_pdf_path / cover_letter_pdf_path values.
    # This is the persistence hook that connects
    # run_evaluate.py -> run_export_queue.py -> application_queue.jsonl.
    from utils.evaluation_store import append_evaluation
    append_evaluation(evaluation)  # Failure must propagate; do not mark processed.

    evaluator._update_tracker(evaluation)

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
    if create_cv_override:
        raise ValueError("CV creation is retired")
    from jobhunter_app.evaluation_service import EvaluationOptions
    EvaluationOptions(method='ai',threshold=threshold,german_policy=german_policy_resolved)
    create_cv = False

    evaluator = Evaluator()
    cv_tailor = None
    cover_writer = CoverLetterWriter()
    telegram = TelegramNotifier()
    jd_cache = JDCache()

    if mode == "url" and url:
        job = {"url": url, "company": "Unknown", "title": "Unknown"}
        result = await evaluate_job(job, evaluator, cv_tailor, cover_writer, threshold, telegram, jd_cache, german_policy=german_policy_resolved, create_cv=create_cv)
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

        result = await evaluate_job(job, evaluator, cv_tailor, cover_writer, threshold, telegram, jd_cache, german_policy=german_policy_resolved, create_cv=create_cv)
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
    logger.info(f"  Score >= {threshold}: {len(high_score)} (eligible for preparation)")
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
            f"Above threshold: {len(high_score)} (eligible for preparation)\n"
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
    parser.add_argument("--no-cv", action="store_true", help="Do not create/tailor CVs (use base cv.md)")
    parser.add_argument("--create-cv", action="store_true", help="Retired: rejected by policy")
    args = parser.parse_args()

    create_cv_override = None
    if args.no_cv:
        create_cv_override = False
    elif args.create_cv:
        create_cv_override = True

    if args.url:
        results = asyncio.run(run_evaluate(mode="url", url=args.url, threshold_override=args.threshold, german_policy=args.german_policy, create_cv_override=create_cv_override))
    elif args.all:
        results = asyncio.run(run_evaluate(mode="all", threshold_override=args.threshold, german_policy=args.german_policy, create_cv_override=create_cv_override))
    elif args.batch:
        results = asyncio.run(run_evaluate(mode="batch", batch_size=args.batch, threshold_override=args.threshold, german_policy=args.german_policy, create_cv_override=create_cv_override))
    else:
        results = asyncio.run(run_evaluate(mode="next", threshold_override=args.threshold, german_policy=args.german_policy, create_cv_override=create_cv_override))
    if any(not r.get("success") for r in results):
        raise SystemExit(2)




def profile_original_cv():
    """Only link explicitly selected, existing candidate originals."""
    configured = load_profile().get("documents", {}).get("original_cv")
    if not configured:
        return None
    path = Path(configured)
    return path if path.is_file() else None


if __name__ == "__main__":
    main()
