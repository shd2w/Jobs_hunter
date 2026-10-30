"""Equivalent real CLI/HTTP intake, source scan, configuration and stored outcomes."""
import json
import time
from threading import Thread
import pytest
import run_local
from jobhunter_app.store import Store
from jobhunter_app.web import make_server
from jobhunter_app.sources import register
from tests.test_web_local import request,token
from tests.test_evaluation_parity import PROFILE
from tests.test_phase3_sources import serve,jobicy

POST={'origin_url':'https://example.org/post/parity','source_label':'Fixture','body':'We are hiring!\nRole: Python Analyst\nCompany: Fixture Employer\nLocation: Remote\nApply: https://example.org/jobs/parity\nPython required'}
FEED='<rss version="2.0"><channel><item><title>Python Analyst</title><link>https://example.org/post/parity</link><description>'+POST['body']+'</description></item></channel></rss>'

@pytest.fixture
def paths(tmp_path):
    stores=[Store(tmp_path/(name+'.db')) for name in ('cli','http')]
    for store in stores:store.save_profile(PROFILE)
    server=make_server(stores[1],0);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield stores,(stores[1],server)
    finally:server.shutdown();server.server_close();thread.join(3)

@pytest.mark.parametrize('kind',['posts','feed'])
def test_intake_equivalent_configuration_results_and_database(paths,tmp_path,capsys,kind):
    (cli,http),web=paths
    file=tmp_path/('input.json' if kind=='posts' else 'input.xml');file.write_text(json.dumps([POST]) if kind=='posts' else FEED)
    assert run_local.main(['--db',str(cli.path),'posts-process' if kind=='posts' else 'feed-import',str(file),'--rights-attested'])==0
    a=json.loads(capsys.readouterr().out)
    status,_,raw=request(web,'POST','/api/posts/process' if kind=='posts' else '/api/feed-import',{'posts':[POST],'rights_attested':True} if kind=='posts' else {'content':FEED,'rights_attested':True},{'X-JobHunter-Token':token(web)})
    assert status==200;b=json.loads(raw)
    for key in ('received','invalid','auto_added','linked_existing','needs_review','evaluated','staged'):assert a.get(key)==b.get(key)
    def snapshot(store):
        return [{k:v for k,v in j.items() if k not in ('first_seen','last_seen')} for j in store.jobs()]
    assert snapshot(cli)==snapshot(http)
    assert cli.summary()['total_jobs']==http.summary()['total_jobs']


def test_source_scan_equivalent_http_worker_and_cli(paths,monkeypatch,capsys):
    (cli,http),web=paths
    ids=[register(store,'jobicy','remote',True) for store in (cli,http)]
    serve(monkeypatch,lambda u,k:{'jobs':[jobicy()],'hasMore':False,'nextCursor':None})
    assert run_local.main(['--db',str(cli.path),'scan',ids[0]])==0;a=json.loads(capsys.readouterr().out)
    assert request(web,'POST','/api/scan',{'source_id':ids[1]},{'X-JobHunter-Token':token(web)})[0]==200
    for _ in range(200):
        task=json.loads(request(web,'GET','/api/task')[2])
        if not task['running']:break
        time.sleep(.01)
    assert not task['error'] and task['status']=='success' and task['started_at'] and task['finished_at']
    for key in ('inserted','updated','invalid','received','pagination','status'):assert a[key]==task['result'][key]
    assert cli.job(cli.jobs()[0]['id'])==http.job(http.jobs()[0]['id'])
