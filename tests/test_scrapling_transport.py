"""Verify actual Scrapling HTTP configuration with an offline session double."""
from types import SimpleNamespace
from threading import Event
from urllib.error import HTTPError
import pytest
pytest.importorskip('scrapling')
from jobhunter_app import scrapling_transport as transport

@pytest.fixture
def session(monkeypatch):
    from scrapling import fetchers
    calls=[];content={'body':b'<html>Public jobs</html>','status':200}
    class Fake:
        def __init__(self,**kwargs):self._curl_session=SimpleNamespace(curl_options={},trust_env=True);calls.append(('config',kwargs))
        def __enter__(self):return self
        def __exit__(self,*args):calls.append(('closed',True))
        def get(self,url,**kwargs):
            calls.append(('request',{'url':url,**kwargs,'options':self._curl_session.curl_options,'trust_env':self._curl_session.trust_env}))
            if not kwargs['content_callback'](content['body']):raise RuntimeError('Write aborted')
            return SimpleNamespace(status=content['status'],headers={'content-type':'text/html','retry-after':'600'})
    monkeypatch.setattr(fetchers,'FetcherSession',Fake)
    monkeypatch.setattr(transport,'public_addresses',lambda host:['93.184.216.34'])
    return calls,content


def test_fetcher_real_controls_pin_dns_disable_stealth_redirects_proxy_and_retries(session):
    from curl_cffi import CurlOpt
    calls,_=session
    body,typ=transport.get('https://jobicy.com/jobs')
    assert body.startswith(b'<html>') and typ=='text/html'
    config=calls[0][1];request=calls[1][1]
    assert config['impersonate'] is None and not config['stealthy_headers']
    assert config['retries']==1 and not config['follow_redirects'] and config['verify']
    assert request['options'][CurlOpt.RESOLVE]==['jobicy.com:443:93.184.216.34']
    assert request['options'][CurlOpt.PROXY]=='' and not request['trust_env']
    assert request['discard_cookies'] and calls[-1][0]=='closed'


@pytest.mark.parametrize('status',[301,302,401,403,429,500])
def test_redirects_and_failures_not_treated_as_jobs(session,status):
    calls,content=session;content['status']=status
    with pytest.raises(HTTPError) as exc:transport.get('https://jobicy.com/jobs')
    assert exc.value.code==status
    assert sum(c[0]=='request' for c in calls)==1


def test_streamed_byte_cap_closes_session(session):
    calls,content=session;content['body']=b'x'*20
    with pytest.raises(ValueError,match='byte limit'):transport.get('https://jobicy.com/jobs',max_bytes=10)
    assert calls[-1][0]=='closed'


def test_cancel_before_fetch_never_sends_request(session):
    calls,_=session;cancel=Event();cancel.set()
    with pytest.raises(InterruptedError):transport.get('https://jobicy.com/jobs',cancel_event=cancel)
    assert not calls


def test_private_dns_failure_never_constructs_fetcher(session,monkeypatch):
    calls,_=session
    def invalid(host):raise ValueError('Source DNS includes a non-public address')
    monkeypatch.setattr(transport,'public_addresses',invalid)
    with pytest.raises(ValueError,match='non-public'):transport.get('https://jobicy.com/jobs')
    assert not calls
