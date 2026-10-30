"""
run_scan.py — Master scanner entry point.

Runs all configured scanners, merges results through the bridge,
and reports what was found.

Usage:
    python run_scan.py              Run full scan
    python run_scan.py --dry-run    Show results without writing to pipeline
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from scanners.workday import DirectAPIScanner
from scanners.jobspy_scanner import JobSpyScanner, bounded_search
from scanners.jobspy_registry import SITES
from scanners.bridge import PipelineBridge
from scanners.scrapling_scanner import ScraplingScanner
from utils.utf8_logging import get_utf8_stream_handler

# Setup logging — use UTF-8 safe handler so job titles containing chars
# like \ufeff (BOM) do not crash logging on Windows cp1252 consoles.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        get_utf8_stream_handler(sys.stdout),
    ],
)
logger = logging.getLogger("scan")

# Also log to file if logs/ exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)
file_handler = logging.FileHandler(logs_dir / "scan.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
logging.getLogger().addHandler(file_handler)


def load_config() -> dict:
    """Load portals.yml config."""
    path = Path("config/portals.yml")
    if not path.exists():
        logger.error("config/portals.yml not found. Run setup first.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


async def run_scan(dry_run: bool = False, config_override=None, data_dir="data", only_jobspy=False, only_scrapling=False):
    """Execute all scanners and merge results."""
    load_dotenv()
    config = config_override if config_override is not None else load_config()
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Starting job scan...")
    logger.info("=" * 60)

    scan_results = []

    # Primary Scrapling engine shares production checkpoints and provider gates.
    if not only_jobspy:
        try:
            result=await ScraplingScanner(config,data_dir,dry_run).scan()
            scan_results.append(result)
            logger.info(f"Scrapling: {result.job_count} jobs, {result.error_count} errors")
        except Exception as exc:
            from scanners.base import ScanResult
            scan_results.append(ScanResult(scanner_name='scrapling',errors=[str(exc)]))
            logger.error(f"Scrapling engine failed: {type(exc).__name__}")

    # 1. Original direct scanner (only explicitly configured employers)
    try:
        workday = DirectAPIScanner(config)
        result = await workday.scan() if not only_jobspy and not only_scrapling else workday._finish_result(workday._make_result())
        scan_results.append(result)
        logger.info(f"Workday: {result.job_count} jobs, {result.error_count} errors")
    except Exception as e:
        logger.error(f"Workday scanner failed entirely: {e}")

    # 2. JobSpy scanner (all pinned providers; original routes retained)
    try:
        jobspy = JobSpyScanner(config)
        result = await jobspy.scan() if not only_scrapling else jobspy._finish_result(jobspy._make_result())
        scan_results.append(result)
        logger.info(f"JobSpy: {result.job_count} jobs, {result.error_count} errors")
    except Exception as e:
        logger.error(f"JobSpy scanner failed entirely: {e}")

    # 3. Merge through bridge
    bridge = PipelineBridge(config, data_dir)
    from filelock import FileLock
    with FileLock(str(Path(data_dir) / '.pipeline.lock'), timeout=30):
        # Reload dedup/cache while holding the same lock as the dashboard mirror.
        bridge = PipelineBridge(config, data_dir)
        summary = bridge.process(scan_results, dry_run=dry_run)
    if not dry_run:
        from scanners.compat import mirror_to_inbox
        # Include repeated sightings as updates so prior jobs gain richer fields.
        from utils.filters import filter_jobs
        rows = [job.to_dict() for result in scan_results for job in result.jobs]
        accepted = filter_jobs(rows, bridge.title_filter, bridge.location_filter)['passed']
        summary['inbox'] = mirror_to_inbox(accepted, data_dir)


    # 4. Print summary
    logger.info("=" * 60)
    logger.info("SCAN SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total found:       {summary['total_found']}")
    logger.info(f"  Passed filters:    {summary['passed_filters']}")
    logger.info(f"  Rejected (title):  {summary['rejected_title']}")
    logger.info(f"  Rejected (loc):    {summary['rejected_location']}")
    logger.info(f"  Duplicates:        {summary['duplicates']}")
    logger.info(f"  [OK] New added:    {summary['new_added']}")

    if summary["errors"]:
        logger.warning(f"  [!] Errors ({len(summary['errors'])}):")
        for err in summary["errors"]:
            logger.warning(f"    - {err}")

    if dry_run:
        logger.info("(DRY RUN — no job records written; empty legacy templates may be initialized)")
        if summary["new_jobs"]:
            logger.info("\nWould add these jobs:")
            for job in summary["new_jobs"][:10]:
                logger.info(f"  - {job['company']}: {job['title']} [{job.get('location', '')}]")
            if len(summary["new_jobs"]) > 10:
                logger.info(f"  ... and {len(summary['new_jobs']) - 10} more")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Scan for working student jobs")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show results without writing to pipeline.md"
    )
    parser.add_argument('--engine',choices=['all','scrapling'],default='all',help='Run all original engines or only primary Scrapling sources')
    parser.add_argument('--site', choices=SITES)
    parser.add_argument('--term', help='Optional bounded query override; registry is not edited')
    parser.add_argument('--location', help='Optional bounded location override')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--data-dir', default='data')
    args = parser.parse_args()
    if args.engine=='scrapling' and (args.site or args.term or args.location):
        parser.error('Scrapling uses fixed source routes; --site/--term/--location are JobSpy overrides')
    config = None
    if args.site or args.term or args.location:
        config = load_config()
        if args.site:
            selected = bounded_search(config, args.site, args.term or 'Software Engineer', args.location, args.limit)
            config.pop('jobspy_providers', None)
            config['jobspy_searches'] = [selected]
        else:
            config.pop('jobspy_providers', None)
            config['jobspy_searches'] = [{'term': args.term or 'Software Engineer',
            'location': args.location or 'Germany', 'sites': [args.site] if args.site else ['linkedin', 'indeed', 'bayt'],
            'results_wanted': max(1, min(100, args.limit))}]


    summary = asyncio.run(run_scan(dry_run=args.dry_run, config_override=config, data_dir=args.data_dir, only_jobspy=config is not None,only_scrapling=args.engine=='scrapling'))
    sys.exit(1 if summary["errors"] and not summary["total_found"] else 0)


if __name__ == "__main__":
    main()
