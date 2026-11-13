"""
Shared helpers for the optional public-source scanners (ATS boards and feeds).

Deliberately small and strict:
* HTTPS only, fixed host allow-list, no redirects, no cookies, no credentials.
* Response size cap and timeout.
* Per-source cooldown persisted in ``data/extra_sources_state.json`` so a
  scheduled run can never hammer a provider (Remotive asks for <= 4 fetches/day).

No proxy, stealth, login or challenge-bypass logic exists here, by design.
A 401/403/429 is reported and the source is skipped.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "JobHunter/1.0 (personal job-search tool; contact via repository)"
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
ATS_MAX_BYTES = 32 * 1024 * 1024  # big employer boards are legitimately large
MAX_DESCRIPTION = 8000

# Every host any extra scanner may contact. Anything else is refused.
ALLOWED_HOSTS = frozenset({
    "boards-api.greenhouse.io",
    "api.lever.co",
    "api.ashbyhq.com",
    "api.smartrecruiters.com",
    "remotive.com",
    "jobicy.com",
    "www.arbeitnow.com",
    "www.arbeitnow.co.uk",
    "remoteok.com",
    "weworkremotely.com",
})


class FetchError(RuntimeError):
    """Raised for blocked, rate-limited, oversized or malformed responses."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status

    @property
    def blocked(self) -> bool:
        return self.status in (401, 403, 429)


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.port not in (None, 443):
        raise FetchError("Only https on port 443 is allowed")
    if (parts.hostname or "").lower() not in ALLOWED_HOSTS:
        raise FetchError(f"Host not on the extra-source allow-list: {parts.hostname}")


def fetch(url: str, accept: str = "application/json", *, timeout: float = 25.0,
          max_bytes: int = DEFAULT_MAX_BYTES, client: httpx.Client | None = None) -> tuple[bytes, str]:
    """GET ``url`` and return ``(body, content_type)``.

    ``client`` can be injected (tests use ``httpx.MockTransport``).
    """
    _check_url(url)
    own = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)
    try:
        with client.stream("GET", url, headers={"Accept": accept, "User-Agent": USER_AGENT}) as resp:
            if 300 <= resp.status_code < 400:
                raise FetchError("Redirects are disabled for extra sources", resp.status_code)
            if resp.status_code >= 400:
                raise FetchError(f"HTTP {resp.status_code}", resp.status_code)
            chunks, size = [], 0
            for chunk in resp.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError("Response exceeds the size limit")
                chunks.append(chunk)
            return b"".join(chunks), resp.headers.get("content-type", "").lower()
    except httpx.HTTPError as exc:
        raise FetchError(f"{type(exc).__name__}: network error") from exc
    finally:
        if own:
            client.close()


def fetch_json(url: str, *, client: httpx.Client | None = None, max_bytes: int = DEFAULT_MAX_BYTES):
    body, content_type = fetch(url, "application/json", max_bytes=max_bytes, client=client)
    if "json" not in content_type:
        raise FetchError("Source did not return JSON")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise FetchError("Source returned malformed JSON") from exc


# ---------------------------------------------------------------- text helpers

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(?:p|br|li|ul|ol|div|h[1-6]|tr)[^>]*>", re.I)
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)


def html_to_text(value, limit: int = MAX_DESCRIPTION) -> str:
    """Plain text from HTML, including entity-escaped HTML (Greenhouse).

    Output is text only; callers must still render it as text, never as HTML.
    """
    if not value:
        return ""
    text = str(value)
    for _ in range(2):  # unescape once to reveal escaped tags, once more for entities
        text = html.unescape(text)
        text = _SCRIPT.sub(" ", text)
        text = _BLOCK.sub("\n", text)
        text = _TAG.sub(" ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:limit]


def safe_text(value, limit: int = 300) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


def https_url(value) -> str:
    """Return the URL only if it is an absolute http(s) URL."""
    text = safe_text(value, 2000)
    return text if text.startswith(("https://", "http://")) else ""


def iso_date(value) -> str:
    """Normalise epoch seconds/milliseconds or date strings to a date string."""
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        try:
            return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""
    return safe_text(value, 40)


# -------------------------------------------------------------------- cooldown

class Cooldown:
    """Persisted per-source "last run" timestamps."""

    def __init__(self, data_dir: str | Path = "data", clock=time.time):
        self.path = Path(data_dir) / "extra_sources_state.json"
        self.clock = clock
        self.state: dict = {}
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.state, dict):
                self.state = {}
        except (OSError, ValueError):
            self.state = {}

    def remaining(self, key: str, seconds: int) -> int:
        last = self.state.get(key)
        if not isinstance(last, (int, float)):
            return 0
        return max(0, int(seconds - (self.clock() - last)))

    def mark(self, key: str) -> None:
        self.state[key] = self.clock()
        self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".extra_state_")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle)
            os.replace(tmp, self.path)  # atomic
        except OSError as exc:
            logger.warning("Could not save extra-source cooldown state: %s", exc)
