"""Fixed-host, bounded manual collection. Checkpoints are committed by sources.scan."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit, parse_qs
import json
import os
import re
import time

@dataclass
class Collection:
    payload: object
    checkpoint: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    posts: bool = False
    leads: list = field(default_factory=list)

class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
        elif not self.hidden and tag in ('p','br','div','li'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
        elif not self.hidden and tag in ('p','div','li'): self.parts.append('\n')
    def handle_data(self, text):
        if not self.hidden: self.parts.append(text)

def text(html):
    if not isinstance(html, str): raise ValueError('Invalid source text')
    p=Paragraphs();p.feed(html);return ''.join(p.parts).strip()

def collect(source, checkpoint=None, cancel_event=None):
    from .network import get
    state=checkpoint or {}; requests=0
    def read(url, credentials=None):
        nonlocal requests
        if cancel_event and cancel_event.is_set(): raise InterruptedError('Collection cancelled')
        if requests: time.sleep(0.6)
        requests+=1
        body,typ=get(url, credentials=credentials) if credentials is not None else get(url)
        if 'json' not in typ: raise ValueError('Expected JSON')
        from .intake import strict_json
        return strict_json(body.decode('utf-8-sig'))
    def finish(payload, next_state, complete, **metrics):
        return Collection(payload,next_state,{'requests':requests,'coverage_complete':complete,'bounded_selection':not complete,**metrics})
    if source.kind=='smartrecruiters':
        offset=int(state.get('offset',0)); pending=state.get('pending',[])
        total=state.get('total',0)
        if not pending:
            if state.get('complete'): offset=0
            root=read(f'https://api.smartrecruiters.com/v1/companies/{source.identifier}/postings?'+urlencode({'limit':100,'offset':offset}))
            if not isinstance(root,dict) or not isinstance(root.get('content'),list) or len(root['content'])>100: raise ValueError('Invalid posting list')
            total=root.get('totalFound',len(root['content']))
            if type(total) is not int or total<0: raise ValueError('Invalid total')
            pending=[x.get('id') if isinstance(x,dict) else None for x in root['content']]
            offset+=len(pending)
        entries=[]
        for identity in pending[:10]:
            if isinstance(identity,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identity):
                entries.append(read(f'https://api.smartrecruiters.com/v1/companies/{source.identifier}/postings/{identity}'))
            else: entries.append({})
        remaining=pending[10:]; complete=not remaining and offset>=total
        return finish({'content':entries,'totalFound':total}, {'offset':offset,'pending':remaining,'total':total,'complete':complete}, complete,total_reported=total)
    if source.kind=='jobicy':
        cursor=state.get('cursor') if not state.get('complete') else None
        started=state.get('started',time.time()) if cursor else time.time()
        if cursor and time.time()-started>=86400: raise ValueError('Jobicy cursor expired; reset checkpoint explicitly')
        params={'count':100}
        if cursor: params['cursor']=cursor
        root=read('https://jobicy.com/api/jobs?'+urlencode(params))
        if not isinstance(root,dict) or not isinstance(root.get('jobs'),list) or len(root['jobs'])>100 or type(root.get('hasMore')) is not bool: raise ValueError('Invalid Jobicy payload')
        cursor=root.get('nextCursor')
        if root['hasMore'] and cursor == state.get('cursor'): raise ValueError('Repeated pagination cursor; reset explicitly after reviewing source')
        if root['hasMore'] and (not isinstance(cursor,str) or not 1<=len(cursor)<=4000): raise ValueError('Invalid cursor')
        return finish(root,{'cursor':cursor if root['hasMore'] else None,'started':started,'complete':not root['hasMore']},not root['hasMore'],window='7-day feed, delayed 3 hours; absence does not establish closure')
    if source.kind=='arbeitnow':
        page=1 if state.get('complete') else int(state.get('page',1))
        base='https://www.arbeitnow.co.uk' if source.identifier=='uk' else 'https://www.arbeitnow.com'
        root=read(base+'/api/job-board-api?'+urlencode({'page':page}))
        if not isinstance(root,dict) or not isinstance(root.get('data'),list) or len(root['data'])>1000: raise ValueError('Invalid Arbeitnow payload')
        nxt=(root.get('links') or {}).get('next')
        next_page=None
        if nxt:
            if not isinstance(nxt,str): raise ValueError('Invalid page link')
            p=urlsplit(nxt);values=parse_qs(p.query).get('page',[])
            # The remote URL is never fetched; only an increasing page number is used.
            if len(values)!=1 or not values[0].isdigit() or int(values[0])!=page+1: raise ValueError('Invalid page sequence')
            next_page=page+1
        return finish(root,{'page':next_page or 1,'complete':next_page is None},next_page is None)
    if source.kind=='usajobs':
        key=os.environ.get('USAJOBS_API_KEY','');agent=os.environ.get('USAJOBS_USER_AGENT','')
        if not key or not agent: raise ValueError('USAJOBS requires explicit environment configuration')
        page=1 if state.get('complete') else int(state.get('page',1))
        root=read('https://data.usajobs.gov/api/Search?'+urlencode({'Keyword':source.identifier,'Page':page,'ResultsPerPage':50,'WhoMayApply':'public'}),{'User-Agent':agent,'Authorization-Key':key})
        result=root.get('SearchResult') if isinstance(root,dict) else None
        if not isinstance(result,dict) or not isinstance(result.get('SearchResultItems'),list) or len(result['SearchResultItems'])>50: raise ValueError('Invalid USAJOBS payload')
        total=int(result.get('SearchResultCountAll',0));complete=page*50>=total
        return finish(root,{'page':page+1,'complete':complete},complete,total_reported=total)
    if source.kind=='hn':
        base='https://hacker-news.firebaseio.com/v0/item/'
        root=read(base+source.identifier+'.json')
        if not isinstance(root,dict) or root.get('type')!='story' or not re.search(r'^Ask HN:\s*Who is hiring\?',root.get('title',''),re.I) or root.get('dead') or root.get('deleted'): raise ValueError('Use an explicit HN Who is hiring thread')
        kids=root.get('kids',[])
        if not isinstance(kids,list) or len(kids)>10000 or any(type(x) is not int or x<=0 for x in kids): raise ValueError('Invalid thread children')
        seen=set(state.get('seen',[]));todo=[x for x in kids if x not in seen];rows=[]
        for identity in todo[:10]:
            item=read(base+str(identity)+'.json');seen.add(identity)
            if item is None: continue
            if not isinstance(item,dict): raise ValueError('Invalid comment')
            if item.get('dead') or item.get('deleted') or item.get('type')!='comment' or item.get('parent')!=int(source.identifier): continue
            body=text(item.get('text',''))
            if not body: continue
            rows.append({'body':body,'origin_url':f'https://news.ycombinator.com/item?id={identity}','source_label':source.id,'published':str(item.get('time',''))})
        # No user profiles, author names or reply trees are collected.
        return Collection(rows,{'seen':sorted(seen.intersection(kids))}, {'requests':requests,'coverage_complete':len(todo)<=10,'bounded_selection':len(todo)>10,'retrieved_comments':min(len(todo),10),'source_context':'HN Who is hiring thread; individual comments unverified'},True)
    raise ValueError('No bounded collector for source')
