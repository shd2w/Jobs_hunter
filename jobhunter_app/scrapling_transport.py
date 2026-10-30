"""Bounded Scrapling HTTP engine. Fixed-source URLs are checked by the caller.

Scrapling 0.5's session hook is pinned and fail-closed: libcurl must use the
public DNS result we validated, not resolve the hostname a second time. There
is no stealth, proxy, redirect following, cookie persistence or browser launch.
"""
import time
import re
from urllib.parse import urlsplit
from urllib.error import HTTPError
from .network import public_addresses
from .validation import public_url

AGENT='JobHunter-Local/0.4 ScraplingEngine'
MAX_BYTES=5*1024*1024

class ScraplingRuntimeMissing(ImportError):
    pass

class ScraplingTransportError(ValueError):
    pass


def get(url,accept='text/html',max_bytes=MAX_BYTES,cancel_event=None):
    public_url(url)
    p=urlsplit(url)
    if p.scheme!='https' or p.port is not None or p.fragment or (p.query and not re.fullmatch(r'page=[1-9][0-9]{0,2}',p.query)):
        raise ValueError('Scrapling engine requires canonical HTTPS URLs without port/query/fragment')
    if not isinstance(max_bytes,int) or not 1<=max_bytes<=MAX_BYTES:raise ValueError('Invalid byte budget')
    if cancel_event and cancel_event.is_set():raise InterruptedError('Collection cancelled')
    address=public_addresses(p.hostname)[0]
    try:
        from scrapling.fetchers import FetcherSession
        from curl_cffi import CurlOpt
    except ImportError:
        raise ScraplingRuntimeMissing('Install requirements-scanners.lock; Scrapling fetching runtime is missing') from None
    chunks=[];size=0;aborted=None;deadline=time.monotonic()+20
    def receive(chunk):
        nonlocal size,aborted
        if cancel_event and cancel_event.is_set():aborted='cancelled';return 0
        if time.monotonic()>deadline:aborted='timeout';return 0
        size+=len(chunk)
        if size>max_bytes:aborted='size';return 0
        chunks.append(chunk);return len(chunk)
    try:
        with FetcherSession(impersonate=None,stealthy_headers=False,retries=1,
                follow_redirects=False,max_redirects=0,verify=True,timeout=20,
                proxies={'all':''},headers={'User-Agent':AGENT,'Accept':accept,
                    'Accept-Encoding':'identity'},selector_config={'adaptive':False}) as session:
            # This is the only version-pinned internal integration seam. Refuse
            # to issue a request if a future Scrapling release changes it.
            raw=getattr(session,'_curl_session',None)
            if raw is None or not hasattr(raw,'curl_options') or not hasattr(raw,'trust_env'):
                raise ScraplingTransportError('Unsupported Scrapling transport hook; no request sent')
            ip='['+address+']' if ':' in address else address
            raw.trust_env=False
            raw.curl_options={CurlOpt.RESOLVE:[f'{p.hostname}:443:{ip}'],
                CurlOpt.MAXFILESIZE_LARGE:max_bytes,CurlOpt.PROXY:'',
                CurlOpt.PROTOCOLS_STR:'https',CurlOpt.REDIR_PROTOCOLS_STR:'https'}
            response=session.get(url,content_callback=receive,accept_encoding='identity',discard_cookies=True)
    except Exception:
        if aborted=='cancelled':raise InterruptedError('Collection cancelled') from None
        if aborted=='timeout':raise TimeoutError('Scrapling read deadline exceeded') from None
        if aborted=='size':raise ValueError('Source response exceeds byte limit') from None
        raise
    if cancel_event and cancel_event.is_set():raise InterruptedError('Collection cancelled')
    headers={k.lower():v for k,v in response.headers.items()}
    if response.status!=200:
        raise HTTPError(url,response.status,'Scrapling source request rejected',
            {'Retry-After':headers.get('retry-after','')[:200]},None)
    if headers.get('content-encoding','identity') not in ('','identity'):
        raise ValueError('Compressed source response rejected')
    body=b''.join(chunks)
    if not body:raise ValueError('Empty Scrapling response')
    return body,headers.get('content-type','').lower()
