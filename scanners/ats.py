"""
Public employer job boards: Greenhouse, Lever, Ashby, SmartRecruiters.

Configure the employers you care about in ``config/portals.yml``::

    extra_sources:
      enabled: true
      ats:
        - {kind: greenhouse,      id: "examplecompany", name: "Example Company"}
        - {kind: lever,           id: "examplecompany"}
        - {kind: ashby,           id: "examplecompany"}
        - {kind: smartrecruiters, id: "ExampleCompany1"}

``id`` is the public board slug (the part of the company's careers URL).
Output is the normal ``JobPosting`` so jobs flow through the existing
filter -> dedup -> pipeline.md -> scoring path unchanged.

Public API availability is not blanket permission: review each employer's
terms. Scans are small, spaced out and cooled down; no bypass of any kind.
"""

from __future__ import annotations

import asyncio
import logging
import re

from .base import BaseScanner, JobPosting, ScanResult
from .net import (ATS_MAX_BYTES, Cooldown, FetchError, fetch_json, html_to_text,
                  https_url, iso_date, safe_text)

logger = logging.getLogger(__name__)

SLUG = re.compile(r"[A-Za-z0-9_-]{1,80}")
COOLDOWN_SECONDS = {"greenhouse": 60, "lever": 60, "ashby": 600, "smartrecruiters": 600}
SR_MAX_DETAILS = 10          # detail requests per board per scan
SR_LIST_LIMIT = 100


def board_url(kind: str, slug: str) -> str:
    if kind == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    if kind == "lever":
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if kind == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    if kind == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit={SR_LIST_LIMIT}&offset=0"
    raise ValueError(f"Unsupported ATS kind: {kind}")


# ------------------------------------------------------------------- parsers
# Pure functions: payload -> list[JobPosting]. Malformed single rows are skipped.

def parse_greenhouse(data, company: str) -> list[JobPosting]:
    jobs = []
    for item in (data.get("jobs") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict):
            continue
        url, title = https_url(item.get("absolute_url")), safe_text(item.get("title"))
        if not url or not title:
            continue
        location = item.get("location")
        jobs.append(JobPosting(
            title=title, url=url, company=company,
            location=safe_text(location.get("name") if isinstance(location, dict) else ""),
            date_posted=iso_date(item.get("updated_at") or item.get("first_published")),
            source="ats-greenhouse", description=html_to_text(item.get("content")),
        ))
    return jobs


def parse_lever(data, company: str) -> list[JobPosting]:
    jobs = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        url, title = https_url(item.get("hostedUrl")), safe_text(item.get("text"))
        if not url or not title:
            continue
        cats = item.get("categories") if isinstance(item.get("categories"), dict) else {}
        description = item.get("descriptionPlain") or html_to_text(item.get("description"))
        for section in item.get("lists") or []:
            if isinstance(section, dict):
                description += "\n" + safe_text(section.get("text"), 120) + "\n" + html_to_text(section.get("content"))
        jobs.append(JobPosting(
            title=title, url=url, company=company, location=safe_text(cats.get("location")),
            date_posted=iso_date(item.get("createdAt")), source="ats-lever",
            description=description.strip()[:8000], salary=safe_text(item.get("salaryDescription")),
        ))
    return jobs


def parse_ashby(data, company: str) -> list[JobPosting]:
    jobs = []
    for item in (data.get("jobs") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict) or item.get("isListed") is not True:
            continue  # never promote direct-link-only / unlisted roles
        url, title = https_url(item.get("jobUrl")), safe_text(item.get("title"))
        if not url or not title:
            continue
        comp = item.get("compensation") if isinstance(item.get("compensation"), dict) else {}
        jobs.append(JobPosting(
            title=title, url=url, company=company, location=safe_text(item.get("location")),
            date_posted=iso_date(item.get("publishedAt")), source="ats-ashby",
            description=(item.get("descriptionPlain") or html_to_text(item.get("descriptionHtml")))[:8000],
            salary=safe_text(comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary")),
        ))
    return jobs


def parse_smartrecruiters_list(data) -> list[dict]:
    """Listing rows (no description yet): id, name, location, date, company."""
    rows = []
    for item in (data.get("content") if isinstance(data, dict) else None) or []:
        if not isinstance(item, dict) or item.get("active") is False:
            continue
        pid, name = safe_text(item.get("id"), 80), safe_text(item.get("name"))
        if not pid or not name or not SLUG.fullmatch(pid):
            continue
        loc = item.get("location") if isinstance(item.get("location"), dict) else {}
        place = ", ".join(safe_text(loc.get(k), 80) for k in ("city", "region", "country") if loc.get(k))
        if loc.get("remote") is True and "remote" not in place.lower():
            place = "Remote" + (f" · {place}" if place else "")
        comp = item.get("company") if isinstance(item.get("company"), dict) else {}
        rows.append({"id": pid, "title": name, "location": place,
                     "date": iso_date(item.get("releasedDate")),
                     "company": safe_text(comp.get("name"), 120)})
    return rows


def parse_smartrecruiters_detail(detail) -> tuple[str, str]:
    """(public_url, description) from a posting detail payload."""
    if not isinstance(detail, dict):
        return "", ""
    sections = (detail.get("jobAd") or {}).get("sections") if isinstance(detail.get("jobAd"), dict) else None
    parts = []
    if isinstance(sections, dict):
        for sec in sections.values():
            if isinstance(sec, dict):
                parts.append(html_to_text(sec.get("text"), 4000))
    return https_url(detail.get("postingUrl") or detail.get("applyUrl")), "\n\n".join(p for p in parts if p)[:8000]


# ------------------------------------------------------------------- scanner

class AtsScanner(BaseScanner):
    """Scans the employer boards listed in ``extra_sources.ats``."""

    def __init__(self, config: dict, data_dir: str = "data", client=None, cooldown: Cooldown | None = None,
                 sleep=asyncio.sleep, title_filter=None):
        super().__init__(config, name="ats")
        raw = (config.get("extra_sources") or {}).get("ats") or []
        self.boards = raw if isinstance(raw, list) else []
        self.client, self.sleep = client, sleep
        self.cooldown = cooldown or Cooldown(data_dir)
        if title_filter is None:
            from utils.filters import TitleFilter
            title_filter = TitleFilter(config)
        self.title_filter = title_filter

    async def scan(self) -> ScanResult:
        result = self._make_result()
        if not self.boards:
            self.logger.info("No extra_sources.ats boards configured")
            return self._finish_result(result)
        for board in self.boards:
            kind = str(board.get("kind", "")).lower() if isinstance(board, dict) else ""
            slug = str(board.get("id", "")) if isinstance(board, dict) else ""
            label = f"{kind}:{slug}"
            if kind not in COOLDOWN_SECONDS or not SLUG.fullmatch(slug):
                result.errors.append(f"{label}: invalid board entry (kind/id)")
                continue
            if board.get("enabled", True) is False:
                continue
            # SmartRecruiters requires explicit authorization before scanning.
            if kind == "smartrecruiters" and board.get("authorized") is not True:
                result.errors.append(f"{label}: not authorized (set authorized: true to enable)")
                continue
            # disabled_by_policy: board is disabled by policy decision, report but skip.
            if board.get("disabled_by_policy") is True:
                result.errors.append(f"{label}: disabled_by_policy (skipped per policy)")
                continue
            wait = self.cooldown.remaining(f"ats:{label}", COOLDOWN_SECONDS[kind])
            if wait:
                result.errors.append(f"{label}: cooldown active, wait {wait}s (skipped, not an error)")
                continue
            company = safe_text(board.get("name") or slug, 120)
            try:
                jobs = await asyncio.to_thread(self._scan_board, kind, slug, company)
                result.jobs.extend(jobs)
                self.cooldown.mark(f"ats:{label}")
                self.logger.info("%s: %d jobs", label, len(jobs))
            except FetchError as exc:
                note = " (blocked: skipping this board, no retry/bypass)" if exc.blocked else ""
                result.errors.append(f"{label}: {exc}{note}")
                if exc.blocked:
                    self.cooldown.mark(f"ats:{label}")  # do not retry immediately
            except Exception as exc:  # one bad board must not stop the others
                result.errors.append(f"{label}: {type(exc).__name__}: {exc}")
            await self.sleep(0.5)
        return self._finish_result(result)

    def _scan_board(self, kind: str, slug: str, company: str) -> list[JobPosting]:
        data = fetch_json(board_url(kind, slug), client=self.client, max_bytes=ATS_MAX_BYTES)
        if kind == "greenhouse":
            return parse_greenhouse(data, company)
        if kind == "lever":
            return parse_lever(data, company)
        if kind == "ashby":
            return parse_ashby(data, company)
        return self._smartrecruiters(data, slug, company)

    def _smartrecruiters(self, data, slug: str, company: str) -> list[JobPosting]:
        import time
        jobs, details = [], 0
        for row in parse_smartrecruiters_list(data):
            display = row["company"] or company
            public = f"https://jobs.smartrecruiters.com/{slug}/{row['id']}"
            description = ""
            # Spend the small detail budget only on titles that pass the filter.
            if details < SR_MAX_DETAILS and self.title_filter.matches(row["title"]):
                details += 1
                try:
                    detail = fetch_json(
                        f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{row['id']}",
                        client=self.client)
                    url, description = parse_smartrecruiters_detail(detail)
                    public = url or public
                except FetchError as exc:
                    self.logger.warning("SmartRecruiters detail %s failed: %s", row["id"], exc)
                    if exc.blocked:
                        details = SR_MAX_DETAILS  # stop spending requests
                time.sleep(0.6 if self.client is None else 0)
            jobs.append(JobPosting(title=row["title"], url=public, company=display,
                                   location=row["location"], date_posted=row["date"],
                                   source="ats-smartrecruiters", description=description))
        return jobs
