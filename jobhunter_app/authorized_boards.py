"""Opt-in, fixed-host HTML collectors. No hidden APIs or challenge bypass.

Only publisher JobPosting JSON-LD is normalized. Listing links without structured
posting data are not guessed into jobs. Live HTML compatibility is time-bound.
"""
from html.parser import HTMLParser
import json
import os
import re
import time
from urllib.parse import urlsplit, urljoin, parse_qsl
from urllib.robotparser import RobotFileParser

HOSTS = {'wuzzuf': 'wuzzuf.net', 'naukrigulf': 'www.naukrigulf.com'}
AGENT = 'JobHunter-Local/0.3'
MAX_DETAILS = 4
MAX_PAGES = 50

def robots_mode():
    """This user-authorized build skips robots only for HOSTS; reversible locally."""
    mode=os.environ.get('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','skip')
    if mode not in ('skip','check'): raise ValueError('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS must be skip or check')
    return mode


class AccessBlocked(ValueError):
    """Requires fresh access review before another manual attempt."""
    pass


def safe_url(kind, value, detail=False):
    from .validation import public_url
    public_url(value)
    p = urlsplit(value)
    if (p.scheme != 'https' or p.hostname != HOSTS[kind] or p.netloc != HOSTS[kind]
            or p.fragment or len(value) > 1000):
        raise ValueError('Use the exact authorized HTTPS board host without credentials, port or fragment')
    if not re.fullmatch(r'/[A-Za-z0-9_./%+-]+', p.path) or '%' in p.path or '..' in p.path or '//' in p.path:
        raise ValueError('Unsupported board path')
    if detail:
        valid = (p.path.startswith('/jobs/p/') and len(p.path) > 8) if kind == 'wuzzuf' else bool(re.fullmatch(r'/[A-Za-z0-9_-]+-jid-[0-9]+', p.path))
        if not valid or p.query: raise ValueError('Unsupported job detail URL')
    else:
        valid = (p.path.startswith('/a/') or p.path.startswith('/jobs/careers/')) if kind == 'wuzzuf' else bool(re.fullmatch(r'/[A-Za-z0-9_-]+', p.path))
        if kind == 'naukrigulf' and not ('jobs' in p.path): valid = False
        pairs = parse_qsl(p.query, keep_blank_values=True)
        if p.query and (len(pairs) != 1 or pairs[0][0] != ('start' if kind == 'wuzzuf' else 'page') or not re.fullmatch(r'[0-9]{1,4}', pairs[0][1])):
            raise ValueError('Only a bounded numeric pagination parameter is supported; no search/tracking URLs')
        if not valid: raise ValueError('Supply an authorized public listing URL, not an account or search endpoint')
    return value


class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.documents=[]; self.script=None; self.parts=[]; self.anchor=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='script' and a.get('type','').lower()=='application/ld+json': self.script=True; self.parts=[]
        if tag=='a' and len(self.links)<1000:
            self.anchor={'url':a.get('href',''), 'next':'next' in a.get('rel','').split(), 'label':''}
        if tag=='link' and 'next' in a.get('rel','').split() and len(self.links)<1000:
            self.links.append({'url':a.get('href',''),'next':True,'label':''})
    def handle_data(self, data):
        if self.script: self.parts.append(data)
        if self.anchor: self.anchor['label']+=data[:100]
    def handle_endtag(self, tag):
        if tag=='script' and self.script:
            self.documents.append(''.join(self.parts));self.script=None;self.parts=[]
        if tag=='a' and self.anchor:
            self.links.append(self.anchor);self.anchor=None


def nodes(value, depth=0):
    if depth > 20: raise ValueError('Structured data nesting limit')
    if isinstance(value,list):
        for x in value: yield from nodes(x,depth+1)
    elif isinstance(value,dict):
        yield value
        for x in value.values():
            if isinstance(x,(list,dict)): yield from nodes(x,depth+1)


def parse(kind, body, page_url):
    from .sources import plain, POLICIES
    p=Page();p.feed(body.decode('utf-8-sig'))
    # Challenges must never be mistaken for empty listings.
    visible=plain(body.decode('utf-8-sig')).lower()
    if any(x in visible for x in ('verify you are human','checking your browser','access denied','just a moment','captcha')):
        raise AccessBlocked('Access challenge; stop and use an authorized manual import')
    rows=[]; links=list(p.links); recognized=False
    for doc in p.documents[:100]:
        try: root=json.loads(doc)
        except (ValueError,TypeError): continue
        for item in nodes(root):
            typ=item.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
            if not isinstance(typ,list): continue
            if 'ListItem' in typ:
                entry=item.get('item'); url=(entry.get('url') if isinstance(entry,dict) else entry) or item.get('url')
                if isinstance(url,str): links.append({'url':url,'next':False,'label':''})
            if 'JobPosting' not in typ: continue
            recognized=True
            try:
                raw_url=item.get('url') or page_url
                url=safe_url(kind,urljoin(page_url,raw_url),True)
                org=item.get('hiringOrganization') or {}; loc=item.get('jobLocation') or []
                loc=loc if isinstance(loc,list) else [loc]; locations=[]
                for x in loc:
                    address=x.get('address',{}) if isinstance(x,dict) else {}
                    if isinstance(address,str): locations.append(address)
                    elif isinstance(address,dict):
                        locations.append(', '.join(str(address[k]) for k in ('addressLocality','addressRegion','addressCountry') if isinstance(address.get(k),str)))
                if not isinstance(item.get('title'),str) or not isinstance(org,dict) or not isinstance(org.get('name'),str) or not isinstance(item.get('description'),str):
                    raise ValueError('Missing structured job fields')
                rows.append({'title':item['title'],'company':org['name'],'url':url,'location':'; '.join(locations),
                             'description':plain(item['description']),'date_posted':item.get('datePosted','') if isinstance(item.get('datePosted',''),str) else '',
                             'attribution':'Wuzzuf' if kind=='wuzzuf' else 'Naukrigulf','source_notice':POLICIES[kind]['notice']})
            except (ValueError,TypeError,AttributeError): rows.append({})
    details=[]; next_urls=[]
    for link in links:
        try: url=urljoin(page_url,link['url'])
        except (ValueError,TypeError): continue
        if link['next'] or link['label'].strip().lower() in ('next','next page','التالي'):
            try: next_urls.append(safe_url(kind,url))
            except ValueError: raise ValueError('Unsafe next-page link; review listing configuration')
        else:
            try: details.append(safe_url(kind,url,True))
            except ValueError: pass
    details=list(dict.fromkeys(details)); next_urls=list(dict.fromkeys(next_urls))
    if len(next_urls)>1: raise ValueError('Ambiguous next-page links')
    if not recognized and not details: raise ValueError('Unsupported HTML; no structured jobs or supported detail links')
    if len(details)>200: raise ValueError('Listing detail bound exceeded; no checkpoint committed')
    return rows,details,next_urls[0] if next_urls else None


def collect(source, checkpoint=None, cancel_event=None, getter=None):
    from .network import get
    from .collection import Collection
    get = getter or get
    kind=source.kind; origin='https://'+HOSTS[kind]; initial=safe_url(kind,source.identifier)
    state=checkpoint or {}; requests=0; mode=robots_mode()
    def read(url, robots=None, rules_request=False):
        nonlocal requests
        if requests>=6: raise ValueError('Board request budget exceeded')
        if cancel_event and cancel_event.is_set(): raise InterruptedError('Collection cancelled')
        if robots and not robots.can_fetch(AGENT,url): raise AccessBlocked('Crawler rules disallow this URL')
        if requests:
            delay=max(1.0,float(robots.crawl_delay(AGENT) or 0)) if robots else 1.0
            if delay>10: raise ValueError('Crawler delay exceeds interactive scan budget; use supplied import')
            time.sleep(delay)
        if cancel_event and cancel_event.is_set(): raise InterruptedError('Collection cancelled')
        requests+=1
        body,typ=get(url,'text/plain' if rules_request else 'text/html',max_bytes=256*1024 if rules_request else 5*1024*1024)
        if rules_request:
            if 'text/plain' not in typ: raise ValueError('Crawler rules unavailable; fail closed')
        elif 'html' not in typ: raise ValueError('Expected public HTML')
        return body
    robots=None
    if mode=='check':
        body=read(origin+'/robots.txt',rules_request=True)
        rules=body.decode('utf-8-sig')
        if not re.search(r'^User-agent\s*:',rules,re.I|re.M): raise ValueError('Unrecognized crawler rules; fail closed')
        robots=RobotFileParser();robots.parse(rules.splitlines())
        rate=robots.request_rate(AGENT)
        if rate and rate.seconds / rate.requests > 1: raise ValueError('Crawler request-rate needs a slower configured route; use authorized import')
    pending=state.get('pending',[]); page=state.get('page',initial); index=state.get('index',1); visited=state.get('visited',[])
    if state.get('complete'): pending=[];page=initial;index=1;visited=[]
    if not isinstance(pending,list) or len(pending)>200 or type(index) is not int or not 1<=index<=MAX_PAGES or not isinstance(visited,list) or len(visited)>MAX_PAGES:
        raise ValueError('Invalid board checkpoint; review and reset explicitly')
    pending=[safe_url(kind,x,True) for x in pending]
    rows=[];next_page=state.get('next_page'); listing=page
    safe_url(kind,listing)
    if not pending:
        rows,links,next_page=parse(kind,read(listing,robots),listing)
        found={r.get('url') for r in rows}; pending=[u for u in links if u not in found]
        if listing not in visited: visited=visited+[listing]
    for url in pending[:MAX_DETAILS]:
        detail,_,_=parse(kind,read(url,robots),url)
        if not detail: raise ValueError('Detail page lacks supported JobPosting data')
        # A detail URL must not silently attribute another page's posting to it.
        if any(r and r.get('url')!=url for r in detail): raise ValueError('Mismatched detail canonical URL')
        rows.extend(detail)
    remaining=pending[MAX_DETAILS:]
    if next_page:
        safe_url(kind,next_page)
        if next_page in visited or next_page==listing: raise ValueError('Repeated page URL; checkpoint not advanced')
    exhausted=not remaining and not next_page
    capped=not remaining and bool(next_page) and index>=MAX_PAGES
    next_state={'page':listing if remaining else next_page or initial,'index':index if remaining else index+1 if next_page else 1,
                'pending':remaining,'next_page':next_page if remaining else None,'visited':visited,'complete':exhausted}
    if capped: raise ValueError('50-page route bound reached; review and explicitly reset')
    unique={};bad=[]
    for row in rows:
        if row: unique[row['url']]=row
        else: bad.append(row)
    return Collection(list(unique.values())+bad,next_state,{'requests':requests,'robots_mode':mode,'robots_requests':1 if mode=='check' else 0,'coverage_complete':False,
        'bounded_selection':True,'listing_pass_exhausted':exhausted,'listing_page':index,'pending_details':len(remaining),
        'transport':'browser' if getter else 'http','live_compatibility':'publisher HTML can change; see current release live evidence','source_scope':'authorized public listing links and JobPosting JSON-LD only; not whole-site coverage'})
