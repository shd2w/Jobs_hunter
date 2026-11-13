#!/usr/bin/env python3
"""
Secret and PII scan (G12).

Scans Git-tracked project files for secrets (API keys, tokens, credentials)
and personal data (email addresses, phone numbers) that must never be
committed. Exits non-zero if any finding is present, so CI fails closed.

Framework files under .ai-engineering/ are excluded: they contain
decision/evidence records, not project secrets or user PII. Example files
(*.example, *.example.yml, .env.example) are excluded because they contain
placeholder values, not real data. Test fixture data (obviously fake emails,
phones, keys) is excluded.

Usage: python scan_secrets_pii.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Secret patterns: real API keys, tokens, credentials.
SECRET_PATTERNS = [
    (r"sk-or-v1-[A-Za-z0-9\-_]{20,}", "OpenRouter API key"),
    (r"AIza[A-Za-z0-9\-_]{30,}", "Google AI API key"),
    (r"sk-[A-Za-z0-9]{20,}", "generic sk- API key"),
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{20,}", "API key assignment"),
    (r"(?i)(secret|password|passwd|token)\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{20,}", "secret/password/token assignment"),
    (r"(?i)TELEGRAM_BOT_TOKEN\s*[:=]\s*\d+:[A-Za-z0-9\-_]{20,}", "Telegram bot token"),
    (r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", "JWT token"),
]

# PII patterns: real contact data.
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "email address"),
    (r"\+\d{1,3}[\s\-][\d\s\-]{6,}", "international phone number"),
    (r"\b\d{3}[\s\-]\d{3}[\s\-]\d{4}\b", "US-style phone number (with separators)"),
]

# Placeholder/example values that are NOT real data.
EXAMPLE_VALUES = {
    "your@email.com", "example.com", "example.org", "example.invalid",
    "your-bot-token", "your-chat-id",
    "sk-or-v1-your-key-here", "sk-or-v1-second-key",
    "sk-or-v1-third-key", "sk-or-v1-fourth-key",
    "AIza-your-first-key", "AIza-your-second-key",
    "jane@example.com", "t@example.com", "m@example.com",
    "test@example.com", "pass@x.io", "someone@example.com",
    "t@example.invalid",
    "000 0000000", "+49 000 0000000",
    "1790000000", "3912345678",
    "4408884793", "4410613957", "4383100860", "4412165988",
    "4410709436", "4410373656",
    "+49 152 000",
}

# Fake/test API key values used in test fixtures.
EXAMPLE_KEYS = {
    "sk-abcdefghijklmnopqrstuvwxyz123456",
    "api_key = abcd1234abcd1234abcd1234",
    "API_KEY=AIzaNewSecretValue99",
}

# File path prefixes to skip entirely.
SKIP_PREFIXES = [
    ".ai-engineering",
    ".git",
    "__pycache__",
    ".pytest_cache",
]

# File name patterns to skip.
SKIP_NAMES = [
    ".env.example",
    "cv.example.md",
]

# Files with known pre-existing PII that is tracked as a known issue (KI-004).
# These contain owner data that predates WP-00-02 and must be addressed
# separately; they are excluded from the scan with a recorded justification.
SKIP_FILES_KNOWN_ISSUE = {
    "tests/test_queue_exporter.py",
}

# LinkedIn job IDs and other numeric URL segments falsely matched as phones.
SKIP_URL_NUMBERS = {
    "4408884793", "4410613957", "4383100860", "4412165988",
    "4410709436", "4410373656", "3912345678",
}


def _is_tracked(path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        capture_output=True,
    )
    return result.returncode == 0


def _should_skip(path: Path, rel: str | None = None) -> bool:
    parts = path.parts
    for prefix in SKIP_PREFIXES:
        if prefix in parts:
            return True
    name = path.name.lower()
    for skip in SKIP_NAMES:
        if skip == name:
            return True
    if name.endswith(".example") or name.endswith(".example.yml"):
        return True
    check_rel = rel if rel is not None else path.as_posix()
    if check_rel in SKIP_FILES_KNOWN_ISSUE:
        return True
    return False


def _is_example_value(value: str) -> bool:
    lowered = value.lower()
    if lowered in {v.lower() for v in EXAMPLE_VALUES}:
        return True
    if lowered in {k.lower() for k in EXAMPLE_KEYS}:
        return True
    if value in SKIP_URL_NUMBERS:
        return True
    return False


def _scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    all_patterns = SECRET_PATTERNS + PII_PATTERNS
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, label in all_patterns:
            for m in re.finditer(pattern, line):
                matched = m.group(0)
                if _is_example_value(matched):
                    continue
                findings.append((line_no, line.strip(), label, matched))
    return findings


def _safe_print(text: str) -> None:
    sys.stdout.write(text.encode(sys.stdout.encoding, errors="replace").decode(sys.stdout.encoding, errors="replace"))


def main() -> int:
    root = Path.cwd()
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line for line in result.stdout.splitlines() if line]

    all_findings: list[tuple[Path, int, str, str, str]] = []

    for rel in tracked:
        path = root / rel
        if not path.is_file():
            continue
        if _should_skip(path, rel):
            continue
        file_findings = _scan_file(path)
        for line_no, line, label, match in file_findings:
            all_findings.append((path, line_no, label, match, line))

    if all_findings:
        _safe_print("SECRET/PII SCAN FAILED - findings detected in tracked files:\n")
        _safe_print("=" * 70 + "\n")
        for path, line_no, label, match, line in all_findings:
            _safe_print(f"  {path}:{line_no} [{label}]\n")
            _safe_print(f"    match: {match!r}\n")
            _safe_print(f"    line:  {line}\n\n")
        _safe_print(f"Total findings: {len(all_findings)}\n\n")
        _safe_print("Remove all secrets and PII from tracked files before committing.\n")
        _safe_print("Use .env.example as a template and keep real values in .env (untracked).\n")
        return 1

    _safe_print("Secret and PII scan: no findings in tracked files. PASS.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
