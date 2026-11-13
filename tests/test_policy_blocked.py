"""
Blocked-dependency policy test (G3).

Enforces DEC-014 (no paid scraping or anti-bot services) and DEC-015
(no login-based scrapers and no archived tools):
selenium, undetected-chromedriver, jobfunnel, python-jobscrape,
jobspy2, jobsparser are blocked by this test.

The test reads the hash-locked requirements files and fails if any
blocked package is present. Run with: python -m pytest tests/test_policy_blocked.py -q
"""
import re
import subprocess
import sys
from pathlib import Path

BLOCKED_PACKAGES = {
    "selenium",
    "undetected-chromedriver",
    "jobfunnel",
    "python-jobscrape",
    "jobspy2",
    "jobsparser",
}

LOCK_FILES = [
    "requirements.txt",
    "requirements-ingestion.txt",
    "requirements-docs.txt",
    "requirements-dev.txt",
]


def _installed_names(requirements_path: Path) -> set[str]:
    """Return the set of package names (lowercased, normalized) from a lock file."""
    names: set[str] = set()
    text = requirements_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Strip inline comments and environment markers
        name_part = re.split(r"[\[<>=!;]", stripped, maxsplit=1)[0].strip()
        if name_part:
            names.add(name_part.lower().replace("_", "-").replace(".", "-"))
    return names


def test_blocked_dependencies_absent_from_core_lock():
    """No blocked package may appear in the hash-locked core requirements."""
    root = Path(__file__).resolve().parents[1]
    found: dict[str, str] = {}
    for lock_name in LOCK_FILES:
        lock_path = root / lock_name
        if not lock_path.exists():
            continue
        installed = _installed_names(lock_path)
        for blocked in BLOCKED_PACKAGES:
            if blocked in installed:
                found[blocked] = lock_name
    assert not found, (
        "Blocked dependency present in lock file(s): "
        + "; ".join(f"{pkg} in {lock}" for pkg, lock in found.items())
        + ". DEC-014/DEC-015 forbid these packages."
    )


def test_blocked_dependencies_absent_from_pip_freeze():
    """No blocked package may be installed in the current environment."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    installed: set[str] = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name_part = re.split(r"[\[<>=!]", stripped, maxsplit=1)[0].strip()
        if name_part:
            installed.add(name_part.lower().replace("_", "-").replace(".", "-"))
    blocked_found = BLOCKED_PACKAGES & installed
    assert not blocked_found, (
        "Blocked package installed in environment: "
        + ", ".join(sorted(blocked_found))
        + ". DEC-014/DEC-015 forbid these packages."
    )
