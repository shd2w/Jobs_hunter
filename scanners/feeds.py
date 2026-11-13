"""
Public remote-job feeds: Remotive, Jobicy, Arbeitnow, Remote OK, We Work Remotely.

Configure in ``config/portals.yml``::

    extra_sources:
      enabled: true
      feeds:
        remotive:       {enabled: true, category: "software-dev"}
        jobicy:         {enabled: true, geo: "anywhere", industry: "data-science", tag: "python"}
        arbeitnow:      {enabled: true, region: "de"}      # de | uk
        remoteok:       {enabled: true}
        weworkremotely: {enabled: false}

Each provider has its own terms (attribution, rate limits). Every job keeps its
original listing URL and a "Source:" line, and a per-feed cooldown is enforced
(Remotive asks for at most four fetches a day). Remote OK / Remotive terms ask
users not to republish their listings to other job boards: this tool is for
your own search only.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import xml.etree.ElementTree as ET

from .base import BaseScanner, JobPosting, ScanResult
from .net import (Cooldown, FetchError, fetch, fetch_json, html_to_text, https_url,
                  iso_date, safe_text)

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = {"remotive": 21600, "jobicy": 3600, "arbeitnow": 3600,
                    "remoteok": 3600, "weworkremotely": 3600}
SLUG = re.compile(r"[A-Za-z0-9_-]{1,50}")
TAG = re.compile(r"[A-Za-z0-9 _+#.-]{3,50}")
LABELS = {"remotive": "Remotive", "jobicy": "Jobicy", "arbeitnow": "Arbeitnow",
          "remoteok": "Remote OK", "weworkremotely": "We Work Remotely"}


def _with_source(description: str, feed: str, url: str) -> str:
    return f"{description}\n\nSource: {LABELS[feed]} - {url}".strip()[:9000]


def _remote_location(location: str, remote_only_board: bool = True, flag: bool | None = None) -> str:
    """Keep the provider's own location text so its geographic restriction
    ("USA Only", "Europe") still drives the location filter.

    "Remote" is added only when the provider explicitly flags the job remote,
    or when a remote-only board gives no location at all. Remote is a source
    flag, never proof that you are eligible from your country.
    """
    location = safe_text(location, 200)
    if flag is True:
        return location if "remote" in location.lower() else "Remote" + (f" · {location}" if location else "")
    if not location and remote_only_board:
        return "Remote"
    return location


def _salary(lo, hi, currency="", period="") -> str:
    nums = [f"{v:g}" for v in (lo, hi)
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0]
    return " ".join(x for x in (safe_text(currency, 8), "-".join(nums), safe_text(period, 12)) if x) if nums else ""


# ------------------------------------------------------------------ URL builders

def feed_url(feed: str, opts: dict) -> str:
    from urllib.parse import urlencode
    if feed == "remotive":
        params = {}
        if opts.get("category"):
            if not SLUG.fullmatch(str(opts["category"])):
                raise ValueError("Invalid Remotive category")
            params["category"] = opts["category"]
        return "https://remotive.com/api/remote-jobs" + ("?" + urlencode(params) if params else "")
    if feed == "jobicy":
        params = {"count": 50}
        for key, rule in (("geo", SLUG), ("industry", SLUG), ("tag", TAG)):
            if opts.get(key):
                if not rule.fullmatch(str(opts[key])):
                    raise ValueError(f"Invalid Jobicy {key}")
                params[key] = opts[key]
        return "https://jobicy.com/api/v2/remote-jobs?" + urlencode(params)
    if feed == "arbeitnow":
        region = str(opts.get("region", "de")).lower()
        if region not in ("de", "uk"):
            raise ValueError("Arbeitnow region must be de or uk")
        host = "www.arbeitnow.co.uk" if region == "uk" else "www.arbeitnow.com"
        return f"https://{host}/api/job-board-api?page=1"
    if feed == "remoteok":
        return "https://remoteok.com/api"
    if feed == "weworkremotely":
        return "https://weworkremotely.com/remote-jobs.rss"
    raise ValueError(f"Unsupported feed: {feed}")


# ------------------------------------------------------------------- parsers

def parse_remotive(data) -> list[JobPosting]:
    jobs = []
    for item in (data.get("jobs") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        url, title = https_url(item.get("url")), safe_text(item.get("title"))
        if not url or not title:
            continue
        jobs.append(JobPosting(
            title=title, url=url, company=safe_text(item.get("company_name"), 120),
            location=_remote_location(item.get("candidate_required_location")),
            date_posted=iso_date(item.get("publication_date")), source="feed-remotive",
            description=_with_source(html_to_text(item.get("description")), "remotive", url),
            salary=safe_text(item.get("salary"), 80)))
    return jobs


def parse_jobicy(data) -> list[JobPosting]:
    jobs = []
    for item in (data.get("jobs") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        url, title = https_url(item.get("url")), safe_text(item.get("jobTitle"))
        if not url or not title:
            continue
        geo = item.get("jobGeo")
        geo = ", ".join(map(str, geo)) if isinstance(geo, list) else geo
        jobs.append(JobPosting(
            title=title, url=url, company=safe_text(item.get("companyName"), 120),
            location=_remote_location(geo), date_posted=iso_date(item.get("pubDate")),
            source="feed-jobicy",
            description=_with_source(html_to_text(item.get("jobDescription")), "jobicy", url),
            salary=_salary(item.get("salaryMin"), item.get("salaryMax"),
                           item.get("salaryCurrency"), item.get("salaryPeriod"))))
    return jobs


def parse_arbeitnow(data) -> list[JobPosting]:
    jobs = []
    for item in (data.get("data") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        url, title = https_url(item.get("url")), safe_text(item.get("title"))
        if not url or not title:
            continue
        flag = item.get("remote") if isinstance(item.get("remote"), bool) else None
        # Arbeitnow lists on-site and remote roles; only mark Remote when flagged.
        location = _remote_location(item.get("location"), remote_only_board=False, flag=flag)
        jobs.append(JobPosting(
            title=title, url=url, company=safe_text(item.get("company_name"), 120),
            location=location, date_posted=iso_date(item.get("created_at")), source="feed-arbeitnow",
            description=_with_source(html_to_text(item.get("description")), "arbeitnow", url)))
    return jobs


def parse_remoteok(data) -> list[JobPosting]:
    if not isinstance(data, list):
        raise FetchError("Remote OK: unexpected payload")
    jobs = []
    for item in data:
        if not isinstance(item, dict) or ("legal" in item and "id" not in item):
            continue  # first element is the terms notice, not a vacancy
        url, title = https_url(item.get("url")), safe_text(item.get("position"))
        if not url or not title:
            continue
        jobs.append(JobPosting(
            title=title, url=url, company=safe_text(item.get("company"), 120),
            location=_remote_location(item.get("location")), date_posted=iso_date(item.get("date")),
            source="feed-remoteok",
            description=_with_source(html_to_text(item.get("description")), "remoteok", url),
            salary=_salary(item.get("salary_min"), item.get("salary_max"))))
    return jobs


def parse_weworkremotely(body: bytes) -> list[JobPosting]:
    # Stdlib parser: refuse DTDs/entities outright (billion-laughs / XXE).
    head = body[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in body.upper():
        raise FetchError("We Work Remotely: DTD/entities are not allowed in feeds")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise FetchError("We Work Remotely: malformed RSS") from exc
    if root.tag != "rss":
        raise FetchError("We Work Remotely: not an RSS document")
    jobs = []
    for item in root.findall("./channel/item"):
        label = (item.findtext("title") or "").strip()
        company, sep, title = label.partition(": ")
        url = https_url(item.findtext("link"))
        if not url or not (title if sep else label):
            continue
        jobs.append(JobPosting(
            title=safe_text(title if sep else label), url=url,
            company=safe_text(company if sep else "", 120),  # never invent a company
            location=_remote_location(item.findtext("region")),
            date_posted=safe_text(item.findtext("pubDate"), 40), source="feed-weworkremotely",
            description=_with_source(html_to_text(item.findtext("description")), "weworkremotely", url)))
    return jobs


# ------------------------------------------------------------------- scanner

class FeedScanner(BaseScanner):
    """Scans the feeds enabled under ``extra_sources.feeds``."""

    def __init__(self, config: dict, data_dir: str = "data", client=None, cooldown: Cooldown | None = None):
        super().__init__(config, name="feeds")
        raw = (config.get("extra_sources") or {}).get("feeds") or {}
        self.feeds = raw if isinstance(raw, dict) else {}
        self.client = client
        self.cooldown = cooldown or Cooldown(data_dir)

    async def scan(self) -> ScanResult:
        result = self._make_result()
        for feed, opts in self.feeds.items():
            opts = opts if isinstance(opts, dict) else {}
            if feed not in COOLDOWN_SECONDS:
                result.errors.append(f"{feed}: unsupported feed name")
                continue
            if not opts.get("enabled", False):
                continue
            wait = self.cooldown.remaining(f"feed:{feed}", COOLDOWN_SECONDS[feed])
            if wait:
                result.errors.append(f"{feed}: cooldown active, wait {wait}s (skipped, not an error)")
                continue
            try:
                jobs = await asyncio.to_thread(self._scan_feed, feed, opts)
                result.jobs.extend(jobs)
                self.cooldown.mark(f"feed:{feed}")
                self.logger.info("%s: %d jobs", feed, len(jobs))
            except FetchError as exc:
                note = " (blocked/rate-limited: not retrying, no bypass)" if exc.blocked else ""
                result.errors.append(f"{feed}: {exc}{note}")
                if exc.blocked:
                    self.cooldown.mark(f"feed:{feed}")
            except Exception as exc:
                result.errors.append(f"{feed}: {type(exc).__name__}: {exc}")
            await asyncio.sleep(0 if self.client is not None else 1.0)
        return self._finish_result(result)

    def _scan_feed(self, feed: str, opts: dict) -> list[JobPosting]:
        url = feed_url(feed, opts)
        if feed == "weworkremotely":
            body, content_type = fetch(url, "application/rss+xml, application/xml, text/xml", client=self.client)
            if "xml" not in content_type:
                raise FetchError("We Work Remotely did not return XML")
            return parse_weworkremotely(body)
        data = fetch_json(url, client=self.client)
        parser = {"remotive": parse_remotive, "jobicy": parse_jobicy, "arbeitnow": parse_arbeitnow,
                  "remoteok": parse_remoteok}[feed]
        return parser(data)
