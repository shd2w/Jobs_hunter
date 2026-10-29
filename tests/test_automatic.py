"""Offline first-run and scheduler contracts. No provider requests or credentials."""
import json
import time
from pathlib import Path
from threading import Event, Thread
from urllib.error import HTTPError
import pytest
from jobhunter_app.automatic import AutomaticDiscovery, configure, KEY
from jobhunter_app.store import Store, dump, now
from jobhunter_app.sources import register, Source
from jobhunter_app.workflow import settings
from jobhunter_app.web import make_server
from tests.test_local_store import PROFILE
from tests.test_web_local import request, token

@pytest.fixture(autouse=True)
def original_starter_scope(monkeypatch):
    # Isolate the original three-feed scheduler contract; expanded sources have
    # their own tests. Offline tests must never invoke a real JobSpy request.
    monkeypatch.setattr('jobhunter_app.automatic.STARTERS',
        (('jobicy', 'remote'), ('arbeitnow', 'de'), ('remotive', 'remote')))

@pytest.fixture
def store(tmp_path): return Store(tmp_path/'app.db')

def payload(url):
    if 'jobicy' in url: return {'jobs':[{'id':1,'url':'https://jobicy.com/jobs/1','jobTitle':'Python Engineer','companyName':'Example','jobGeo':'Worldwide','jobDescription':'Python required'}],'hasMore':False,'nextCursor':None}
    if 'arbeitnow' in url: return {'data':[{'slug':'fixture','url':'https://www.arbeitnow.com/jobs/fixture','title':'SQL Engineer','company_name':'Example DE','location':'Berlin','description':'SQL required'}],'links':{'next':None}}
    return {'jobs':[{'id':3,'url':'https://remotive.com/remote-jobs/3','title':'Support Engineer','company_name':'Example Remote','candidate_required_location':'Worldwide','description':'Support required'}]}

@pytest.fixture
def transport(monkeypatch):
    calls=[]
    def get(url,*args,**kwargs):
        assert not kwargs.get('credentials');calls.append(url)
        return json.dumps(payload(url)).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    return calls

def test_first_run_no_input_fetches_jobs(store,transport):
    a=AutomaticDiscovery(store);a.cycle()
    assert len(transport)==3 and store.summary()['total_jobs']==3
    assert store.profile()['skills']==[] and store.summary()['matched_jobs']==0
    assert all(s['next_allowed_at'] for s in a.status()['sources'])
    a.cycle();assert len(transport)==3
    assert a.status()['enabled']

def test_bootstrap_once_preserves_user_profile_pause_and_namespaces(store):
    store.save_profile(PROFILE)
    with store.connect() as db: db.execute('INSERT INTO workflow_settings VALUES(?,?,?)',('default',dump({'saved_searches':[{'private':'retained'}],'learning_progress':{'private':'retained'}}),now()))
    register(store,'jobicy','remote',False)
    configure(store);configure(store,enabled=False);configure(store)
    assert store.profile()==PROFILE
    with store.connect() as db:
        data=json.loads(db.execute('SELECT data FROM workflow_settings').fetchone()[0])
        assert data['saved_searches']==[{'private':'retained'}] and data['learning_progress']=={'private':'retained'}
        assert data[KEY]['enabled'] is False
        assert db.execute("SELECT approved FROM sources WHERE id='jobicy:remote'").fetchone()[0]==0
        assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==3
    assert settings(store)['enabled'] is False
    settings(store,value={'enabled':False})
    with store.connect() as db: assert json.loads(db.execute('SELECT data FROM workflow_settings').fetchone()[0])[KEY]['enabled'] is False

@pytest.mark.parametrize('bad',[None,{},True,{'version':True,'enabled':True},{'version':1,'enabled':1},{'version':2,'enabled':True}])
def test_corrupt_config_never_reset(store,bad):
    store.save_profile(PROFILE)
    with store.connect() as db: db.execute('INSERT INTO workflow_settings VALUES(?,?,?)',('default',dump({KEY:bad}),now()))
    with pytest.raises(ValueError):configure(store)
    assert store.profile()==PROFILE
    with store.connect() as db: assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==0

@pytest.mark.parametrize('bad',[0,1,'yes',[],{}])
def test_choice_strict_boolean(store,bad):
    with pytest.raises(ValueError):configure(store,enabled=bad)

def test_one_failed_feed_does_not_block_others(store,transport,monkeypatch):
    real_get=__import__('jobhunter_app.network',fromlist=['get']).get
    def get(url,*args,**kwargs):
        if 'jobicy' in url: raise HTTPError(url,403,'denied',{},None)
        return real_get(url,**kwargs)
    monkeypatch.setattr('jobhunter_app.network.get',get)
    a=AutomaticDiscovery(store);a.cycle()
    assert store.summary()['total_jobs']==2
    assert next(x for x in a.status()['sources'] if x['id']=='jobicy:remote')['health']=='failed'

def test_rate_limit_pauses_provider_without_bypass(store,transport,monkeypatch):
    def get(url,*args,**kwargs):
        if 'jobicy' in url: raise HTTPError(url,429,'quota',{'Retry-After':'7200'},None)
        transport.append(url);return json.dumps(payload(url)).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    a=AutomaticDiscovery(store);a.cycle();assert store.summary()['total_jobs']==2
    a.choice(False);a.choice(True);a.cycle()
    source=next(x for x in a.status()['sources'] if x['id']=='jobicy:remote')
    assert not source['approved'] and source['health']=='rate_limited'
    assert len(transport)==2

def test_pause_persists_restart_and_resume_retains_cooldowns(store,transport):
    a=AutomaticDiscovery(store);a.choice(False);a.cycle();assert transport==[]
    b=AutomaticDiscovery(store);b.cycle();assert transport==[]
    b.choice(True);b.cycle();assert len(transport)==3
    b.choice(False);b.choice(True);b.cycle();assert len(transport)==3
    assert store.summary()['total_jobs']==3

def test_pause_from_other_server_discards_inflight_response(store,transport,monkeypatch):
    entered,release=Event(),Event()
    def get(url,*args,**kwargs):
        transport.append(url);entered.set();assert release.wait(5)
        return json.dumps(payload(url)).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    a=AutomaticDiscovery(store);b=AutomaticDiscovery(store)
    t=Thread(target=a.cycle);t.start();assert entered.wait(3)
    b.choice(False);release.set();t.join(5)
    assert not t.is_alive() and store.summary()['total_jobs']==0 and len(transport)==1
    assert a.status()['enabled'] is False

def test_profile_optional_and_existing_profile_gets_local_matching(store,transport):
    store.save_profile(PROFILE);a=AutomaticDiscovery(store);a.cycle()
    assert store.profile()==PROFILE and store.summary()['matched_jobs']==3
    store.save_profile({**PROFILE,'skills':['SQL']});a.cycle()
    assert len(transport)==3 and store.summary()['matched_jobs']==3

def test_deleted_default_not_readded_on_restart(store):
    a=AutomaticDiscovery(store)
    with store.connect() as db: db.execute("DELETE FROM sources WHERE id='remotive:remote'")
    AutomaticDiscovery(store)
    assert len(a.status()['sources'])==2

def test_shutdown_worker(store,transport):
    a=AutomaticDiscovery(store,interval=1);a.start()
    end=time.monotonic()+5
    while not a.state['last_cycle'] and time.monotonic()<end:time.sleep(.05)
    a.stop();assert not a.thread.is_alive() and len(transport)==3

def test_http_defaults_off_and_no_get_mutation(store,monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('unexpected automatic request')
    monkeypatch.setattr('jobhunter_app.network.get',forbidden)
    server=make_server(store,0)
    t=Thread(target=server.serve_forever,daemon=True);t.start();w=(store,server)
    try:
        data=json.loads(request(w,'GET','/api/automatic')[2]);assert not data['available']
        assert request(w,'GET','/automatic.js')[0]==200
        assert request(w,'POST','/api/automatic',{'enabled':True},{'X-JobHunter-Token':token(w)})[0]==400
        with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==0
    finally:server.shutdown();server.server_close();t.join(3)

def test_http_automatic_control_csrf_and_input(store,transport,monkeypatch):
    monkeypatch.setattr(AutomaticDiscovery,'start',lambda self:None)
    server=make_server(store,0,automatic=True);t=Thread(target=server.serve_forever,daemon=True);t.start();w=(store,server)
    try:
        assert request(w,'POST','/api/automatic',{'enabled':False})[0]==403
        headers={'X-JobHunter-Token':token(w)}
        for data in ({'enabled':'false'},{'enabled':False,'force':True},{}): assert request(w,'POST','/api/automatic',data,headers)[0]==400
        assert request(w,'POST','/api/automatic',{'enabled':False},headers)[0]==200
        assert not json.loads(request(w,'GET','/api/automatic')[2])['enabled']
        assert request(w,'POST','/api/automatic-check',{'force':True},headers)[0]==400
        assert request(w,'POST','/api/automatic-check',{},headers)[0]==200
        assert transport==[]
    finally:server.shutdown();server.server_close();t.join(3)

def test_expired_starter_cursor_restarts_due_pass_without_extra_request(store,transport):
    a=AutomaticDiscovery(store)
    with store.connect() as db:
        db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',('jobicy:remote',dump({'cursor':'expired','started':time.time()-90000,'complete':False}),now()))
    a.cycle();assert len(transport)==3 and 'cursor=' not in transport[0]
    assert store.summary()['total_jobs']==3

def test_fair_rotation_does_not_starve_extra_sources(store,monkeypatch):
    a=AutomaticDiscovery(store)
    for i in range(12):register(store,'greenhouse','fixture'+str(i),True)
    visited=[]
    def scan(store,identity,**kwargs):
        visited.append(identity)
        with store.connect() as db:db.execute('UPDATE sources SET last_run=? WHERE id=?',(now(),identity))
    monkeypatch.setattr('jobhunter_app.automatic.scan',scan)
    a.cycle();assert len(visited)==10
    a.cycle();assert len(set(visited))==15


def test_codespace_start_script_restarts_only_owned_process(tmp_path):
    import os, signal, subprocess, sys
    root=tmp_path/'repo';(root/'.devcontainer').mkdir(parents=True)
    (root/'.devcontainer/start.sh').write_bytes(Path('.devcontainer/start.sh').read_bytes())
    (root/'run_local.py').write_text("import time,signal\nfrom pathlib import Path\np=Path('data/starts');p.write_text(p.read_text()+'x' if p.exists() else 'x')\nsignal.signal(signal.SIGTERM,lambda *args:exit(0))\nwhile True:time.sleep(.1)\n")
    bindir=tmp_path/'bin';bindir.mkdir();(bindir/'python').symlink_to(sys.executable)
    env={**os.environ,'PATH':str(bindir)+':'+os.environ['PATH']}
    def run(*args):return subprocess.run(['bash','.devcontainer/start.sh',*args],cwd=root,env=env,capture_output=True,text=True,timeout=10)
    pid=None
    try:
        result=run();assert result.returncode==0,result.stdout+result.stderr
        pid=int((root/'data/dashboard.pid').read_text());assert (root/'data/starts').read_text()=='x'
        assert run().returncode==0 and (root/'data/starts').read_text()=='x'
        result=run('--restart');assert result.returncode==0,result.stdout+result.stderr
        pid=int((root/'data/dashboard.pid').read_text());assert (root/'data/starts').read_text()=='xx'
        os.kill(pid,signal.SIGTERM);pid=None
        # Pointing at this test runner must never terminate it or start another.
        (root/'data/dashboard.pid').write_text(str(os.getpid()))
        result=run('--restart');assert result.returncode==1 and 'another process' in result.stdout
        assert (root/'data/starts').read_text()=='xx'
    finally:
        if pid:
            try:os.kill(pid,signal.SIGTERM)
            except ProcessLookupError:pass
