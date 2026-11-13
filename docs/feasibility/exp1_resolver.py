"""Experiment 1: does ats_scrapers.resolve.resolve_careers_url recognise realistic URLs?
Run: pip install ats-scrapers==0.3.0 beautifulsoup4 html2text ; python exp1_resolver.py
URLs are hand-written in the shapes these providers use; they are NOT real tenants."""
from ats_scrapers.resolve import resolve_careers_url
CASES = [  # (url, expect_recognised)
 ("https://boards.greenhouse.io/acme", True), ("https://boards.greenhouse.io/acme/jobs/4012345", True),
 ("https://job-boards.greenhouse.io/acme", True), ("https://job-boards.eu.greenhouse.io/acme", True),
 ("https://jobs.lever.co/acme", True), ("https://jobs.lever.co/acme/8f1c2a4e-1111-2222-3333-444455556666", True),
 ("https://jobs.ashbyhq.com/acme", True), ("https://jobs.ashbyhq.com/acme/0a1b2c3d", True),
 ("https://apply.workable.com/acme/", True), ("https://apply.workable.com/acme/j/ABC123DEF/", True),
 ("https://careers.smartrecruiters.com/Acme", True), ("https://jobs.smartrecruiters.com/Acme/743999-engineer", True),
 ("https://acme.recruitee.com/", True), ("https://acme.recruitee.com/o/data-engineer", True),
 ("https://acme.jobs.personio.de/", True), ("https://acme.jobs.personio.com/job/123456", True),
 ("https://acme.teamtailor.com/jobs", True), ("https://acme.teamtailor.com/jobs/123-engineer", True),
 ("https://acme.breezy.hr/", True), ("https://acme.bamboohr.com/careers", True), ("https://acme.bamboohr.com/careers/45", True),
 ("https://ats.rippling.com/acme/jobs", True),
 ("https://acme.wd5.myworkdayjobs.com/External", True), ("https://acme.wd3.myworkdayjobs.com/en-US/Careers/job/Berlin/Engineer_R123", True),
 # must NOT be recognised (boards, redirects, trackers, employer sites)
 ("https://www.indeed.com/viewjob?jk=abc123", False), ("https://de.indeed.com/rc/clk?jk=abc&fccid=123", False),
 ("https://www.linkedin.com/jobs/view/3912345678", False), ("https://lnkd.in/dAbCdEf", False),
 ("https://www.glassdoor.com/job-listing/engineer-acme-JV_IC1.htm", False), ("https://www.acme.com/careers", False),
 ("https://click.mailer.example.com/track?u=https%3A%2F%2Fboards.greenhouse.io%2Facme", False),
 ("https://acme.com/jobs?gh_jid=4012345", False),   # Greenhouse embedded on a custom domain: URL alone cannot tell
 ("not a url", False), ("", False),
]
ok = bad = 0
for url, expect in CASES:
    try:
        r = resolve_careers_url(url)
    except Exception as e:
        r = f"EXC {type(e).__name__}"
    got = bool(r) and not str(r).startswith("EXC")
    flag = "ok " if got == expect else "BAD"
    ok += got == expect; bad += got != expect
    print(f"{flag} expect={'hit ' if expect else 'none'} got={str(r)[:95]!s:95}  {url[:70]}")
print(f"\nmatched expectation: {ok}/{ok+bad}")
