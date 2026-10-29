"""Explicit ordinary-browser transport; no stealth, automatic fallback or login.

The optional Playwright client attaches only to a loopback, dedicated browser.
Only tabs created here are closed. Browser subresources are counted, not bounded
by the collector's five top-level navigation allowance. No cookies are exported.
"""
import os
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError
from .authorized_boards import safe_url, HOSTS, AccessBlocked

MESSAGES = {
    'runtime_missing': 'Install requirements-local-browser.txt; core HTTP mode is unchanged.',
    'endpoint_invalid': 'Browser endpoint must be http://127.0.0.1:PORT (or localhost/[::1]), without a path, credentials or query.',
    'connection_failed': 'Start the dedicated local browser using start_board_browser.ps1, then retry manually when due.',
    'navigation_failed': 'Public browser navigation failed; inspect the dedicated browser. No alternate transport was attempted.',
    'structured_data_timeout': 'Browser page did not expose the required publisher structured data before the deadline; no jobs/checkpoint committed.',
    'response_too_large': 'Browser HTML exceeds the configured byte limit; no jobs/checkpoint committed.',
    'content_type': 'Expected public HTML (or plain-text crawler rules) from the browser.',
}

class BrowserError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(MESSAGES[code])


def transport_mode():
    value = os.environ.get('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT', 'http')
    if value not in ('http', 'browser'):
        raise ValueError('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT must be http or browser')
    return value


def endpoint():
    value = os.environ.get('JOBHUNTER_BOARD_BROWSER_CDP', 'http://127.0.0.1:9222')
    try:
        p = urlsplit(value)
        if (p.scheme != 'http' or p.hostname not in ('127.0.0.1', 'localhost', '::1')
                or p.username is not None or p.password is not None or p.path not in ('', '/')
                or p.query or p.fragment or not p.port or not 1024 <= p.port <= 65535
                or any(ord(c) < 33 or ord(c) > 126 for c in value)):
            raise ValueError()
    except ValueError:
        raise BrowserError('endpoint_invalid') from None
    return value


# Readiness follows public DOM/JSON-LD only, never undocumented endpoints.
READY = r'''(detail) => {
 const walk=(x,d=0)=>d>20?false:Array.isArray(x)?x.some(v=>walk(v,d+1)):
  x && typeof x==='object' ? ([].concat(x['@type']||[]).includes('JobPosting') || Object.values(x).some(v=>walk(v,d+1))) : false;
 for(const s of document.querySelectorAll('script[type="application/ld+json"]')){
  try{if(walk(JSON.parse(s.textContent)))return true;}catch{}
 }
 if(detail)return false;
 return [...document.querySelectorAll('a[href]')].some(a=>a.origin===location.origin &&
   (location.hostname==='wuzzuf.net'?a.pathname.startsWith('/jobs/p/'):/-jid-[0-9]+$/.test(a.pathname)));
}'''

class BrowserHTML:
    def __init__(self, kind, cancel_event=None, connector=None):
        self.kind = kind
        self.cancel_event = cancel_event
        self.connector = connector  # Dependency injection for offline and managed-CDP acceptance tests.
        self.driver = self.page = None
        self.requests = 0
        self.navigations = 0
        self.violation = False

    def __enter__(self):
        self._cancel()
        address = endpoint() if self.connector is None else None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise BrowserError('runtime_missing') from None
        try:
            self.driver = sync_playwright().start()
            browser = self.connector(self.driver) if self.connector else self.driver.chromium.connect_over_cdp(address, timeout=10000)
            if not browser.contexts:
                raise BrowserError('connection_failed')
            self.page = browser.contexts[0].new_page()
            self.page.on('request', self._request)
            self.page.route('**/*', self._route)
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise BrowserError('connection_failed') from None

    def __exit__(self, *args):
        try:
            if self.page:
                self.page.close()
        finally:
            if self.driver:
                # Disconnect the client. Do NOT call browser.close(): the browser is user-owned.
                self.driver.stop()

    def _request(self, request):
        self.requests += 1

    def _allowed(self, url):
        if url == 'https://' + HOSTS[self.kind] + '/robots.txt':
            return
        try:
            safe_url(self.kind, url, detail=True)
        except ValueError:
            safe_url(self.kind, url)

    def _route(self, route):
        r = route.request
        if r.is_navigation_request() and r.frame == self.page.main_frame:
            try:
                self._allowed(r.url)
                if r.redirected_from is not None:
                    raise ValueError('redirect')
            except ValueError:
                self.violation = True
                route.abort()
                return
        # Normal browser assets are not fetched through the pinned-HTTP client.
        route.continue_()

    def _cancel(self):
        if self.cancel_event and self.cancel_event.is_set():
            raise InterruptedError('Collection cancelled')

    def get(self, url, accept='text/html', max_bytes=5*1024*1024):
        self._allowed(url)
        self._cancel()
        if self.navigations >= 6:
            raise ValueError('Browser navigation budget exceeded')
        self.navigations += 1
        self.violation = False
        deadline = time.monotonic() + 60
        try:
            response = self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if self.violation or self.page.url != url:
                raise AccessBlocked('Browser redirect or unapproved navigation; collection stopped')
            if response is None:
                raise BrowserError('navigation_failed')
            if response.status != 200:
                raise HTTPError(url, response.status, 'Public browser request rejected',
                                {'Retry-After': response.headers.get('retry-after', '')[:200]}, None)
            content_type = response.headers.get('content-type', '').lower()
            if url.endswith('/robots.txt'):
                if 'text/plain' not in content_type:
                    raise BrowserError('content_type')
                body = self.page.locator('body').inner_text(timeout=5000).encode('utf-8')
            else:
                if 'html' not in content_type:
                    raise BrowserError('content_type')
                try:
                    safe_url(self.kind, url, True)
                    detail = True
                except ValueError:
                    detail = False
                while True:
                    self._cancel()
                    visible = self.page.locator('body').inner_text(timeout=5000).lower()
                    if any(s in visible for s in ('verify you are human', 'checking your browser', 'access denied', 'just a moment', 'captcha')):
                        raise AccessBlocked('Browser access challenge; collection stopped')
                    if self.violation or self.page.url != url:
                        raise AccessBlocked('Browser navigation left the approved URL')
                    if self.page.evaluate(READY, detail):
                        break
                    if time.monotonic() >= deadline:
                        raise BrowserError('structured_data_timeout')
                    self.page.wait_for_timeout(250)
                # Bound serialized DOM before transferring it through CDP.
                body = self.page.evaluate('''limit => {const h=document.documentElement.outerHTML;
                    return new TextEncoder().encode(h).byteLength>limit ? null : h;}''', max_bytes)
                if body is None:
                    raise BrowserError('response_too_large')
                body = body.encode('utf-8')
            if len(body) > max_bytes:
                raise BrowserError('response_too_large')
            self._cancel()
            if self.violation or self.page.url != url:
                raise AccessBlocked('Browser navigation left the approved URL')
            return body, content_type
        except (HTTPError, AccessBlocked, BrowserError, InterruptedError):
            raise
        except Exception:
            if self.violation:
                raise AccessBlocked('Browser redirect or unapproved navigation; collection stopped') from None
            raise BrowserError('navigation_failed') from None

    def metrics(self):
        return {'transport': 'browser', 'request_unit': 'top_level_navigations', 'top_level_navigations': self.navigations,
                'browser_resource_requests_observed': self.requests,
                'browser_resource_notice': 'Normal browser assets make additional requests; five/six limits apply to top-level navigations, not total HTTP traffic.'}
