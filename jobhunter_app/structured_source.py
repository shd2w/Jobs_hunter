"""Opt-in reviewed generic JSON-LD method. Existing fixed collectors unchanged."""
import json,re
from urllib.parse import urlsplit,urljoin
from .collection import Collection,text
from .authorized_boards import nodes,structured_salary,AccessBlocked
from .scrapling_engine import selector
from .scrapling_transport import AGENT
from .network import feed_url


def collect(source,checkpoint=None,cancel_event=None,getter=None):
    from .scrapling_transport import get
    from protego import Protego
    get=getter or get;start=source.identifier;p=urlsplit(start)
    state=checkpoint or {}
    if state.get('complete'): state={}
    requests=0
    def safe(url):
        feed_url(url);q=urlsplit(url)
        if q.netloc!=p.netloc or q.fragment or (q.query and not re.fullmatch(r'page=[1-9][0-9]{0,2}',q.query)):
            raise ValueError('Structured recipe stays on observed origin; canonical page query only')
        return url
    def read(url,robots=None):
        nonlocal requests
        if requests>=5: raise ValueError('Structured read budget exhausted')
        if cancel_event and cancel_event.is_set(): raise InterruptedError('Cancelled')
        if robots and not robots.can_fetch(url,AGENT): raise AccessBlocked('Robots disallows structured source')
        requests+=1
        body,typ=get(url,'text/plain' if robots is None else 'text/html',cancel_event=cancel_event)
        if robots is not None and 'html' not in typ: raise ValueError('Expected structured HTML')
        return body,typ
    robot_body,typ=read(f'https://{p.netloc}/robots.txt')
    rules_text=robot_body.decode('utf-8-sig')
    if 'text/plain' not in typ or not re.search(r'^User-agent\s*:',rules_text,re.I|re.M): raise ValueError('Missing/invalid robots policy')
    robots=Protego.parse(rules_text)
    delay=max(1.0,float(robots.crawl_delay(AGENT) or 0))
    rate=robots.request_rate(AGENT)
    if rate: delay=max(delay,rate.seconds/rate.requests)
    def html(url):
        import time
        # Do not sleep through long publisher delays in an on-demand run.
        if delay>10: raise ValueError('Publisher pacing requires deferred/manual collection')
        time.sleep(delay)
        return selector(read(safe(url),robots)[0])
    page_url=safe(state.get('page') or start);page=html(page_url);rows=[]
    def extract(page,url):
        found=[]
        for raw in page.css('script[type="application/ld+json"]::text').getall()[:100]:
            try: value=json.loads(raw)
            except ValueError: continue
            for item in nodes(value):
                types=item.get('@type',[])
                if 'JobPosting' not in ([types] if isinstance(types,str) else types): continue
                organization=item.get('hiringOrganization') or {}
                if not isinstance(organization,dict): raise ValueError('Invalid hiring organization')
                loc=item.get('jobLocation') or {};loc=loc[0] if isinstance(loc,list) and loc else loc
                address=loc.get('address',{}) if isinstance(loc,dict) else {}
                location=', '.join(str(address[k]) for k in ('addressLocality','addressRegion','addressCountry') if isinstance(address,dict) and isinstance(address.get(k),str))
                restrictions=item.get('applicantLocationRequirements') or [];restrictions=restrictions if isinstance(restrictions,list) else [restrictions]
                extra=[r['name'] for r in restrictions if isinstance(r,dict) and isinstance(r.get('name'),str)]
                if item.get('jobLocationType')=='TELECOMMUTE': location='Remote · '+location
                if extra: location+=' · '+', '.join(extra)
                found.append({'title':item.get('title'),'company':organization.get('name'),
                    'url':safe(urljoin(url,item.get('url') or url)), 'description':text(item.get('description','')),
                    'location':location,'date_posted':item.get('datePosted',''),
                    'salary':structured_salary(item.get('baseSalary')),
                    'source_notice':'Source-backed structured metadata; remote does not imply worldwide eligibility.'})
        return found
    rows.extend(extract(page,page_url))
    next_links=[safe(urljoin(page_url,a.attrib['href'])) for a in page.css('link[rel="next"][href]')]
    if len(set(next_links))>1: raise ValueError('Ambiguous next page')
    pending=state.get('pending',[])
    if not isinstance(pending,list) or len(pending)>100: raise ValueError('Invalid structured pending state')
    if not rows and not pending:
        for anchor in page.css('a[href]')[:1000]:
            url=urljoin(page_url,anchor.attrib['href'])
            if url!=page_url and re.search(r'/(?:jobs?|careers?)/',urlsplit(url).path):
                try: pending.append(safe(url))
                except ValueError: pass
        pending=list(dict.fromkeys(pending))[:100]
    initial_pending=len(pending)
    while pending and requests<5:
        url=safe(pending.pop(0));rows.extend(extract(html(url),url))
    if not rows: raise ValueError('No usable JobPosting; unsupported recipe/schema, not empty success')
    index=int(state.get('index',1))
    if not 1<=index<=20: raise ValueError('Structured page limit reached')
    next_page=next_links[0] if next_links else None
    return Collection(rows,{'page':page_url if pending else next_page,'pending':pending,'index':index if pending else index+1,'complete':not pending and not next_page},
        {'requests':requests,'bounded_selection':bool(pending or next_page),'coverage_complete':not pending and not next_page,
         'reusable_source_established':len(rows)>1 or initial_pending>1 or bool(next_page),
         'source_scope':'Observed structured pages only; no arbitrary-site completeness'})
