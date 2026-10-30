"""Primary fixed-source Scrapling crawl engine; no arbitrary URL or code input."""
import json
import re
import time
from urllib.parse import urlsplit, urljoin
from .collection import Collection, text
from .authorized_boards import AccessBlocked, nodes, structured_salary
from .scrapling_transport import AGENT

SOURCES={
 'scrapling_jobicy':{'identifier':'remote','host':'jobicy.com','start':'https://jobicy.com/jobs',
    'detail':r'/jobs/[0-9]+-[a-zA-Z0-9_-]+','listing':r'/jobs(?:/page/[1-9][0-9]?)?',
    'publisher':'Jobicy','provider':'jobicy'},
 'scrapling_arbeitnow':{'identifier':'de','host':'www.arbeitnow.com','start':'https://www.arbeitnow.com',
    'detail':r'/jobs/companies/[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+-[0-9]+','listing':r'/',
    'publisher':'Arbeitnow','provider':'arbeitnow'},
}
MAX_DETAILS=3
MAX_PAGES=20
MAX_PENDING=200


def validate_source(kind,identifier):
    if kind not in SOURCES or identifier!=SOURCES[kind]['identifier']:
        raise ValueError('Use the fixed Scrapling source identifier from the source catalog')


def safe_url(kind,url,detail=False):
    from .validation import public_url
    public_url(url);p=urlsplit(url);cfg=SOURCES[kind]
    path=p.path or '/'
    if p.scheme!='https' or p.netloc!=cfg['host'] or p.fragment or '%' in p.path or '..' in p.path or len(url)>1000:
        raise ValueError('URL outside fixed Scrapling source scope')
    if not re.fullmatch(cfg['detail'] if detail else cfg['listing'],path):
        raise ValueError('Unsupported Scrapling detail/listing path')
    if p.query and (detail or not re.fullmatch(r'page=[1-9][0-9]{0,2}',p.query)):
        raise ValueError('Unsupported Scrapling query')
    return url


def selector(body):
    from scrapling import Selector
    if len(body)>5*1024*1024:raise ValueError('Source response exceeds byte limit')
    page=Selector(body.decode('utf-8-sig'),adaptive=False)
    visible=page.get_all_text(ignore_tags=('script','style')).lower()
    if any(s in visible for s in ('verify you are human','checking your browser','access denied','just a moment','captcha')):
        raise AccessBlocked('Scrapling source access challenge; no bypass or alternate route')
    return page


def listing(kind,body,url):
    page=selector(body);details=[];next_pages=[]
    for anchor in page.css('a[href]')[:5000]:
        target=urljoin(url,anchor.attrib.get('href',''))
        if 'next' in anchor.attrib.get('rel','').split() or anchor.get_all_text().strip().lower() in ('next','next page','weiter'):
            next_pages.append(safe_url(kind,target));continue
        try:details.append(safe_url(kind,target,True))
        except ValueError:pass
    for link in page.css('link[rel="next"]'):
        next_pages.append(safe_url(kind,urljoin(url,link.attrib.get('href',''))))
    details=list(dict.fromkeys(details));next_pages=list(dict.fromkeys(next_pages))
    if not details:raise ValueError('Scrapling layout changed or no recognized detail links; not claimed as successful empty coverage')
    if len(details)>MAX_PENDING or len(next_pages)>1:raise ValueError('Scrapling listing bound/ambiguous pagination')
    return details,next_pages[0] if next_pages else None


def postings(kind,body,url):
    cfg=SOURCES[kind];page=selector(body);rows=[]
    for script in page.css('script[type="application/ld+json"]::text').getall()[:100]:
        try:value=json.loads(script)
        except (ValueError,TypeError):continue
        for item in nodes(value):
            typ=item.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
            if not isinstance(typ,list) or 'JobPosting' not in typ:continue
            org=item.get('hiringOrganization') or {}
            if not isinstance(org,dict) or not isinstance(org.get('name'),str) or not isinstance(item.get('title'),str) or not isinstance(item.get('description'),str):
                raise ValueError('Incomplete publisher JobPosting; no guessed vacancy')
            locations=[];rawloc=item.get('jobLocation') or []
            for entry in rawloc if isinstance(rawloc,list) else [rawloc]:
                address=entry.get('address',{}) if isinstance(entry,dict) else {}
                if isinstance(address,str):locations.append(address)
                elif isinstance(address,dict):
                    parts=[]
                    for key in ('addressLocality','addressRegion','addressCountry'):
                        part=address.get(key,'')
                        if isinstance(part,dict):part=part.get('name','')
                        if isinstance(part,str) and part:parts.append(part)
                    if parts:locations.append(', '.join(parts))
            # Preserve declared applicant-country restrictions, even for remote.
            constraints=item.get('applicantLocationRequirements') or []
            for entry in constraints if isinstance(constraints,list) else [constraints]:
                if isinstance(entry,dict) and isinstance(entry.get('name'),str):locations.append(entry['name'])
            locations=list(dict.fromkeys(locations))
            remote=item.get('jobLocationType')=='TELECOMMUTE'
            location=('Remote · ' if remote and locations else 'Remote' if remote else '')+'; '.join(locations)
            employment=item.get('employmentType','')
            if isinstance(employment,list):employment=', '.join(x for x in employment if isinstance(x,str))
            identity=item.get('identifier') or {};external=identity.get('value','') if isinstance(identity,dict) else ''
            canonical=safe_url(kind,urljoin(url,item.get('url') or url),True)
            rows.append({'title':item['title'],'company':org['name'],'url':canonical,
                'description':text(item['description']),'location':location,
                'employment_type':employment if isinstance(employment,str) else '',
                'date_posted':item.get('datePosted','') if isinstance(item.get('datePosted',''),str) else '',
                'salary':structured_salary(item.get('baseSalary')),
                'external_job_id':str(external) if isinstance(external,(str,int)) else '',
                'attribution':cfg['publisher'],'source_notice':f"Source: {cfg['publisher']}. Preserve attribution and original listing backlink. Declared location restrictions apply; remote does not establish global eligibility."})
    if not rows:raise ValueError('No publisher JobPosting; detail layout needs review')
    if len(rows)>20:raise ValueError('Too many JobPosting records on one detail page')
    return rows


def collect(source,checkpoint=None,cancel_event=None,getter=None):
    from .scrapling_transport import get
    try:
        from protego import Protego
        from scrapling import Selector
    except ImportError:
        from .scrapling_transport import ScraplingRuntimeMissing
        raise ScraplingRuntimeMissing("Install requirements-scanners.lock") from None
    validate_source(source.kind,source.identifier)
    kind=source.kind;cfg=SOURCES[kind];state=checkpoint or {}
    if not isinstance(state,dict) or ('complete' in state and type(state['complete']) is not bool):raise ValueError('Invalid Scrapling checkpoint')
    if state.get('complete'):state={}
    page=state.get('page',cfg['start']);pending=state.get('pending',[]);visited=state.get('visited',[])
    next_page=state.get('next_page');index=state.get('index',1)
    safe_url(kind,page)
    if type(index) is not int or not 1<=index<=MAX_PAGES or not isinstance(pending,list) or len(pending)>MAX_PENDING or not isinstance(visited,list) or len(visited)>MAX_PAGES:
        raise ValueError('Invalid Scrapling checkpoint bounds')
    pending=[safe_url(kind,x,True) for x in pending]
    visited=[safe_url(kind,x) for x in visited]
    if next_page:safe_url(kind,next_page)
    requests=0;get=getter or get;last_request=None;delay=1.0
    def read(url,rules=None,is_robots=False):
        nonlocal requests,last_request
        if requests>=5:raise ValueError('Scrapling request budget exceeded')
        if cancel_event and cancel_event.is_set():raise InterruptedError('Collection cancelled')
        if rules and not rules.can_fetch(url,AGENT):raise AccessBlocked('Crawler rules disallow Scrapling source URL')
        if last_request is not None:time.sleep(max(0,delay-(time.monotonic()-last_request)))
        if cancel_event and cancel_event.is_set():raise InterruptedError('Collection cancelled')
        requests+=1;last_request=time.monotonic()
        body,typ=get(url,'text/plain' if is_robots else 'text/html',max_bytes=256*1024 if is_robots else 5*1024*1024,cancel_event=cancel_event)
        if is_robots and 'text/plain' not in typ:raise ValueError('Crawler rules unavailable; fail closed')
        if not is_robots and 'html' not in typ:raise ValueError('Scrapling expected public HTML')
        return body
    robot_body=read('https://'+cfg['host']+'/robots.txt',is_robots=True).decode('utf-8-sig')
    if not re.search(r'^User-agent\s*:',robot_body,re.I|re.M):raise ValueError('Unrecognized crawler rules; fail closed')
    robots=Protego.parse(robot_body)
    delay=max(1.0,float(robots.crawl_delay(AGENT) or 0))
    rate=robots.request_rate(AGENT)
    if rate:delay=max(delay,rate.seconds/rate.requests)
    if delay>10:raise AccessBlocked('Crawler delay needs a slower deployment-specific route')
    if not pending:
        if page in visited:raise ValueError('Repeated Scrapling listing page')
        pending,next_page=listing(kind,read(page,robots),page);visited=visited+[page]
    rows=[];leads=[]
    for target in pending[:MAX_DETAILS]:
        body=read(target,robots)
        rows.extend(postings(kind,body,target))
        from .source_discovery import discover
        from dataclasses import asdict
        leads.extend(asdict(lead) for lead in discover([{'url':target,'description':body.decode('utf-8-sig')}]))
    remaining=pending[MAX_DETAILS:]
    if next_page and next_page in visited:raise ValueError('Scrapling pagination cycle')
    if not remaining and next_page and index>=MAX_PAGES:raise ValueError('Scrapling page bound reached; review/reset checkpoint explicitly')
    complete=not remaining and not next_page
    state={'page':next_page if not remaining and next_page else page,
        'pending':remaining,'visited':visited,'index':index+1 if not remaining and next_page else index,
        'next_page':None if not remaining else next_page,'complete':complete}
    return Collection(rows,state,{'engine':'scrapling','engine_version':'0.5','transport':'scrapling_http',
        'requests':requests,'detail_pages':min(len(pending),MAX_DETAILS),'pending_details':len(remaining),
        'robots':'checked','coverage_complete':False,'listing_pass_complete':complete,
        'bounded_selection':True,'coverage_scope':'Configured HTML listing pages only; no whole-site completeness claim'},leads=leads)
