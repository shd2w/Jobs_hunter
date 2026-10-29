"""Real loopback HTTP tests, including CSRF, DNS rebinding and payload boundaries."""
import http.client
import json
import re
from threading import Thread
import pytest
from jobhunter_app.store import Store
from jobhunter_app.web import make_server
from tests.test_local_store import JOB, PROFILE

@pytest.fixture
def web(tmp_path):
    store=Store(tmp_path/'web.sqlite3');store.save_profile(PROFILE)
    server=make_server(store,0)
    t=Thread(target=server.serve_forever,daemon=True);t.start()
    yield store,server
    server.shutdown();server.server_close();t.join(timeout=3)


def request(web,method,path,data=None,headers=None):
    _,server=web
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    body=json.dumps(data) if data is not None else None
    all_headers={'Content-Type':'application/json',**(headers or {})}
    conn.request(method,path,body,all_headers)
    response=conn.getresponse();raw=response.read();out=(response.status,dict(response.getheaders()),raw)
    conn.close();return out


def token(web):
    return re.search(rb'name="csrf-token" content="([^"]+)"',request(web,'GET','/')[2]).group(1).decode()


def test_home_and_headers(web):
    status,headers,body=request(web,'GET','/')
    assert status==200 and b'JobHunter' in body and b'__CSRF__' not in body
    assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert headers['Cache-Control']=='no-store'
    assert headers['X-Content-Type-Options']=='nosniff'

@pytest.mark.parametrize('path',['/app.js','/style.css','/api/profile','/api/summary','/api/learning','/api/task','/api/jobs','/api/history?id=test','/api/export?format=csv','/api/export?format=json'])
def test_routes(web,path):assert request(web,'GET',path)[0]==200

@pytest.mark.parametrize('path',['/../../etc/passwd','/.env','/app.js/../../.env','/unknown'])
def test_no_filesystem_traversal(web,path):assert request(web,'GET',path)[0]==404


def test_rebinding_rejected(web):
    assert request(web,'GET','/',headers={'Host':'evil.example'})[0]==403


def test_csrf_and_origin(web):
    assert request(web,'POST','/api/import',{'jobs':[JOB]})[0]==403
    assert request(web,'POST','/api/import',{'jobs':[JOB]}, {'X-JobHunter-Token':token(web),'Origin':'https://evil.example'})[0]==403
    assert web[0].summary()['total_jobs']==0


def test_content_type_size_and_bad_body(web):
    t=token(web)
    assert request(web,'POST','/api/import',{'jobs':[JOB]}, {'X-JobHunter-Token':t,'Content-Type':'text/plain'})[0]==415
    assert request(web,'POST','/api/import',{'jobs':[JOB]}, {'X-JobHunter-Token':t,'Content-Length':str(11*1024*1024)})[0]==413
    assert request(web,'POST','/api/import',[], {'X-JobHunter-Token':t})[0]==400


def test_http_end_to_end(web):
    store,_=web;t={'X-JobHunter-Token':token(web)}
    assert request(web,'POST','/api/import',{'jobs':[JOB],'dry_run':True},t)[0]==200
    assert store.summary()['total_jobs']==0
    assert request(web,'POST','/api/import',{'jobs':[JOB]},t)[0]==200
    assert request(web,'POST','/api/match',{},t)[0]==200
    jobs=json.loads(request(web,'GET','/api/jobs')[2]);j=jobs[0]
    assert j['match']['score_percent']==100
    assert request(web,'POST','/api/status',{'id':j['id'],'status':'saved','notes':'User note'},t)[0]==200
    assert store.jobs()[0]['notes']=='User note'
    assert request(web,'POST','/api/pack',{'id':j['id']},t)[0]==200
    assert request(web,'POST','/api/backup',{},t)[0]==200
    assert json.loads(request(web,'GET','/api/history?id='+j['id'])[2])[0]['new_status']=='saved'


def test_no_web_filesystem_profile_selection(web):
    status,_,_=request(web,'POST','/api/profile',{'profile':{'original_cv':'/etc/passwd'}},{'X-JobHunter-Token':token(web)})
    assert status==400


def test_unknown_status_bad_query_and_exports(web):
    assert request(web,'GET','/api/jobs?status=invalid')[0]==400
    assert request(web,'GET','/api/jobs?offset=bad')[0]==400
    assert request(web,'GET','/api/export?format=html')[0]==400


def test_xss_payload_remains_inert_json(web):
    payload='<img src=x onerror=alert(1)>'
    request(web,'POST','/api/import',{'jobs':[{**JOB,'title':payload}]},{'X-JobHunter-Token':token(web)})
    _,headers,body=request(web,'GET','/api/jobs')
    assert headers['Content-Type'].startswith('application/json')
    assert json.loads(body)[0]['title']==payload
    script=request(web,'GET','/app.js')[2]
    assert b'innerHTML' not in script and b'textContent' in script
