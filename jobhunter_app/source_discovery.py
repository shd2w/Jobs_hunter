"""Source leads from observed URLs/markup only. No guessed domains or endpoints."""
from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import re
from .search_strategy import fingerprint
from .validation import public_url


@dataclass(frozen=True)
class SourceLead:
    url: str
    origin_url: str
    field: str
    kind: str = ''
    identifier: str = ''
    posting_id: str = ''

    @property
    def id(self): return fingerprint([self.kind, self.identifier] if self.kind else [self.url])


def recognize(url):
    public_url(url)
    p=urlsplit(url)
    if p.scheme!='https' or p.username or p.port or p.fragment: return None
    host=p.hostname.lower(); parts=p.path.strip('/').split('/')
    kind=identifier=posting=''
    if host in ('boards.greenhouse.io','job-boards.greenhouse.io') and parts:
        kind,identifier='greenhouse',parts[0]
        if len(parts)>=3 and parts[1]=='jobs': posting=parts[2]
    elif host=='boards-api.greenhouse.io' and len(parts)>=3 and parts[:2]==['v1','boards']:
        kind,identifier='greenhouse',parts[2]
    elif host=='jobs.lever.co' and parts:
        kind,identifier='lever',parts[0]
        if len(parts)>=2: posting=parts[1]
    elif host=='jobs.ashbyhq.com' and parts:
        kind,identifier='ashby',parts[0]
        if len(parts)>=2: posting=parts[1]
    elif host in ('jobs.smartrecruiters.com','careers.smartrecruiters.com') and parts:
        kind,identifier='smartrecruiters',parts[0]
        if len(parts)>=2: posting=parts[1].split('-')[0]
    elif re.fullmatch(r'[a-z0-9-]+\.wd[0-9]+\.myworkdayjobs\.com',host):
        if parts and re.fullmatch(r'[a-z]{2}-[A-Z]{2}',parts[0]): parts=parts[1:]
        if parts:
            tenant,node,*_=host.split('.')
            kind,identifier='workday',f'{tenant}__{node}__{parts[0]}'
            if parts[-1] != parts[0]: posting=parts[-1]
    elif p.path.lower().endswith(('.rss','.atom','.xml')):
        from .network import feed_url
        feed_url(url);kind,identifier='feed',url
    if not kind: return None
    from .sources import Source
    Source(kind,identifier)  # closed production validation, never arbitrary host activation
    if posting and not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',posting): posting=''
    return kind,identifier,posting


class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('a','link'):
            values=dict(attrs)
            if len(self.links)<50 and values.get('href'): self.links.append(values['href'])


def discover(observations):
    leads=[];seen=set()
    for row in observations[:1000]:
        if not isinstance(row,dict): continue
        origin=row.get('origin_url') or row.get('url','')
        candidates=[(row.get('url',''),'listing')]
        for key in ('job_url_direct','company_url','career_url','application_url'):
            if row.get(key): candidates.append((row[key],key))
        parser=Links();parser.feed(str(row.get('description',''))[:100000])
        candidates += [(link,'description_link') for link in parser.links]
        for url,field in candidates:
            try:
                from .network import feed_url
                feed_url(url)  # reject credentials, social scopes and non-public schemes
                binding=recognize(url)
            except (ValueError,TypeError): continue
            lead=SourceLead(url,origin,field,*(binding or ('','','')))
            key=(lead.id,origin,field)
            if key not in seen: leads.append(lead);seen.add(key)
    return leads


def inspect_public(lead, getter=None):
    """Optional two-read first-party inspection; no redirects/login/JS execution."""
    from .network import get,feed_url
    from .scrapling_transport import AGENT
    from protego import Protego
    from .scrapling_engine import selector
    get=getter or get;requests=0
    def read(url,accept):
        nonlocal requests
        requests+=1
        return get(url,accept,max_bytes=1024*1024)
    try:
        feed_url(lead.url);p=urlsplit(lead.url)
        body,typ=read('https://'+p.netloc+'/robots.txt','text/plain')
        rules=body.decode('utf-8-sig')
        if 'text/plain' not in typ or not re.search(r'^User-agent\s*:',rules,re.I|re.M):
            raise ValueError('Unrecognized robots policy')
        robots=Protego.parse(rules)
        if not robots.can_fetch(lead.url,AGENT): raise ValueError('Robots disallows inspection')
        delay=max(1,float(robots.crawl_delay(AGENT) or 0))
        rate=robots.request_rate(AGENT)
        if rate: delay=max(delay,rate.seconds/rate.requests)
        if delay>10: raise ValueError('Publisher pacing requires deferred inspection')
        import time
        time.sleep(delay)
        body,typ=read(lead.url,'text/html')
        if 'html' not in typ: raise ValueError('Expected HTML inspection')
        page=selector(body)
        # Only observed first-party evidence; do not fetch unrecognized outgoing links.
        candidates=[]
        for anchor in page.css('a[href],iframe[src]')[:1000]:
            from urllib.parse import urljoin
            link=urljoin(lead.url,anchor.attrib.get('href') or anchor.attrib.get('src') or '')
            try:
                binding=recognize(link)
                if binding: candidates.append(SourceLead(link,lead.url,'inspected_link',*binding))
            except ValueError: pass
        return {'status':'recognized' if candidates else 'no_supported_family','requests':requests,'leads':candidates}
    except Exception as exc:
        return {'status':'blocked_or_unavailable','requests':requests,'error_category':type(exc).__name__,'leads':[]}
