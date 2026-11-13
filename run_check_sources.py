"""
run_check_sources.py — try each enabled extra source ONCE and report what came back.

Writes nothing to pipeline.md / history and does not start a cooldown, so a real
`python run_scan.py` right afterwards still works. Use it to see which sources
work from your network (some will be blocked) before relying on them.

    python run_check_sources.py
"""

import asyncio
import sys
from pathlib import Path

import yaml

from scanners.ats import AtsScanner
from scanners.feeds import FeedScanner
from scanners.net import Cooldown


class NoCooldown(Cooldown):
    """Never blocks and never records, so checking is side-effect free."""

    def remaining(self, key, seconds):
        return 0

    def mark(self, key):
        pass


async def main() -> int:
    path = Path("config/portals.yml")
    if not path.exists():
        print("config/portals.yml not found")
        return 1
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not (config.get("extra_sources") or {}).get("enabled", False):
        print("extra_sources.enabled is false in config/portals.yml")
        return 1
    problems = 0
    for label, cls in (("ATS boards", AtsScanner), ("Feeds", FeedScanner)):
        result = await cls(config, cooldown=NoCooldown("data")).scan()
        print(f"\n== {label}: {result.job_count} jobs ==")
        by_source: dict[str, int] = {}
        for job in result.jobs:
            by_source[job.source] = by_source.get(job.source, 0) + 1
        for source, count in sorted(by_source.items()):
            sample = next(j for j in result.jobs if j.source == source)
            print(f"  OK   {source}: {count} jobs, e.g. '{sample.title}' [{sample.location or 'no location'}]")
        for err in result.errors:
            problems += 1
            print(f"  FAIL {err}")
    print("\nDone." if not problems else f"\nDone with {problems} problem(s) - see FAIL lines above.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
