"""Approved bounded public ATS sources, no dynamic code or arbitrary network URLs.

Public API availability is not a blanket permission. Review provider and employer
terms before approving a source. Scans are manual and bounded by the adapter policy. Feed entries require review.
"""
from __future__ import annotations
from dataclasses import dataclass
from html.parser import HTMLParser
import json
import re
import ssl
import urllib.request
import urllib.error
from filelock import FileLock, Timeout
from .store import dump, now
from .pagination import state as pagination_state
from hashlib import sha256

POLICIES = {
 "greenhouse": {"cooldown": 60, "requests": 1, "docs": "https://developers.greenhouse.io/job-board.html", "notice": "Public employer board; review employer and API terms."},
 "lever": {"cooldown": 60, "requests": 1, "docs": "https://github.com/lever/postings-api", "notice": "Public employer board; review employer and API terms."},
 "ashby": {"cooldown": 600, "requests": 1, "docs": "https://developers.ashbyhq.com/docs/public-job-posting-api", "notice": "Only listed jobs; 10-minute local cooldown, not a published provider quota."},
 "smartrecruiters": {"cooldown": 600, "requests": 11, "docs": "https://developers.smartrecruiters.com/docs/endpoints", "notice": "Public unauthenticated records only. At most 10 details per scan; resumes committed list checkpoints. Listing snapshots can change; no completeness claim. At most 11 requests, spaced 0.6 seconds."},
 "remotive": {"cooldown": 21600, "requests": 1, "docs": "https://github.com/remotive-com/remote-jobs-api", "notice": "Remotive attribution and original backlink required. API jobs are delayed 24 hours. At most 4 requests/day; do not republish to third-party job sites."},
 "feed": {"cooldown": 3600, "requests": 1, "docs": "", "notice": "Approve only a public HTTPS RSS/Atom feed whose terms permit this use. Use official platform adapters for social sources. Complete source-backed vacancies may be auto-added; ambiguous entries remain for review. One-hour local cooldown."},
}

POLICIES['structured_html'] = {'cooldown':3600,'requests':5,'docs':'https://schema.org/JobPosting','notice':'Opt-in reviewed generic Scrapling JSON-LD recipe. Explicit source approval, robots, same-origin bounds; at most five reads. No universal extraction.'}

POLICIES['workday'] = {'cooldown': 600, 'requests': 105, 'docs': 'https://github.com/shd2w/Jobs_hunter/blob/main/scanners/workday.py', 'notice': 'Explicitly approved public Workday tenant/board. Reuses bounded direct scanner (at most five listing pages plus details). No authentication or fallback.'}

POLICIES.update({
 'jobicy': {'cooldown':3600,'requests':1,'docs':'https://jobicy.com/jobs-rss-feed','notice':'Public free API only; never attaches a paid key. Jobicy credit/backlink retained. Seven-day feed delayed three hours. Cursor expires after 24 hours; expired incomplete passes need a checkpoint reset (automatic mode restarts a due pass without clearing gates).'},
 'arbeitnow': {'cooldown':3600,'requests':1,'docs':'https://www.arbeitnow.com/blog/job-board-api','notice':'Public DE/UK API; identifier de or uk. One page per manual scan. One-hour conservative local cooldown, not a published provider quota. Credit/backlink retained.'},
 'hn': {'cooldown':600,'requests':11,'docs':'https://github.com/HackerNews/API','notice':'Supply a Who is hiring story ID. At most 10 top-level comments per scan, no profiles or replies. Complete source-backed vacancies may be auto-added and evaluated, never human-verified; ambiguous comments remain for review. Ten-minute local cooldown; not a provider quota.'},
 'usajobs': {'cooldown':600,'requests':1,'docs':'https://developer.usajobs.gov/Guides/Authentication','notice':'Optional API key required: USAJOBS_API_KEY and USAJOBS_USER_AGENT in environment only. Identifier is a keyword query. One page (50 results) per scan. Public announcement does not establish citizenship or eligibility. Ten-minute local cooldown.'},
})
from .expanded_sources import JOBSPY, PUBLIC as EXPANDED_PUBLIC
from scanners.jobspy_registry import SCOPES
from .scrapling_engine import SOURCES as SCRAPLING_SOURCES
SCRAPLING_KINDS=tuple(SCRAPLING_SOURCES)
for _site in JOBSPY:
    POLICIES[_site] = {'cooldown': 86400 if _site == 'jobspy_google' else 300, 'requests': 1, 'docs': 'https://github.com/speedyapply/JobSpy',
        'notice': 'Original configured JobSpy searches, one provider/query/page per scan (five-minute local cooldown; Google daily while unavailable upstream); rotates through all configured regions and English/German terms. Description requests are additional. No proxy or challenge bypass. Google Jobs is currently unavailable upstream; failures are reported, not zero-result success. Install requirements-scanners.txt.'}
for _site, _scope in SCOPES.items():
    POLICIES['jobspy_' + _site]['notice'] += ' Provider scope: ' + _scope + '.'
for _kind, _docs in [('remoteok', 'https://remoteok.com/api'), ('weworkremotely', 'https://weworkremotely.com/remote-job-rss-feed')]:
    POLICIES[_kind] = {'cooldown': 3600, 'requests': 1, 'docs': _docs,
        'notice': 'Public feed; retain publisher attribution and original listing backlink. One-hour conservative local cooldown. Current feed only, no whole-site completeness claim.'}
for _kind,_cfg in SCRAPLING_SOURCES.items():
    POLICIES[_kind]={'cooldown':3600,'requests':5,'docs':'https://github.com/D4Vinci/Scrapling',
        'engine':'scrapling','provider':_cfg['provider'],
        'notice':'Primary Scrapling HTTP+Selector engine. Fixed public HTML source, robots checked, one listing and at most three structured detail pages per scan plus robots; pending details resume. Public DNS pinned, verified TLS, no redirects/proxies/stealth/browser/credentials. One-hour cooldown shared with native publisher adapters. Retain publisher attribution/backlink. No whole-site or worldwide eligibility claim. Install requirements-scanners.lock.'}
PAGED = {'wuzzuf','naukrigulf','smartrecruiters','jobicy','arbeitnow','hn','usajobs'}

for _kind, _docs in [('wuzzuf','https://wuzzuf.net/policies'),('naukrigulf','https://www.naukrigulf.com/terms-and-conditions')]:
    POLICIES[_kind] = {'cooldown':3600,'requests':6,'docs':_docs,'notice':'Explicit provider authorization required, plus local approval. Publisher structured-data HTML collector; optional explicit browser transport. See current live-access results; layouts can change. One public listing and at most four details, plus optional robots.txt in check mode; committed continuation only. Publisher JobPosting JSON-LD required. Robots check skipped for these two user-authorized boards by default; JOBHUNTER_AUTHORIZED_BOARD_ROBOTS=check restores it. Stop on redirects, login/challenges, 403/429 or changed formats. No whole-site completeness claim. One-hour provider-wide local cooldown.'}


from .platform_posts import KINDS as POST_PLATFORMS, DOCS as POST_DOCS
for _kind in POST_PLATFORMS:
    POLICIES[_kind]={'cooldown':3600,'requests':1,'docs':POST_DOCS[_kind],
        'notice':'Explicit authorized official API access and source identifier required; one page of at most 50 posts per manual scan. Clear complete vacancies may be auto-added and lexically evaluated, never human-verified. Ambiguous posts stay in review. One-hour provider-wide local cooldown. Setup and any API costs require separate local consent; not currently live verified.'}


def catalog():
    from .authorized_boards import robots_mode
    from .board_browser import transport_mode
    from .scrapling_parser import parser_mode
    mode=robots_mode(); transport=transport_mode(); parser=parser_mode()
    from .platform_posts import setup
    return [{"kind": k, **v, **(setup(k) if k in POST_PLATFORMS else {}), **({'robots_mode':mode,'transport':transport,'parser':parser,'request_unit':'top-level navigations; browser assets make additional requests' if transport=='browser' else 'HTTP requests','requests':5 if mode=='skip' else 6} if k in ('wuzzuf','naukrigulf') else {})} for k, v in POLICIES.items()]


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.ignored = max(0, self.ignored - 1)
    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def plain(value):
    parser = Text()
    parser.feed(value or '')
    return ' '.join(parser.parts)


@dataclass(frozen=True)
class Source:
    kind: str
    identifier: str

    def __post_init__(self):
        if self.kind not in POLICIES:
            raise ValueError('Unsupported source kind')
        if self.kind == 'workday':
            if not re.fullmatch(r'[a-z0-9-]+__wd[0-9]+__[A-Za-z0-9_-]{1,80}', self.identifier):
                raise ValueError('Workday requires observed tenant__wdN__board identity')
        if self.kind in POST_PLATFORMS:
            from .platform_posts import validate_identifier
            validate_identifier(self.kind,self.identifier)
        elif self.kind in ('wuzzuf','naukrigulf'):
            from .authorized_boards import safe_url
            safe_url(self.kind,self.identifier)
        elif self.kind in ('feed','structured_html'):
            from .network import feed_url
            feed_url(self.identifier)
        elif self.kind == 'usajobs':
            if not isinstance(self.identifier,str) or not 1 <= len(self.identifier) <= 100 or any(ord(c)<32 for c in self.identifier): raise ValueError('Supply a keyword query of 1–100 characters')
        elif not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', self.identifier):
            raise ValueError('Use a simple public board identifier')
        if self.kind in SCRAPLING_KINDS:
            from .scrapling_engine import validate_source
            validate_source(self.kind,self.identifier)
        if self.kind in JOBSPY and self.identifier != 'configured': raise ValueError('JobSpy uses configured registry only')
        if self.kind in EXPANDED_PUBLIC and self.identifier != 'remote': raise ValueError('Use remote for this public feed')
        if self.kind == 'remotive' and self.identifier != 'remote':
            raise ValueError('Remotive uses the single identifier remote to enforce its global cooldown')

        if self.kind == 'arbeitnow' and self.identifier not in ('de','uk'): raise ValueError('Arbeitnow identifier must be de or uk')
        if self.kind == 'jobicy' and self.identifier != 'remote': raise ValueError('Jobicy identifier must be remote')
        if self.kind == 'hn' and not re.fullmatch(r'[1-9][0-9]{0,14}',self.identifier): raise ValueError('Supply a positive HN thread ID')

    @property
    def id(self):
        return f'{self.kind}:' + (sha256(self.identifier.encode()).hexdigest()[:32] if self.kind in ('feed','structured_html','usajobs','wuzzuf','naukrigulf') else self.identifier)

    @property
    def url(self):
        if self.kind in SCRAPLING_KINDS:return SCRAPLING_SOURCES[self.kind]['start']
        if self.kind == 'workday':
            tenant, node, board = self.identifier.split('__')
            return f'https://{tenant}.{node}.myworkdayjobs.com/{board}'
        if self.kind == 'greenhouse':
            return f'https://boards-api.greenhouse.io/v1/boards/{self.identifier}/jobs?content=true'
        if self.kind == 'lever':
            return f'https://api.lever.co/v0/postings/{self.identifier}?mode=json'
        if self.kind == 'ashby':
            return f'https://api.ashbyhq.com/posting-api/job-board/{self.identifier}?includeCompensation=true'
        if self.kind == 'smartrecruiters':
            return f'https://api.smartrecruiters.com/v1/companies/{self.identifier}/postings?limit=100&offset=0'
        if self.kind == 'remotive':
            return 'https://remotive.com/api/remote-jobs'
        if self.kind == 'jobicy': return 'https://jobicy.com/api/jobs?count=100'
        if self.kind == 'arbeitnow': return ('https://www.arbeitnow.co.uk' if self.identifier=='uk' else 'https://www.arbeitnow.com')+'/api/job-board-api?page=1'
        if self.kind == 'hn': return 'https://hacker-news.firebaseio.com/v0/item/'+self.identifier+'.json'
        if self.kind == 'usajobs':
            from urllib.parse import urlencode
            return 'https://data.usajobs.gov/api/Search?'+urlencode({'Keyword':self.identifier,'Page':1,'ResultsPerPage':50,'WhoMayApply':'public'})
        return self.identifier


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Source redirects are disabled; review registry configuration')


def fetch(source: Source, cancel_event=None, checkpoint=None):
    if source.kind == 'structured_html':
        from .structured_source import collect
        return collect(source,checkpoint,cancel_event)
    if source.kind == 'workday':
        from .workday_source import collect
        return collect(source, checkpoint, cancel_event)
    if source.kind in SCRAPLING_KINDS:
        from .scrapling_engine import collect
        return collect(source,checkpoint,cancel_event)
    if source.kind in JOBSPY + EXPANDED_PUBLIC + SCRAPLING_KINDS:
        from .expanded_sources import collect
        return collect(source, checkpoint, cancel_event)
    if source.kind in POST_PLATFORMS:
        from .platform_posts import collect
        return collect(source, checkpoint, cancel_event)
    if source.kind in ('wuzzuf','naukrigulf'):
        from .authorized_boards import collect
        from .board_browser import transport_mode, BrowserHTML
        if transport_mode() == 'browser':
            with BrowserHTML(source.kind, cancel_event) as browser:
                result = collect(source, checkpoint, cancel_event, getter=browser.get)
                result.metrics.update(browser.metrics())
            return result
        return collect(source,checkpoint,cancel_event)
    if source.kind in PAGED:
        from .collection import collect
        return collect(source, checkpoint, cancel_event)
    from .network import get
    accept = 'application/rss+xml, application/atom+xml, application/xml, text/xml' if source.kind == 'feed' else 'application/json'
    # Large employer boards legitimately exceed 5 MiB. Keep a finite bound,
    # scoped to these three static ATS adapters (not arbitrary feeds/URLs).
    content, content_type = get(source.url, accept, max_bytes=32 * 1024 * 1024) if source.kind in ('greenhouse', 'lever', 'ashby') else get(source.url, accept)
    if source.kind == 'feed':
        if 'xml' not in content_type:
            raise ValueError('Feed source did not return XML')
        return content
    if 'json' not in content_type:
        raise ValueError('Source did not return JSON')
    data = json.loads(content)
    if source.kind == 'remotive':
        # This endpoint supplies a bounded snapshot, not a resumable cursor.
        normalize(source, data)  # Validate before emitting a completed receipt.
        from .collection import Collection
        from .pagination import state as pagination
        return Collection(data, {'complete': True}, {'requests': 1,
            'pagination': pagination(response_mode='snapshot', pages_retrieved=1,
                                    evidence='validated Remotive current API response; not all vacancies')})
    return data


def normalize(source: Source, data):
    if source.kind in ('structured_html','workday','wuzzuf','naukrigulf') + JOBSPY + EXPANDED_PUBLIC + SCRAPLING_KINDS:
        if not isinstance(data,list) or len(data)>10000: raise ValueError('Invalid normalized board rows')
        return data
    if source.kind in ('jobicy','arbeitnow','usajobs'):
        from .source_rows import normalize_new
        return normalize_new(source,data)
    entries = (data.get('content') if source.kind == 'smartrecruiters' else data.get('jobs')) if source.kind in ('greenhouse','ashby','remotive','smartrecruiters') and isinstance(data, dict) else data
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError('Invalid ATS payload')
    rows = []
    for item in entries:
        if not isinstance(item, dict):
            rows.append(item)  # Common intake reports malformed individual records.
            continue
        try:
            if source.kind == 'greenhouse':
                location = item.get('location') or {}
                rows.append({'title': item.get('title'), 'url': item.get('absolute_url'),
                             'company': source.identifier, 'location': location.get('name', '') if isinstance(location, dict) else '',
                             'description': plain(item.get('content', '')), 'external_job_id': str(item.get('id', ''))})
            elif source.kind == 'ashby':
                if item.get('isListed') is not True:
                    continue  # Never promote direct-link-only/unlisted roles.
                rows.append({'title': item.get('title'), 'url': item.get('jobUrl'), 'company': source.identifier,
                             'location': item.get('location', ''), 'description': item.get('descriptionPlain') or plain(item.get('descriptionHtml', '')),
                             'date_posted': item.get('publishedAt', ''), 'employment_type': item.get('employmentType', ''),
                             'salary': (item.get('compensation') or {}).get('scrapeableCompensationSalarySummary') or (item.get('compensation') or {}).get('compensationTierSummary', '')})
            elif source.kind == 'remotive':
                rows.append({'title': item.get('title'), 'url': item.get('url'), 'company': item.get('company_name'),
                             'location': item.get('candidate_required_location', ''), 'description': plain(item.get('description', '')),
                             'salary': item.get('salary', ''), 'date_posted': item.get('publication_date', ''),
                             'employment_type': item.get('job_type', ''), 'external_job_id': str(item.get('id', '')),
                             'attribution': 'Remotive', 'source_notice': POLICIES['remotive']['notice']})
            elif source.kind == 'smartrecruiters':
                if item.get('active') is False: continue
                location = item.get('location') or {}
                company = item.get('company') or {}
                sections = (item.get('jobAd') or {}).get('sections') or {}
                description = '\n'.join(plain(x.get('text', '')) for x in sections.values() if isinstance(x, dict)) if isinstance(sections, dict) else ''
                rows.append({'title': item.get('name'), 'url': item.get('applyUrl'),
                             'company': company.get('name', source.identifier) if isinstance(company, dict) else source.identifier,
                             'location': ', '.join(str(location.get(x, '')) for x in ('city','region','country') if location.get(x)) if isinstance(location, dict) else '',
                             'description': description, 'employment_type': (item.get('typeOfEmployment') or {}).get('label', ''), 'date_posted': item.get('releasedDate', ''), 'external_job_id': str(item.get('id', ''))})
            else:
                category = item.get('categories') or {}
                lists = item.get('lists') or []
                description = item.get('descriptionPlain') or plain(item.get('description', ''))
                for section in lists:
                    if isinstance(section, dict):
                        description += '\n' + plain(section.get('content', ''))
                rows.append({'title': item.get('text'), 'url': item.get('hostedUrl'),
                             'company': source.identifier, 'location': category.get('location', '') if isinstance(category, dict) else '',
                             'description': description, 'employment_type': category.get('commitment', '') if isinstance(category, dict) else '',
                             'salary': item.get('salaryDescription', ''), 'external_job_id': str(item.get('id', ''))})
        except (TypeError, ValueError, AttributeError):
            # Preserve the row position, never persist the malformed raw payload.
            rows.append({})

    return rows


def register(store, kind, identifier, approved=False):
    source = Source(kind, identifier)
    with store.connect() as db:
        db.execute('INSERT INTO sources(id,kind,identifier,approved) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET approved=excluded.approved',
                   (source.id, kind, identifier, int(approved)))
        store.audit(db, 'source_approval_changed', {'source': source.id, 'approved': approved})
    return source.id


def scan(store, source_id, transport=fetch, cancel_event=None, profile_id='default', mirror_legacy=True, request=None):
    if request is not None:
        from .discovery_state import ensure
        ensure(store)
    lock = FileLock(str(store.path) + '.scan.lock', timeout=0)
    try:
        with lock:
            return _scan_locked(store, source_id, transport, cancel_event, profile_id, mirror_legacy, request)
    except Timeout as exc:
        raise ValueError('Another source scan is active; wait for completion') from exc


def _scan_locked(store, source_id, transport, cancel_event=None, profile_id='default', mirror_legacy=True, request=None):
    from datetime import datetime, timezone
    import time
    started = time.monotonic()
    with store.connect() as db:
        row = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if not row or not row['approved']:
            raise ValueError('Source must be explicitly approved after reviewing access terms')
        if row['kind'] in POST_PLATFORMS and transport is fetch:
            from .platform_posts import setup, SetupRequired
            missing=setup(row['kind'])['missing_configuration']
            if missing:raise SetupRequired('Configure authorized post access locally: '+', '.join(missing))
        from .source_health import provider_family, provider_kinds
        family=provider_family(row['kind']);family_kinds=provider_kinds(row['kind'])
        gate = db.execute('SELECT not_before FROM provider_gates WHERE kind=?',(family,)).fetchone()
        if gate and datetime.fromisoformat(gate[0]) > datetime.now(timezone.utc): raise ValueError('Provider Retry-After gate is active; reapproval does not bypass it')
        cooldown = POLICIES[row['kind']]['cooldown']
        if row['last_run'] and (datetime.now(timezone.utc) - datetime.fromisoformat(row['last_run'])).total_seconds() < cooldown:
            raise ValueError(f'Per-source cooldown: wait at least {cooldown} seconds between scans')
        if row['kind'] in ('structured_html','jobicy','arbeitnow','hn','usajobs','wuzzuf','naukrigulf')+POST_PLATFORMS+SCRAPLING_KINDS:
            latest = db.execute('SELECT MAX(last_run) FROM sources WHERE kind IN ('+','.join('?' for _ in family_kinds)+')',family_kinds).fetchone()[0]
            if latest and (datetime.now(timezone.utc)-datetime.fromisoformat(latest)).total_seconds()<cooldown: raise ValueError('Provider-wide local cooldown is active')
        run_id = db.execute('INSERT INTO runs(source,started_at,status) VALUES(?,?,?)', (source_id, now(), 'running')).lastrowid
        db.execute('UPDATE sources SET last_run=? WHERE id=?', (now(), source_id))
        if row['kind'] in ('wuzzuf','naukrigulf'):
            from .authorized_boards import robots_mode
            from .board_browser import transport_mode
            store.audit(db,'authorized_board_robots_mode',{'source':source_id,'robots_mode':robots_mode(),'transport':transport_mode(),'approval_required':True})
    failure_stage = 'configuration'
    try:
        source = Source(row['kind'], row['identifier'])
        if request is not None:
            from .search_strategy import QuerySpec
            if not isinstance(request, QuerySpec) or source.kind != 'jobspy_' + request.provider or request.profile_id != profile_id:
                raise ValueError('Runtime query must match source and profile')
        with store.connect() as db:
            checkpoint = db.execute('SELECT data FROM search_progress WHERE signature=?', (request.signature,)).fetchone() if request else db.execute('SELECT data FROM source_checkpoints WHERE source_id=?',(source_id,)).fetchone()
        state = json.loads(checkpoint[0]) if checkpoint else {}
        failure_stage = 'retrieval'
        if request:
            from .expanded_sources import collect
            payload = collect(source, state, cancel_event, request=request) if transport is fetch else transport(source)
        else:
            payload = transport(source, cancel_event=cancel_event, checkpoint=state) if transport is fetch else transport(source)
        from .collection import Collection
        collected = payload if isinstance(payload, Collection) else None
        if collected: payload = collected.payload
        if cancel_event and cancel_event.is_set():
            with store.connect() as db:
                db.execute('UPDATE runs SET finished_at=?,status=?,metrics=? WHERE id=?', (now(), 'cancelled', dump({'pagination':pagination_state(cancelled=True)}), run_id))
                db.execute('UPDATE sources SET health=? WHERE id=?', ('cancelled', source_id))
            return {'cancelled': True, 'inserted': 0,'status':'cancelled','pagination':pagination_state(cancelled=True)}
        from .source_discovery import discover
        from dataclasses import asdict
        failure_stage = 'normalization'
        observed = normalize(source, payload) if source.kind != 'feed' and not (collected and collected.posts) else []
        raw_evidence=[]
        if source.kind in ('jobicy','arbeitnow') and isinstance(payload,dict):
            for item in payload.get('jobs' if source.kind=='jobicy' else 'data',[])[:1000]:
                if isinstance(item,dict): raw_evidence.append({'url':item.get('url',''),'description':item.get('jobDescription' if source.kind=='jobicy' else 'description','')})
        leads = (collected.leads if collected else []) + [asdict(lead) for lead in discover(observed+raw_evidence)]
        failure_stage = 'intake'
        if source.kind == 'feed':
            from .feeds import ingest
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                result = ingest(store, payload, rights_attested=True, source_label=source_id, base_url=source.identifier,_db=db,auto_add=True,profile_id=profile_id)
                result.pop('items', None)
                from .pagination import state as pagination
                result['pagination'] = pagination(response_mode='snapshot', evidence='current feed response only')
                result['duration_seconds']=round(time.monotonic()-started,3)
                result['new_unique_jobs']=result.get('auto_added',0)
                result['existing_job_observations']=result.get('linked_existing',0)
                state = 'partial' if result['invalid'] or result.get('feed_truncated') or result.get('feed_errors') else 'success'
                from .source_outcomes import outcome
                result['outcome'] = outcome(result)
                db.execute('UPDATE runs SET finished_at=?,status=?,metrics=? WHERE id=?', (now(), state, dump(result), run_id))
                db.execute('UPDATE sources SET health=?,last_error=NULL WHERE id=?', (state, source_id))
        else:
            # Job writes and their completion record must commit together.
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if collected and collected.posts:
                    from .posts import process
                    result = process(store,payload,rights_attested=True,_db=db,_hiring_context=source.kind=='hn',profile_id=profile_id) if payload else {'received':0,'staged':0,'duplicates':0,'invalid':0,'skipped':0}
                    result.pop('items',None)
                else:
                    result = store.ingest(normalize(source, payload), source=source_id, _db=db)
                if collected:
                    result.update(collected.metrics)
                    if request:
                        db.execute('INSERT INTO search_progress VALUES(?,?,?) ON CONFLICT(signature) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(request.signature,dump(collected.checkpoint),now()))
                    else:
                        db.execute('INSERT INTO source_checkpoints VALUES(?,?,?) ON CONFLICT(source_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(source_id,dump(collected.checkpoint),now()))
                from .pagination import receipt
                result['pagination'] = receipt(source,collected)
                if result.get('invalid') or result.get('provider_errors') or result.get('detail_errors'):
                    result['pagination'].update(partial=True)
                    result['pagination']['message'] = 'Scan partially completed due to source errors or invalid records. ' + result['pagination']['message']
                result['discovery_leads'] = leads
                result['duration_seconds'] = round(time.monotonic()-started,3)
                result['new_unique_jobs'] = result.get('inserted',0)
                result['existing_job_observations'] = result.get('updated',0)
                result['eligibility_relevance'] = 'Deterministic profile matching only; not human verification or legal eligibility' if result.get('auto_added') else 'not evaluated by discovery'
                result['valid_records'] = result.get('received',0)-result['invalid']
                if result.get('received'):
                    result['invalid_rate'] = round(result['invalid']/result['received'],4)
                    result['existing_observation_rate'] = round(result.get('updated',result.get('duplicates',0))/result['received'],4)
                result['freshness_notice']='Observed snapshot; never infer closure from absence.'
                if source.kind == 'smartrecruiters':
                    result['bounded_selection'] = collected.metrics['bounded_selection'] if collected else True
                    result['total_reported'] = payload.get('totalFound')
                    result['notice'] = 'At most 10 details per scan; default collector resumes only committed checkpoints. Injected transport coverage is unverified.'
                state = 'partial' if result['pagination']['partial'] or result.get('bounded_selection') else 'success'
                from .source_outcomes import outcome
                result['outcome'] = outcome(result)
                db.execute('UPDATE runs SET finished_at=?,status=?,metrics=? WHERE id=?', (now(), state, dump(result), run_id))
                db.execute('UPDATE sources SET health=?,last_error=NULL WHERE id=?', (state, source_id))

        result['status'] = state
        if mirror_legacy and source.kind in JOBSPY + EXPANDED_PUBLIC + SCRAPLING_KINDS:
            try:
                from scanners.compat import mirror_to_pipeline
                result['legacy_pipeline'] = mirror_to_pipeline(store.path.parent, normalize(source, payload))
            except Exception as mirror_error:
                # SQLite is committed; never pretend rollback. A later sighting
                # safely retries the idempotent Markdown/cache mirror.
                result['legacy_mirror_error'] = type(mirror_error).__name__
                with store.connect() as db:
                    store.audit(db, 'legacy_mirror_failed', {'source': source_id, 'error_type': type(mirror_error).__name__})
        return result
    except Exception as exc:
        # Do not persist provider bodies, headers, secrets or candidate input.
        if isinstance(exc,InterruptedError) or (cancel_event and cancel_event.is_set()):
            with store.connect() as db:
                db.execute('UPDATE runs SET finished_at=?,status=?,metrics=? WHERE id=?',(now(),'cancelled',dump({'pagination':pagination_state(cancelled=True)}),run_id))
                db.execute('UPDATE sources SET health=? WHERE id=?',('cancelled',source_id))
            return {'cancelled':True,'inserted':0,'status':'cancelled','pagination':pagination_state(cancelled=True)}
        rate_limited = isinstance(exc, urllib.error.HTTPError) and exc.code == 429
        from .authorized_boards import AccessBlocked
        access_blocked = row['kind'] in ('structured_html','wuzzuf','naukrigulf')+POST_PLATFORMS+SCRAPLING_KINDS and (isinstance(exc,AccessBlocked) or (isinstance(exc,urllib.error.HTTPError) and exc.code in (401,403)))
        message = ('Provider quota exhausted; all registered sources of this adapter kind are paused. Review provider retry policy before re-approving.' if rate_limited else 'Source access blocked; this provider is unapproved. Review permission and access rules; no bypass or automatic retry.' if access_blocked else type(exc).__name__ + ': source scan failed; check access, quota or payload')
        from .board_browser import BrowserError
        from .platform_posts import SetupRequired
        from .scrapling_transport import ScraplingRuntimeMissing
        failure = {'error': message}
        if row['kind'] in JOBSPY and isinstance(exc, RuntimeError):
            message = 'JobSpy provider failed; no successful empty scan. Google Jobs is unavailable upstream.' if row['kind']=='jobspy_google' else 'JobSpy provider rejected or failed the request; inspect local scanner log. No proxy, login or challenge bypass.'
            failure = {'error': message, 'failure_code': 'jobspy_provider_failure'}
            if getattr(exc, 'http_status', None): failure['http_status'] = exc.http_status
        if row['kind'] in JOBSPY and isinstance(exc, ImportError):
            message = 'Original JobSpy runtime missing. Install requirements-scanners.lock and restart; no sources or data were removed.'
            failure = {'error': message, 'failure_code': 'scanner_runtime_missing'}
        if isinstance(exc,ScraplingRuntimeMissing):
            message='Primary Scrapling runtime missing; install requirements-scanners.lock and restart. No fallback attempted.'
            failure={'error':message,'failure_code':'scrapling_runtime_missing','engine':'scrapling'}
        if isinstance(exc, SetupRequired):
            message = str(exc)
            failure = {'error':message,'failure_code':'platform_setup_required'}
        elif isinstance(exc, BrowserError):
            message = 'Browser access: ' + str(exc)
            failure = {'error': message, 'failure_code': exc.code, 'transport': 'browser'}
        elif isinstance(exc, urllib.error.HTTPError):
            failure['http_status'] = exc.code
        elif isinstance(exc, TimeoutError):
            message = ('Direct HTTP timed out. Optional explicit browser transport may be used after local setup; no automatic retry or fallback.' if row['kind'] in ('wuzzuf','naukrigulf') else 'Source HTTP timed out; review official access/configuration. No automatic retry or alternate transport.')
            failure['error'] = message
            failure['failure_code'] = 'http_timeout'
        validation_hints = {
            'Expected JSON': 'Expected a JSON response, but the source returned a different content type. No usable response was imported.',
            'Invalid Arbeitnow payload': 'Arbeitnow response did not contain the expected bounded jobs data list. No successful empty scan was recorded.',
        }
        if type(exc) is ValueError and str(exc) in validation_hints:
            failure['validation_hint'] = validation_hints[str(exc)]
        from .pagination import state as pagination
        failure['pagination'] = pagination(failed=True)
        failure.update(error_type=type(exc).__name__, failure_stage=failure_stage)
        failure.setdefault('failure_code', 'http_error' if isinstance(exc, urllib.error.HTTPError) else 'response_validation' if isinstance(exc, (ValueError, TypeError, KeyError)) else 'source_failure')
        with store.connect() as db:
            if row['kind'] in JOBSPY and isinstance(exc, RuntimeError):
                from .source_health import retry_gate
                from .provider_recovery import policy
                consecutive = 1
                for previous in db.execute('SELECT status FROM runs WHERE source=? AND id<? ORDER BY id DESC', (source_id, run_id)):
                    if previous['status'] != 'failed': break
                    consecutive += 1
                recovery = policy(row['kind'], getattr(exc, 'http_status', None), consecutive)
                failure.update(recovery, consecutive_failures=consecutive)
                message = recovery['error']
                retry_gate(db, row['kind'], getattr(exc, 'retry_after', '') or '', max(cooldown, recovery['retry_delay_seconds']))
            if access_blocked:
                db.execute('UPDATE sources SET approved=0,health=?,last_error=? WHERE kind=?',('access_blocked',message,row['kind']))
                store.audit(db,'provider_access_pause',{'kind':row['kind']})
            if rate_limited:
                # Do not let another board configuration become a quota workaround.
                db.execute('UPDATE sources SET approved=0,health=?,last_error=? WHERE kind IN ('+','.join('?' for _ in family_kinds)+')', ('rate_limited',message,*family_kinds))
                from .source_health import retry_gate
                retry_gate(db,family,exc.headers.get('Retry-After','') if exc.headers else '',cooldown)
                store.audit(db, 'provider_quota_pause', {'kind': row['kind']})
            db.execute('UPDATE runs SET finished_at=?,status=?,metrics=? WHERE id=?', (now(), 'failed', dump(failure), run_id))
            db.execute('UPDATE sources SET health=?,last_error=?,approved=CASE WHEN ? THEN 0 ELSE approved END WHERE id=?', ('rate_limited' if rate_limited else 'access_blocked' if access_blocked else 'failed', message, int(rate_limited or access_blocked), source_id))
        raise ValueError(message) from exc
