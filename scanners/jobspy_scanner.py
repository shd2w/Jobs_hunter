"""
JobSpy scanner — wraps python-jobspy to search all pinned JobSpy providers.

Returns normalized JobPosting objects from all configured search queries.
Handles rate limits and errors per-site gracefully.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

# numpy must be imported BEFORE jobspy to suppress floating-point
# exception traps that cause "longdouble infinity to integer" crashes
# on Python 3.14 + numpy 2.4 (https://github.com/numpy/numpy/issues/...)
try:
    import numpy as np
    np.seterr(all="ignore")
except ImportError:
    pass

from .base import BaseScanner, JobPosting, ScanResult

logger = logging.getLogger(__name__)


class ProviderFailure(RuntimeError):
    """Structured provider failure; no response body is persisted in source health."""
    def __init__(self, errors):
        import re
        match = re.search(r'(?:status code|HTTP)\s*(401|403|429)', str(errors), re.I)
        self.http_status = int(match[1]) if match else None
        super().__init__('JobSpy provider failure: ' + '; '.join(f'{k}: {v}' for k, v in errors.items()))


def clean(value):
    """Do not invent fields or stringify pandas missing-value sentinels."""
    if value is None: return ""
    text = str(value)
    return "" if text in ("nan", "NaN", "NaT", "None", "<NA>") else text



class JobSpyScanner(BaseScanner):
    """Scanner using python-jobspy for all pinned JobSpy providers."""

    def __init__(self, config: dict):
        super().__init__(config, name="jobspy")
        self.searches = self._load_searches(config)
        self.last_errors = {}
        self.last_warnings = {}

    @staticmethod
    def _load_searches(config: dict) -> list[dict]:
        from .jobspy_registry import SITES
        searches = JobSpyScanner._load_primary(config)
        providers = config.get('jobspy_providers', {})
        if not isinstance(providers, dict): raise ValueError('jobspy_providers must be a mapping')
        primary = config.get('jobspy_searches', {})
        terms = primary.get('terms', []) if isinstance(primary, dict) else []
        for site, options in providers.items():
            if site not in SITES or not isinstance(options, dict):
                raise ValueError('Unsupported JobSpy provider configuration')
            if not options.get('enabled', True): continue
            raw = {'terms': terms, 'results_wanted': 30, **options, 'sites': [site]}
            searches.extend(JobSpyScanner._load_primary({'jobspy_searches': raw}))
        return searches

    @staticmethod
    def _load_primary(config: dict) -> list[dict]:
        """Load search configs, supporting both compact and legacy formats.

        Compact format (terms × locations cross-product):
            jobspy_searches:
              terms: ["Working Student", "Werkstudent"]
              locations: ["Erlangen, Germany", "Munich, Germany"]
              sites: ["indeed", "linkedin", "google"]
              results_wanted: 50
              distance_km: 50

        Legacy format (explicit per-search entries):
            jobspy_searches:
              - term: "Working Student"
                location: "Erlangen, Germany"
                ...
        """
        raw = config.get("jobspy_searches", {})

        # Legacy format: list of dicts
        if isinstance(raw, list):
            return [s for s in raw if s.get("enabled", True)]

        # Compact format: dict with terms + locations
        terms = raw.get("terms", [])
        locations = raw.get("locations", [])
        if not terms or not locations:
            return []

        sites = raw.get("sites", ["indeed", "linkedin", "google"])
        results_wanted = raw.get("results_wanted", 50)
        distance_km = raw.get("distance_km", None)

        searches = []
        for term in terms:
            for location in locations:
                entry = {
                    "term": term,
                    "location": location,
                    "sites": sites,
                    "results_wanted": results_wanted,
                }
                if distance_km:
                    entry["distance_km"] = distance_km
                for key in ("pages", "hours_old", "fetch_description", "country_indeed", "is_remote", "scope_notice"):
                    if key in raw: entry[key] = raw[key]
                searches.append(entry)

        return searches

    async def scan(self) -> ScanResult:
        """Execute all configured JobSpy searches."""
        result = self._make_result()

        if not self.searches:
            self.logger.warning("No jobspy_searches configured in portals.yml")
            return self._finish_result(result)

        # Run jobspy in a thread pool since it's synchronous + blocking
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            for search_config in self.searches:
                try:
                    jobs = await loop.run_in_executor(
                        executor, self._run_search, search_config
                    )
                    result.jobs.extend(jobs)
                    result.errors.extend(f"{site}: {message}" for site, message in self.last_errors.items())
                except Exception as e:
                    error_msg = (
                        f"JobSpy search '{search_config.get('term', '?')}' "
                        f"in '{search_config.get('location', '?')}': {e}"
                    )
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)

                # Delay between searches to avoid rate limits
                await asyncio.sleep(2.0)

        return self._finish_result(result)

    def _run_search(self, search_config: dict) -> list[JobPosting]:
        """Run a single JobSpy search (synchronous, runs in thread)."""
        term = search_config.get("term", "Working Student")
        location = search_config.get("location", "Erlangen, Germany")

        try:
            return self._do_search(search_config)
        except Exception as e:
            self.logger.warning(
                f"JobSpy search '{term}' in '{location}' failed: "
                f"{type(e).__name__}: {e}"
            )
            raise

    def _do_search(self, search_config: dict) -> list[JobPosting]:
        """Inner search logic — separated so errors are always caught."""
        try:
            from jobspy import scrape_jobs
        except ImportError:
            raise ImportError(
                "python-jobspy not installed. Run: pip install python-jobspy"
            )

        term = search_config.get("term", "Working Student")
        location = search_config.get("location", "Erlangen, Germany")
        sites = search_config.get("sites", ["indeed", "google"])
        results_wanted = search_config.get("results_wanted", 30)
        distance_km = search_config.get("distance_km", None)

        self.logger.info(
            f"Searching '{term}' in '{location}' on {sites} "
            f"(want {results_wanted} results)"
        )

        # Determine country_indeed dynamically: search config -> global config -> infer from location
        country_indeed = search_config.get("country_indeed") or self.config.get("country_indeed")
        if not country_indeed:
            loc_lower = location.lower()
            if any(c in loc_lower for c in ["oman", "muscat", "sohar", "salalah", "nizwa", "duqm"]):
                country_indeed = "Oman"
            elif any(c in loc_lower for c in ["egypt", "cairo", "alexandria", "giza"]):
                country_indeed = "Egypt"
            elif any(c in loc_lower for c in ["uae", "united arab emirates", "dubai", "abu dhabi", "sharjah"]):
                country_indeed = "United Arab Emirates"
            elif any(c in loc_lower for c in ["switzerland", "swiss", "schweiz", "suisse", "zurich", "zürich", "geneva", "basel", "bern"]):
                country_indeed = "Switzerland"
            elif any(c in loc_lower for c in ["austria", "österreich", "vienna", "wien", "graz", "linz", "salzburg"]):
                country_indeed = "Austria"
            elif any(c in loc_lower for c in ["germany", "deutschland", "berlin", "munich", "münchen", "frankfurt", "erlangen", "nürnberg"]):
                country_indeed = "Germany"
            elif any(c in loc_lower for c in ["remote", "worldwide", "anywhere", "global"]):
                country_indeed = "USA"
            else:
                country_indeed = "USA"

        is_remote = search_config.get("is_remote", False)
        if not is_remote and any(r in location.lower() for r in ["remote", "worldwide", "anywhere", "global"]):
            is_remote = True

        kwargs = {
            "site_name": sites,
            "search_term": term,
            "location": location,
            "results_wanted": results_wanted,
            "country_indeed": country_indeed,
        }
        if is_remote:
            kwargs["is_remote"] = True

        # distance parameter (if supported by the jobspy version)
        if distance_km:
            kwargs["distance"] = distance_km

        # JobSpy preserves per-provider failures in DataFrame.attrs. An empty
        # frame is not proof of a successful search.
        kwargs.update(offset=int(search_config.get("offset", 0)),
                      fetch_description=search_config.get("fetch_description", True),
                      linkedin_fetch_description=search_config.get("fetch_description", True))
        if search_config.get("hours_old") is not None:
            kwargs["hours_old"] = int(search_config["hours_old"])
        if "google" in sites:
            kwargs["google_search_term"] = search_config.get("google_search_term", f"{term} jobs in {location}")
        self.last_errors = {}; self.last_warnings = {}
        from .jobspy_registry import SITES
        unknown = set(sites) - set(SITES)
        if unknown: raise ValueError('Unsupported JobSpy sites: ' + ', '.join(sorted(unknown)))
        df = scrape_jobs(**kwargs)
        attrs = getattr(df, "attrs", {})
        self.last_errors = dict(attrs.get("errors") or {})
        self.last_warnings = dict(attrs.get("warnings") or {})
        if self.last_errors and (df is None or df.empty):
            raise ProviderFailure(self.last_errors)

        if df is None or df.empty:
            self.logger.info(f"No results for '{term}' in '{location}'")
            return []

        jobs = []
        for _, row in df.iterrows():
            try:
                url = clean(row.get("job_url"))
                title = clean(row.get("title"))
                if not url.startswith(("https://", "http://")) or not title:
                    continue
                company = clean(row.get("company"))
                location_str = clean(row.get("location"))
                # Only a provider-declared remote flag is a remote fact. Keep
                # the original country: remote does not mean globally eligible.
                if clean(row.get('is_remote')).lower() == 'true' and 'remote' not in location_str.lower():
                    location_str = 'Remote' + (' · ' + location_str if location_str else '')
                description = clean(row.get("description"))
                date_posted = clean(row.get("date_posted"))
                import math
                amounts = []
                for key in ("min_amount", "max_amount"):
                    try:
                        value = float(row.get(key))
                        if math.isfinite(value): amounts.append(f"{value:g}")
                    except (ValueError, TypeError, OverflowError): pass
                salary = " ".join(x for x in (clean(row.get("currency")), "-".join(amounts), clean(row.get("interval"))) if x) if amounts else ""

                # Determine source site
                site = str(row.get("site", "jobspy"))

                jobs.append(JobPosting(
                    title=title,
                    url=url,
                    company=company,
                    location=location_str,
                    date_posted=date_posted,
                    source=f"jobspy-{site}",
                    description=description,
                    employment_type=clean(row.get("job_type")),
                    salary=salary,
                ))
            except Exception as e:
                self.logger.debug(f"Skipping row due to error: {e}")
                continue

        self.logger.info(
            f"Got {len(jobs)} results for '{term}' in '{location}'"
        )
        return jobs


def bounded_search(config, site, term=None, location=None, limit=10):
    """Pick the provider's native configured scope for CLI verification."""
    from .jobspy_registry import SITES
    if site not in SITES: raise ValueError('Unsupported JobSpy provider')
    matches = [s for s in JobSpyScanner(config).searches if site in s.get('sites', [])]
    if not matches: raise ValueError('No searches configured for this provider')
    preferred = next((s for s in matches if s.get('location') == 'Germany'), matches[0])
    search = {**preferred, 'sites': [site], 'results_wanted': max(1, min(100, limit)), 'offset': 0}
    if term: search['term'] = term
    if location:
        search['location'] = location
        # An explicit override must not reuse a previous region's country.
        search.pop('country_indeed', None)
    return search
