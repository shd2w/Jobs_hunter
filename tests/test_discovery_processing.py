import pytest
from jobhunter_app.store import Store
from jobhunter_app.discovery_state import ensure
from jobhunter_app.discovery_processing import finish
from jobhunter_app.source_discovery import discover
from jobhunter_app.opportunity_identity import reconcile, unlink

JOB={'title':'Engineer','company':'Example','url':'https://jobs.lever.co/heldout/req1','description':'Python'}


def test_reversible_identity_requires_native_anchor_and_keeps_requisitions(tmp_path):
    store=Store(tmp_path/'app.db');ensure(store)
    other={**JOB,'url':'https://example.org/syndicated/1'}
    leads=discover([{'url':other['url'],'job_url_direct':JOB['url']}])
    store.ingest([other]);assert reconcile(store,leads)['groups']==0
    store.ingest([JOB,{**JOB,'url':'https://jobs.lever.co/heldout/req2'}],source='lever:heldout')
    result=reconcile(store,leads)
    assert result=={'members':3,'groups':2}
    assert len(store.jobs())==3
    job=next(j for j in store.jobs() if j['url']==other['url'])
    store.save_profile({'skills':['Python']});store.set_status(job['id'],'saved')
    unlink(store,job['id'])
    assert next(j for j in store.jobs() if j['id']==job['id'])['status']=='saved'
    assert len(store.jobs())==3


def test_pending_matching_and_failed_projection_retry_even_no_new_inserts(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');ensure(store);store.save_profile({'skills':['Python']})
    store.ingest([JOB]);store.ingest([JOB])
    def broken(*a): raise OSError('fixture')
    monkeypatch.setattr('scanners.compat.mirror_to_pipeline',broken)
    first=finish(store)
    assert first['local_matching']['evaluated']==1 and first['projection_pending']==1
    monkeypatch.setattr('scanners.compat.mirror_to_pipeline',lambda *a:{'new_added':0})
    second=finish(store)
    assert second['local_matching']['evaluated']==0 and second['projection_pending']==0
    assert finish(store)['projection_completed']==0
    store.ingest([{**JOB,'description':'Python SQL'}])
    assert finish(store)['local_matching']['evaluated']==1


def test_run_all_matches_pending_sqlite_despite_zero_legacy_inserts(tmp_path,monkeypatch):
    import asyncio,run_all
    monkeypatch.chdir(tmp_path)
    store=Store(tmp_path/'data/jobhunter.sqlite3');store.save_profile({'skills':['Python']});store.ingest([JOB])
    async def empty(**kw): return {'new_added':0,'total_found':0,'pending_legacy':0}
    monkeypatch.setattr(run_all,'run_scan',empty)
    asyncio.run(run_all._run_pipeline())
    assert store.summary()['matched_jobs']==1
