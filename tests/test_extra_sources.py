"""Tests for the optional ATS + feed scanners and the JobSpy provider upgrade.

ALL network access here is MOCKED (httpx.MockTransport / a fake ``jobspy``
module). Passing these tests proves parsing, safety rules and wiring; it does
not prove that any real provider currently returns this shape.
"""

import asyncio
import json
import sys
import types

import httpx
import pandas as pd
import pytest

from scanners import ats, feeds, net
from scanners.base import JobPosting, ScanResult
from scanners.bridge import PipelineBridge
from scanners.jobspy_scanner import JobSpyScanner, ProviderFailure, clean
from scanners.net import Cooldown, FetchError


def run(coro):
    return asyncio.run(coro)


def client_for(routes: dict, calls: list | None = None):
    """MockTransport client; ``routes`` maps URL-substring -> (status, body, ctype)."""
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(str(request.url))
        for needle, (status, body, ctype) in routes.items():
            if needle in str(request.url):
                content = body if isinstance(body, (bytes, str)) else json.dumps(body)
                return httpx.Response(status, content=content, headers={"content-type": ctype})
        return httpx.Response(404, content="nope", headers={"content-type": "text/plain"})
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


JSON = "application/json"


# ---------------------------------------------------------------- net helpers

def test_html_to_text_handles_escaped_html_and_scripts():
    escaped = "&lt;p&gt;Build &amp;amp; ship&lt;/p&gt;&lt;script&gt;alert(1)&lt;/script&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;"
    text = net.html_to_text(escaped)
    assert "Build & ship" in text and "Python" in text
    assert "<" not in text and "alert" not in text


def test_fetch_refuses_other_hosts_http_and_redirects():
    with pytest.raises(FetchError):
        net.fetch("https://evil.example.com/x", client=client_for({}))
    with pytest.raises(FetchError):
        net.fetch("http://remotive.com/api/remote-jobs", client=client_for({}))
    redirect = client_for({"remotive.com": (302, "", JSON)})
    with pytest.raises(FetchError) as exc:
        net.fetch("https://remotive.com/api/remote-jobs", client=redirect)
    assert "Redirect" in str(exc.value)


def test_fetch_size_cap_and_blocked_flags():
    big = client_for({"remotive.com": (200, "x" * 5000, JSON)})
    with pytest.raises(FetchError):
        net.fetch("https://remotive.com/api/remote-jobs", client=big, max_bytes=1000)
    for code in (401, 403, 429):
        err = None
        try:
            net.fetch("https://remotive.com/api/remote-jobs", client=client_for({"remotive": (code, "", JSON)}))
        except FetchError as exc:
            err = exc
        assert err and err.blocked and err.status == code


def test_cooldown_persists_and_expires(tmp_path):
    now = [1000.0]
    cd = Cooldown(tmp_path, clock=lambda: now[0])
    assert cd.remaining("a", 60) == 0
    cd.mark("a")
    assert Cooldown(tmp_path, clock=lambda: now[0]).remaining("a", 60) == 60  # reloaded from disk
    now[0] += 61
    assert cd.remaining("a", 60) == 0


def test_cooldown_survives_corrupt_state_file(tmp_path):
    (tmp_path / "extra_sources_state.json").write_text("{not json", encoding="utf-8")
    assert Cooldown(tmp_path).remaining("x", 10) == 0


# ------------------------------------------------------------------ ATS parsers

def test_parse_greenhouse():
    data = {"jobs": [
        {"title": "ML Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
         "location": {"name": "Berlin"}, "content": "&lt;p&gt;Python &amp;amp; LLMs&lt;/p&gt;",
         "updated_at": "2026-10-01T10:00:00Z"},
        {"title": "No url"}, "garbage", {"absolute_url": "https://x/y"},
    ]}
    jobs = ats.parse_greenhouse(data, "Acme")
    assert len(jobs) == 1
    j = jobs[0]
    assert (j.company, j.location, j.source) == ("Acme", "Berlin", "ats-greenhouse")
    assert "Python & LLMs" in j.description and "<" not in j.description


def test_parse_lever_joins_lists_and_epoch_ms():
    data = [{"text": "Backend Dev", "hostedUrl": "https://jobs.lever.co/acme/1", "createdAt": 1790000000000,
             "categories": {"location": "Remote"}, "descriptionPlain": "Intro",
             "lists": [{"text": "Requirements", "content": "<li>Python</li>"}]}]
    j = ats.parse_lever(data, "Acme")[0]
    assert j.location == "Remote" and "Requirements" in j.description and "Python" in j.description
    assert j.date_posted.startswith("20")


def test_parse_ashby_skips_unlisted():
    data = {"jobs": [
        {"title": "Listed", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "isListed": True,
         "descriptionPlain": "d", "compensation": {"compensationTierSummary": "EUR 60k"}},
        {"title": "Hidden", "jobUrl": "https://jobs.ashbyhq.com/acme/2", "isListed": False},
        {"title": "Missing flag", "jobUrl": "https://jobs.ashbyhq.com/acme/3"},
    ]}
    jobs = ats.parse_ashby(data, "Acme")
    assert [j.title for j in jobs] == ["Listed"] and jobs[0].salary == "EUR 60k"


def test_smartrecruiters_list_and_detail():
    listing = {"content": [
        {"id": "743999", "name": "Data Scientist", "releasedDate": "2026-10-02T00:00:00Z",
         "location": {"city": "Munich", "country": "de", "remote": True}, "company": {"name": "Acme GmbH"}},
        {"id": "bad id!", "name": "Rejected id"}, {"id": "1", "name": "Inactive", "active": False},
    ]}
    rows = ats.parse_smartrecruiters_list(listing)
    assert len(rows) == 1 and rows[0]["location"].startswith("Remote")
    url, desc = ats.parse_smartrecruiters_detail(
        {"postingUrl": "https://jobs.smartrecruiters.com/acme/743999",
         "jobAd": {"sections": {"jobDescription": {"text": "<p>Build models</p>"}}}})
    assert url.endswith("743999") and desc == "Build models"


# ------------------------------------------------------------------ ATS scanner

def make_ats(tmp_path, boards, routes, calls=None, **kw):
    cfg = {"extra_sources": {"ats": boards}, "title_filter": {"positive": ["data", "engineer"], "negative": []}}
    async def no_sleep(_): return None
    return ats.AtsScanner(cfg, data_dir=str(tmp_path), client=client_for(routes, calls), sleep=no_sleep, **kw)


def test_ats_scanner_collects_and_cools_down(tmp_path):
    routes = {"boards-api.greenhouse.io/v1/boards/acme/jobs": (200, {"jobs": [
        {"title": "Data Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/9", "content": "x"}]}, JSON)}
    calls = []
    scanner = make_ats(tmp_path, [{"kind": "greenhouse", "id": "acme", "name": "Acme"}], routes, calls)
    res = run(scanner.scan())
    assert res.job_count == 1 and not res.errors and len(calls) == 1
    res2 = run(scanner.scan())  # second scan inside the cooldown: no request
    assert res2.job_count == 0 and "cooldown" in res2.errors[0] and len(calls) == 1


def test_ats_scanner_reports_bad_entries_and_isolated_failures(tmp_path):
    routes = {"api.lever.co/v0/postings/gone": (404, "", JSON),
              "api.ashbyhq.com": (200, {"jobs": [{"title": "Eng", "jobUrl": "https://jobs.ashbyhq.com/a/1", "isListed": True}]}, JSON)}
    boards = [{"kind": "lever", "id": "gone"}, {"kind": "nope", "id": "x"}, {"kind": "greenhouse", "id": "../etc"},
              {"kind": "ashby", "id": "acme"}]
    res = run(make_ats(tmp_path, boards, routes).scan())
    assert res.job_count == 1  # the good board still worked
    text = " | ".join(res.errors)
    assert "lever:gone" in text and "invalid board entry" in text


def test_ats_blocked_board_is_not_retried(tmp_path):
    routes = {"api.lever.co": (429, "", JSON)}
    calls = []
    scanner = make_ats(tmp_path, [{"kind": "lever", "id": "acme"}], routes, calls)
    res = run(scanner.scan())
    assert "blocked" in res.errors[0]
    run(scanner.scan())
    assert len(calls) == 1  # cooled down after a block, no immediate retry


def test_smartrecruiters_detail_budget_and_title_filter(tmp_path):
    content = [{"id": str(1000 + i), "name": f"Data Engineer {i}"} for i in range(15)]
    content.append({"id": "9999", "name": "Barista"})
    detail = {"postingUrl": "https://jobs.smartrecruiters.com/acme/x", "jobAd": {"sections": {"a": {"text": "desc"}}}}
    routes = {"/postings/1": (200, detail, JSON), "/postings?limit": (200, {"content": content}, JSON)}
    calls = []
    res = run(make_ats(tmp_path, [{"kind": "smartrecruiters", "id": "acme"}], routes, calls).scan())
    detail_calls = [c for c in calls if "/postings/" in c]
    assert len(detail_calls) == ats.SR_MAX_DETAILS            # bounded
    assert not any("9999" in c for c in calls)                 # filtered-out title costs no request
    assert res.job_count == 16                                 # all listed, details only for a few


# ---------------------------------------------------------------- feed parsers

def test_parse_remotive_jobicy_arbeitnow_remoteok():
    remotive = feeds.parse_remotive({"jobs": [{"title": "Py Dev", "url": "https://remotive.com/remote-jobs/1",
                                               "company_name": "Co", "candidate_required_location": "Worldwide",
                                               "description": "<b>Hi</b>", "publication_date": "2026-10-01T00:00:00"}]})
    assert remotive[0].location == "Worldwide" and "Source: Remotive" in remotive[0].description

    jobicy = feeds.parse_jobicy({"jobs": [{"jobTitle": "Data Analyst", "url": "https://jobicy.com/jobs/1",
                                           "companyName": "J", "jobGeo": ["Europe", "UK"],
                                           "jobDescription": "<p>x</p>", "salaryMin": 50000, "salaryMax": 60000,
                                           "salaryCurrency": "EUR", "salaryPeriod": "yearly"}]})
    assert jobicy[0].salary == "EUR 50000-60000 yearly" and "Europe, UK" in jobicy[0].location

    an = feeds.parse_arbeitnow({"data": [
        {"title": "A", "url": "https://www.arbeitnow.com/jobs/a", "company_name": "C", "location": "Berlin", "remote": False,
         "description": "d", "created_at": 1790000000},
        {"title": "B", "url": "https://www.arbeitnow.com/jobs/b", "company_name": "C", "location": "Hamburg", "remote": True},
        {"title": "C", "url": "https://www.arbeitnow.com/jobs/c", "company_name": "C", "location": "Köln"}]})
    assert [j.location for j in an] == ["Berlin", "Remote · Hamburg", "Köln"]  # on-site is never labelled remote

    assert feeds.parse_remotive({"jobs": [{"title": "T", "url": "https://remotive.com/2"}]})[0].location == "Remote"
    ro = feeds.parse_remoteok([{"legal": "terms"}, {"id": "1", "position": "ML", "company": "X",
                                                    "url": "https://remoteok.com/remote-jobs/1", "salary_min": 0, "salary_max": 90000}])
    assert len(ro) == 1 and ro[0].salary == "90000"


def test_parse_weworkremotely_and_xml_attack_rejected():
    rss = (b"<?xml version='1.0'?><rss><channel><item><title>Acme: Python Dev</title>"
           b"<link>https://weworkremotely.com/remote-jobs/1</link><region>Anywhere</region>"
           b"<description>&lt;p&gt;hi&lt;/p&gt;</description></item>"
           b"<item><title>No company here</title><link>https://weworkremotely.com/remote-jobs/2</link></item></channel></rss>")
    jobs = feeds.parse_weworkremotely(rss)
    assert (jobs[0].company, jobs[0].title) == ("Acme", "Python Dev")
    assert jobs[1].company == ""                           # never invent a company
    evil = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><rss><channel/></rss>'
    with pytest.raises(FetchError):
        feeds.parse_weworkremotely(evil)


def test_feed_url_validation():
    assert "category=software-dev" in feeds.feed_url("remotive", {"category": "software-dev"})
    assert "count=50" in feeds.feed_url("jobicy", {"geo": "anywhere"})
    assert feeds.feed_url("arbeitnow", {"region": "uk"}).startswith("https://www.arbeitnow.co.uk/")
    for bad in ({"category": "a&b=c"}, {"category": "../x"}):
        with pytest.raises(ValueError):
            feeds.feed_url("remotive", bad)
    with pytest.raises(ValueError):
        feeds.feed_url("arbeitnow", {"region": "evil.com"})
    with pytest.raises(ValueError):
        feeds.feed_url("jobicy", {"tag": "x"})  # too short for the documented 3-50 range


# -------------------------------------------------------------- feed scanner

def make_feeds(tmp_path, feed_cfg, routes, calls=None):
    return feeds.FeedScanner({"extra_sources": {"feeds": feed_cfg}}, data_dir=str(tmp_path),
                             client=client_for(routes, calls))


def test_feed_scanner_enabled_only_and_remotive_cooldown(tmp_path):
    routes = {"remotive.com": (200, {"jobs": [{"title": "T", "url": "https://remotive.com/1", "company_name": "C"}]}, JSON)}
    calls = []
    scanner = make_feeds(tmp_path, {"remotive": {"enabled": True}, "remoteok": {"enabled": False}}, routes, calls)
    assert run(scanner.scan()).job_count == 1
    again = run(scanner.scan())
    assert again.job_count == 0 and "cooldown" in again.errors[0]
    assert len(calls) == 1 and "remoteok" not in calls[0]


def test_feed_scanner_rate_limit_and_unknown_feed(tmp_path):
    routes = {"jobicy.com": (429, "", JSON)}
    res = run(make_feeds(tmp_path, {"jobicy": {"enabled": True}, "madeup": {"enabled": True}}, routes).scan())
    assert any("rate-limited" in e for e in res.errors) and any("unsupported feed" in e for e in res.errors)


def test_feed_scanner_wrong_content_type_and_malformed_json(tmp_path):
    routes = {"jobicy.com": (200, "<html>captcha</html>", "text/html")}
    res = run(make_feeds(tmp_path, {"jobicy": {"enabled": True}}, routes).scan())
    assert res.job_count == 0 and "JSON" in res.errors[0]
    routes = {"remoteok.com": (200, "{broken", JSON)}
    res = run(make_feeds(tmp_path / "b", {"remoteok": {"enabled": True}}, routes).scan())
    assert "malformed" in res.errors[0]


# --------------------------------------------- pipeline integration (mocked)

def test_extra_sources_flow_through_filters_dedup_and_pipeline(tmp_path):
    """Scanner output -> original PipelineBridge: filtered, written, deduped on re-run."""
    routes = {"jobicy.com": (200, {"jobs": [
        {"jobTitle": "Python Developer", "url": "https://jobicy.com/jobs/1", "companyName": "A", "jobGeo": "Anywhere", "jobDescription": "d"},
        {"jobTitle": "Barista", "url": "https://jobicy.com/jobs/2", "companyName": "B", "jobGeo": "Anywhere"},
        {"jobTitle": "Python Developer", "url": "https://jobicy.com/jobs/3", "companyName": "C", "jobGeo": "USA Only"}]}, JSON)}
    config = {"title_filter": {"positive": ["python"], "negative": []},
              "location_filter": {"allow": ["remote", "anywhere"], "block": []},
              "extra_sources": {"feeds": {"jobicy": {"enabled": True}}}}
    result = run(feeds.FeedScanner(config, data_dir=str(tmp_path), client=client_for(routes)).scan())
    bridge = PipelineBridge(config, data_dir=str(tmp_path))
    summary = bridge.process([result])
    assert summary["new_added"] == 1                           # only the python + remote/anywhere job
    pipeline = (tmp_path / "pipeline.md").read_text(encoding="utf-8")
    assert "https://jobicy.com/jobs/1" in pipeline and "jobs/2" not in pipeline and "jobs/3" not in pipeline
    again = PipelineBridge(config, data_dir=str(tmp_path)).process([result])
    assert again["new_added"] == 0 and again["duplicates"] == 1


def test_run_scan_wires_extra_scanners_only_when_enabled(monkeypatch):
    import run_scan
    seen = []

    class Fake:
        def __init__(self, name): self.name = name
        def __call__(self, config):
            outer = self
            class S:
                async def scan(self_inner):
                    seen.append(outer.name)
                    return ScanResult(scanner_name=outer.name)
            return S()

    class FakeBridge:
        def __init__(self, config): pass
        def process(self, results, dry_run=False):
            return {"total_found": 0, "passed_filters": 0, "rejected_title": 0, "rejected_location": 0,
                    "duplicates": 0, "new_added": 0, "new_jobs": [], "errors": []}

    for cfg, expected in (({"extra_sources": {"enabled": False}}, []), ({"extra_sources": {"enabled": True}}, ["ats", "feeds"]), ({}, [])):
        seen.clear()
        monkeypatch.setattr(run_scan, "load_config", lambda cfg=cfg: cfg)
        monkeypatch.setattr(run_scan, "DirectAPIScanner", Fake("workday"))
        monkeypatch.setattr(run_scan, "JobSpyScanner", Fake("jobspy"))
        monkeypatch.setattr(run_scan, "AtsScanner", Fake("ats"))
        monkeypatch.setattr(run_scan, "FeedScanner", Fake("feeds"))
        monkeypatch.setattr(run_scan, "PipelineBridge", FakeBridge)
        asyncio.run(run_scan.run_scan(dry_run=True))
        assert [s for s in seen if s in ("ats", "feeds")] == expected


# ------------------------------------------------------- JobSpy upgrade (mocked)

BASE_CFG = {"jobspy_searches": {"terms": ["AI Engineer"], "locations": ["Germany"], "sites": ["linkedin"]}}


def test_jobspy_providers_off_by_default_and_validated():
    cfg = {**BASE_CFG, "jobspy_providers": {"glassdoor": {"enabled": False, "locations": ["Germany"]}}}
    assert len(JobSpyScanner(cfg).searches) == 1
    cfg["jobspy_providers"]["glassdoor"]["enabled"] = True
    searches = JobSpyScanner(cfg).searches
    assert len(searches) == 2 and searches[1]["sites"] == ["glassdoor"] and searches[1]["term"] == "AI Engineer"
    with pytest.raises(ValueError):
        JobSpyScanner({**BASE_CFG, "jobspy_providers": {"not_a_site": {"enabled": True}}})
    with pytest.raises(ValueError):
        JobSpyScanner({**BASE_CFG, "jobspy_providers": ["glassdoor"]})  # must be a mapping


def fake_jobspy(monkeypatch, frame):
    module = types.ModuleType("jobspy")
    module.scrape_jobs = lambda **kw: frame
    monkeypatch.setitem(sys.modules, "jobspy", module)


def test_jobspy_empty_frame_with_provider_errors_is_a_failure_not_success(monkeypatch):
    frame = pd.DataFrame()
    frame.attrs["errors"] = {"glassdoor": "response status code 403"}
    fake_jobspy(monkeypatch, frame)
    scanner = JobSpyScanner(BASE_CFG)
    with pytest.raises(ProviderFailure) as exc:
        scanner._run_search(scanner.searches[0])
    assert exc.value.http_status == 403
    res = run(_scan_without_sleep(scanner))
    assert res.job_count == 0 and res.errors and "403" in res.errors[0]


async def _scan_without_sleep(scanner):
    real = asyncio.sleep
    asyncio.sleep = lambda *_a, **_k: real(0)
    try:
        return await scanner.scan()
    finally:
        asyncio.sleep = real


def test_jobspy_rows_clean_nan_salary_and_remote_flag(monkeypatch):
    frame = pd.DataFrame([
        {"job_url": "https://example.com/1", "title": "AI Engineer", "company": float("nan"), "location": "Berlin, DE",
         "description": None, "date_posted": pd.NaT, "min_amount": 50000.0, "max_amount": 70000.0,
         "currency": "EUR", "interval": "yearly", "is_remote": True, "site": "linkedin"},
        {"job_url": float("nan"), "title": "dropped: nan url"},
        {"job_url": "javascript:alert(1)", "title": "dropped: not http"},
        {"job_url": "https://example.com/2", "title": "", "company": "x"},
    ])
    fake_jobspy(monkeypatch, frame)
    scanner = JobSpyScanner(BASE_CFG)
    jobs = scanner._run_search(scanner.searches[0])
    assert len(jobs) == 1
    j = jobs[0]
    assert j.company == "" and j.date_posted == "" and j.description == ""
    assert j.salary == "EUR 50000-70000 yearly" and j.location.startswith("Remote")
    assert j.source == "jobspy-linkedin"
    assert clean(float("nan")) == "" and clean("nan") == "" and clean(None) == "" and clean("ok") == "ok"
