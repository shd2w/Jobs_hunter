"""
Direct API scanner for companies using Workday, SmartRecruiters, or similar
public/semi-public career APIs.

IMPORTANT: Siemens does NOT use Workday — they use Eightfold.ai which has
no public API. Siemens jobs are discovered via JobSpy (LinkedIn/Indeed)
instead. See portals.yml for the correct scan_method per company.

Supported providers:
- workday: POST to /wday/cxs/{tenant}/{board}/jobs
- smartrecruiters: GET from /api/v1/search
"""

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
import re

import httpx

from .base import BaseScanner, JobPosting, ScanResult

logger = logging.getLogger(__name__)

# Known API endpoints — discovered by inspecting network traffic
# Only include companies with VERIFIED, working endpoints
# Note: Adidas/Puma use Eightfold.ai (no direct API support) — covered by JobSpy
KNOWN_ENDPOINTS = {
    "bosch": {
        "api_url": "https://careers.smartrecruiters.com/BoschGroup",
        "base_url": "https://www.bosch.com/careers/",
        "provider": "smartrecruiters",
    },
}

FETCH_TIMEOUT = 20
MAX_PAGES = 5
PAGE_SIZE = 20


@dataclass
class APIEndpoint:
    """A company API endpoint."""
    company_name: str
    api_url: str
    base_url: str
    provider: str  # "workday", "smartrecruiters", "eightfold"


class DirectAPIScanner(BaseScanner):
    """Scanner for companies with known public/semi-public APIs.
    
    This scanner only handles companies where we have a verified API endpoint.
    Companies without API access (like Siemens/Eightfold) are handled by
    JobSpy via LinkedIn/Indeed/Google instead.
    """

    def __init__(self, config: dict):
        super().__init__(config, name="direct-api")
        self.companies = self._load_companies()
        self.query_errors = []

    def _load_companies(self) -> list[APIEndpoint]:
        """Load companies with known API endpoints from config."""
        endpoints = []
        tracked = self.config.get("tracked_companies", [])

        for company in tracked:
            if not company.get("enabled", True):
                continue
            if company.get("scan_method") not in ("workday", "direct-api"):
                continue

            name_lower = company["name"].lower()
            # Explicit public Workday tenant configuration; no credentials or
            # inferred endpoints. Existing known-company configuration is kept.
            if company.get("api_url") and company.get("base_url"):
                api, base = company["api_url"], company["base_url"]
                parsed = urlsplit(api); public = urlsplit(base)
                if (parsed.scheme != "https" or public.scheme != "https"
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or public.username or public.password or public.hostname != parsed.hostname
                    or not re.fullmatch(r"[a-zA-Z0-9-]+\.wd[0-9]+\.myworkdayjobs\.com", parsed.hostname or "")
                    or not re.fullmatch(r"/wday/cxs/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/jobs", parsed.path)):
                    raise ValueError("Configure an explicit public HTTPS Workday tenant/board jobs endpoint")
                endpoints.append(APIEndpoint(company["name"], api, base, "workday"))
                continue

            if name_lower in KNOWN_ENDPOINTS:
                known = KNOWN_ENDPOINTS[name_lower]
                endpoints.append(APIEndpoint(
                    company_name=company["name"],
                    api_url=known["api_url"],
                    base_url=known["base_url"],
                    provider=known["provider"],
                ))
            else:
                self.logger.info(
                    f"No direct API for '{company['name']}' — "
                    f"will be covered by JobSpy scanner instead."
                )

        self.logger.info(f"Loaded {len(endpoints)} direct-API companies")
        return endpoints

    async def scan(self) -> ScanResult:
        """Scan all companies with direct API access."""
        result = self._make_result()
        self.query_errors = []

        for endpoint in self.companies:
            try:
                jobs = await self._scan_company(endpoint)
                result.jobs.extend(jobs)
            except Exception as e:
                error_msg = f"{endpoint.company_name}: {e}"
                result.errors.append(error_msg)
                self.logger.error(f"Error scanning {error_msg}")

        result.errors.extend(self.query_errors)
        return self._finish_result(result)

    async def _scan_company(self, endpoint: APIEndpoint) -> list[JobPosting]:
        """Scan a single company via its API."""
        search_terms = self._get_search_terms(endpoint.company_name)
        all_jobs = []

        for search_term in search_terms:
            try:
                if endpoint.provider == "workday":
                    jobs = await self._scan_workday(endpoint, search_term)
                elif endpoint.provider == "smartrecruiters":
                    jobs = await self._scan_smartrecruiters(endpoint, search_term)
                else:
                    # For unsupported providers, skip gracefully
                    self.logger.info(
                        f"{endpoint.company_name}: provider '{endpoint.provider}' "
                        f"not directly supported — skipping API scan"
                    )
                    continue

                all_jobs.extend(jobs)
            except Exception as e:
                self.query_errors.append(f"{endpoint.company_name} / {search_term}: {type(e).__name__}: {e}")
                self.logger.warning(self.query_errors[-1])

            await asyncio.sleep(1)  # Be polite between searches

        self.logger.info(f"{endpoint.company_name}: found {len(all_jobs)} jobs via API")
        return all_jobs

    async def _scan_workday(self, endpoint: APIEndpoint, search_text: str) -> list[JobPosting]:
        """Scan a Workday career portal."""
        all_jobs = []
        offset = 0

        for _ in range(MAX_PAGES):
            payload = {
                "appliedFacets": {},
                "limit": PAGE_SIZE,
                "offset": offset,
                "searchText": search_text,
            }

            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
                resp = await client.post(
                    endpoint.api_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    },
                )

                resp.raise_for_status()

                data = resp.json()
                total = data.get("total", 0)
                postings = data.get("jobPostings", [])

                for p in postings:
                    title = p.get("title", "")
                    external_path = p.get("externalPath", "")
                    url = f"{endpoint.base_url.rstrip(chr(47))}{external_path}" if external_path else ""

                    location = p.get("locationsText", "")
                    detail = {}
                    if external_path:
                        detail_url = endpoint.api_url.rsplit("/jobs", 1)[0] + external_path
                        try:
                            detail_response = await client.get(detail_url)
                            detail_response.raise_for_status()
                            detail = detail_response.json().get("jobPostingInfo", {})
                        except Exception as exc:
                            self.query_errors.append(f"{endpoint.company_name}: detail failed ({type(exc).__name__}); listing retained without invented details")
                    from jobhunter_app.sources import plain

                    all_jobs.append(JobPosting(
                        title=title,
                        url=url,
                        company=endpoint.company_name,
                        location=location,
                        date_posted=detail.get("startDate", ""),
                        description=plain(detail.get("jobDescription", "")),
                        employment_type=detail.get("timeType", ""),
                        source=f"workday-{endpoint.company_name.lower()}",
                    ))

                if offset + PAGE_SIZE >= total:
                    break
                offset += PAGE_SIZE
                await asyncio.sleep(0.5)

        return all_jobs

    async def _scan_smartrecruiters(self, endpoint: APIEndpoint, search_text: str) -> list[JobPosting]:
        """Scan SmartRecruiters API."""
        jobs = []
        # Display names are not SmartRecruiters account IDs (BoschGroup != Bosch).
        account = urlsplit(endpoint.api_url).path.rstrip("/").split("/")[-1]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", account):
            raise ValueError("Invalid SmartRecruiters account")
        from jobhunter_app.sources import Source, normalize
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT) as client:
            for page in range(MAX_PAGES):
                response = await client.get(
                    f"https://api.smartrecruiters.com/v1/companies/{account}/postings",
                    params={"q": search_text, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE})
                response.raise_for_status()
                data = response.json()
                entries = data.get("content")
                if not isinstance(entries, list): raise ValueError("Invalid SmartRecruiters list")
                for item in entries:
                    identity = str(item.get("id", ""))
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identity):
                        raise ValueError("Invalid posting identity")
                    await asyncio.sleep(0.6)
                    try:
                        detail = await client.get(f"https://api.smartrecruiters.com/v1/companies/{account}/postings/{identity}")
                        detail.raise_for_status()
                        detail_data = detail.json()
                    except Exception as exc:
                        self.query_errors.append(f"{endpoint.company_name}: detail {identity} failed ({type(exc).__name__}); other jobs retained")
                        continue
                    rows = normalize(Source("smartrecruiters", account), {"content": [detail_data]})
                    for row in rows:
                        jobs.append(JobPosting(**{key: row.get(key, "") for key in
                            ("title", "url", "company", "location", "description", "date_posted", "salary", "employment_type")},
                            source="smartrecruiters-" + account))
                if not entries or (page + 1) * PAGE_SIZE >= data.get("totalFound", len(entries)): break
                await asyncio.sleep(0.6)
        return jobs

    def _get_search_terms(self, company_name: str) -> list[str]:
        """Get search terms for a company from config."""
        for c in self.config.get("tracked_companies", []):
            if c["name"] == company_name:
                return c.get("search_terms", ["working student"])
        return ["working student"]
