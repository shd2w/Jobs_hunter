"""Immutable version publication, conservative integrity and explicit self-review."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
import yaml
from agents.cover_letter import CoverLetterWriter
from jobhunter_app.documents import prepare_pack
from jobhunter_app.store import Store
from jobhunter_app import pack_management as pm
from tests.test_local_store import JOB, PROFILE
from tests.test_web_local import web, request, token

@pytest.fixture
def bundle(tmp_path):
    s=Store(tmp_path/'local.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0]
    root=tmp_path/'packs';pack=prepare_pack(s,job['id'],root)
    return s,root,pack

def history_count(store):
    with store.connect() as db:return db.execute('SELECT count(*) FROM status_history').fetchone()[0]

def inspect(b):
    s,r,p=b;return pm.inspect_pack(s,r,p['version_id'])

def decide(b,decision='reviewed',**overrides):
    s,r,p=b;v=inspect(b);args={'confirmed':True,'checks':{k:True for k in pm.CHECKS}}
    args.update(overrides)
    return pm.review_pack(s,r,p['version_id'],decision,v['fingerprint'],**args)

def test_pending_review_rejection_and_fresh_version_isolation(bundle):
    s,r,p=bundle;v=inspect(bundle);assert v['valid'] and v['review_state']=='pending' and not v['history']
    assert p['review_state']=='pending' and v['validation_report']==p['validation_report']
    original={n: (Path(p['directory'])/n).read_bytes() for n in ('preparation.json','cover-letter-draft.txt','pack.json')}
    a=decide(bundle);assert a['review_state']=='reviewed' and a['review_required']
    assert a['history'][0]['confirmed'] and a['history'][0]['actor']=='local user self-record'
    b=decide(bundle,'needs_changes',checks={k:False for k in pm.CHECKS})
    assert b['review_state']=='needs_changes' and len(b['history'])==2
    assert s.jobs()[0]['status']=='discovered' and history_count(s)==0
    assert all((Path(p['directory'])/n).read_bytes()==raw for n,raw in original.items())
    second=prepare_pack(s,v['job_id'],r)
    assert second['version_id']!=p['version_id'] and pm.inspect_pack(s,r,second['version_id'])['review_state']=='pending'
    assert inspect(bundle)['review_state']=='needs_changes'

@pytest.mark.parametrize('confirmed',[False,None,1,'true'])
def test_explicit_human_confirmation_required(bundle,confirmed):
    with pytest.raises(ValueError):decide(bundle,confirmed=confirmed)
    assert inspect(bundle)['history']==[]

@pytest.mark.parametrize('checks',[{},None,[],{'facts':True},{k:1 for k in pm.CHECKS},dict.fromkeys(pm.CHECKS,False)])
def test_reviewed_requires_all_four_true_boolean_checks(bundle,checks):
    with pytest.raises(ValueError):decide(bundle,checks=checks)
    assert inspect(bundle)['history']==[]

@pytest.mark.parametrize('decision',['approved','applied','',None,True])
def test_no_approval_or_application_decision(bundle,decision):
    with pytest.raises(ValueError):decide(bundle,decision)

@pytest.mark.parametrize('bad',['../outside','../../etc/passwd','a/b','A'*32,'1'*31,'1'*33,None,False,[],{}])
def test_opaque_identifier_only(bundle,bad):
    s,r,_=bundle
    with pytest.raises(ValueError):pm.inspect_pack(s,r,bad)


def test_stale_preview_and_parallel_review_cannot_overwrite(bundle):
    s,r,p=bundle;preview=inspect(bundle)
    def run(_):
        try:return pm.review_pack(s,r,p['version_id'],'reviewed',preview['fingerprint'],True,{k:True for k in pm.CHECKS})
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(run,range(5)))
    assert sum(x is not None for x in results)==1 and len(inspect(bundle)['history'])==1
    with pytest.raises(ValueError,match='preview changed'):pm.review_pack(s,r,p['version_id'],'needs_changes',preview['fingerprint'],True,{k:False for k in pm.CHECKS})

@pytest.mark.parametrize('change',['name','skills','facts','job','cv'])
def test_changed_inputs_block_historical_review(bundle,tmp_path,change):
    s,r,p=bundle
    if change=='cv':
        source=tmp_path/'cv.pdf';source.write_bytes(b'%PDF-original synthetic');s.save_profile({**PROFILE,'original_cv':str(source)})
        p=prepare_pack(s,inspect(bundle)['job_id'],r);bundle=(s,r,p)
    decide(bundle)
    if change=='cv':source.write_bytes(b'%PDF-different synthetic')
    elif change=='job':s.ingest([{**JOB,'description':'Updated Python listing'}])
    else:
        profile=deepcopy(PROFILE)
        if change=='name':profile['name']+=' changed'
        if change=='skills':profile['skills']=['SQL']
        if change=='facts':profile['facts'][0]['source']+=' updated'
        s.save_profile(profile)
    v=inspect(bundle);assert not v['valid'] and v['review_state']=='blocked' and len(v['history'])==1
    with pytest.raises(ValueError):decide(bundle)


def test_tracking_status_not_pack_content_change(bundle):
    s,r,p=bundle;s.set_status(inspect(bundle)['job_id'],'applied','Synthetic user note')
    assert inspect(bundle)['valid'] and inspect(bundle)['review_state']=='pending'
    decide(bundle);assert s.jobs()[0]['status']=='applied' and history_count(s)==1


def test_provenance_change_blocks_pack(bundle,monkeypatch):
    from jobhunter_app import posts
    monkeypatch.setattr(posts,'origins',lambda *a:[{'synthetic':'new provenance'}])
    assert not inspect(bundle)['valid']

@pytest.mark.parametrize('filename',['cover-letter-draft.txt','preparation.json','original-cv.pdf'])
def test_artifact_changes_or_symlinks_block_review(bundle,tmp_path,filename):
    s,r,p=bundle
    if filename.endswith('.pdf'):
        cv=tmp_path/'original.pdf';cv.write_bytes(b'%PDF-SYNTHETIC');s.save_profile({**PROFILE,'original_cv':str(cv)})
        p=prepare_pack(s,inspect(bundle)['job_id'],r);bundle=(s,r,p)
    path=Path(p['directory'])/filename;path.write_text('MODIFIED SYNTHETIC FILE')
    assert not inspect(bundle)['valid']
    with pytest.raises(ValueError):decide(bundle)
    path.unlink();outside=tmp_path/'outside';outside.write_text('UNRELATED PRIVATE FILE');path.symlink_to(outside)
    assert not inspect(bundle)['valid'] and outside.read_text()=='UNRELATED PRIVATE FILE'
    with pytest.raises(ValueError):decide(bundle)


def test_owner_profile_and_manifest_traversal_rejected(bundle,tmp_path):
    s,r,p=bundle;s.save_profile(PROFILE,'other')
    assert pm.list_packs(s,r,'other')['packs']==[]
    with pytest.raises(ValueError):pm.inspect_pack(s,r,p['version_id'],'other')
    folder=Path(p['directory']);manifest=json.loads((folder/'pack.json').read_text())
    manifest['artifacts']['../outside']='0'*64;pm.write_json(folder/'pack.json',manifest)
    with pytest.raises(ValueError,match='artifact list'):inspect(bundle)
    assert pm.list_packs(s,r)['packs']==[]


def test_symlink_folder_and_manifest_rejected(bundle,tmp_path):
    s,r,p=bundle;folder=Path(p['directory']);fake='a'*32
    (r/('pack-'+fake)).symlink_to(folder,target_is_directory=True)
    with pytest.raises(ValueError):pm.inspect_pack(s,r,fake)
    manifest=folder/'pack.json';copy=tmp_path/'copy.json';copy.write_bytes(manifest.read_bytes());manifest.unlink();manifest.symlink_to(copy)
    with pytest.raises(ValueError):inspect(bundle)


def test_history_corruption_is_not_reset_or_treated_as_reviewed(bundle):
    decide(bundle);decide(bundle,'needs_changes');folder=Path(bundle[2]['directory'])/'reviews';first=folder/'000001.json'
    first.write_text('{}');before=first.read_bytes();v=inspect(bundle)
    assert not v['valid'] and v['review_state']=='blocked'
    with pytest.raises(ValueError):decide(bundle)
    assert first.read_bytes()==before and len(list(folder.iterdir()))==2


def test_profile_and_manifest_without_owned_format_are_not_auto_migrated(bundle):
    s,r,p=bundle;old=r/'old-pack';old.mkdir();(old/'cover.txt').write_text('SYNTHETIC OLD EDIT')
    stage=r/'.pack-stage-incomplete';stage.mkdir();(stage/'cover-letter-draft.txt').write_text('SYNTHETIC INCOMPLETE')
    listing=pm.list_packs(s,r);assert len(listing['packs'])==1
    assert (old/'cover.txt').read_text()=='SYNTHETIC OLD EDIT' and stage.exists()
    assert not pm.list_packs(s,r,job_id='missing')['packs']
    assert not pm.list_packs(s,r,offset=50)['packs']
    with pytest.raises(ValueError):pm.list_packs(s,r,limit=0)


def test_parallel_core_creation_has_unique_complete_versions(bundle):
    s,r,p=bundle;job=inspect(bundle)['job_id']
    with ThreadPoolExecutor(max_workers=5) as pool:packs=list(pool.map(lambda _:prepare_pack(s,job,r),range(5)))
    assert len({x['version_id'] for x in packs})==5
    assert all(pm.inspect_pack(s,r,x['version_id'])['valid'] for x in packs)
    assert len(pm.list_packs(s,r)['packs'])==6 and not list(r.glob('.pack-stage-*'))


def test_failed_seal_and_changed_input_cleanup_only_new_stage(bundle,monkeypatch):
    s,r,p=bundle;job=inspect(bundle)['job_id'];old=Path(p['directory']);before=(old/'pack.json').read_bytes()
    original=pm.seal_pack
    def failed(*a,**kw):raise OSError('synthetic disk full')
    monkeypatch.setattr(pm,'seal_pack',failed)
    with pytest.raises(OSError):prepare_pack(s,job,r)
    assert (old/'pack.json').read_bytes()==before and not list(r.glob('.pack-stage-*'))
    def changed(*a,**kw):
        result=original(*a,**kw);s.save_profile({**PROFILE,'name':'Changed during creation'});return result
    monkeypatch.setattr(pm,'seal_pack',changed)
    with pytest.raises(ValueError,match='inputs changed'):prepare_pack(s,job,r)
    assert (old/'pack.json').read_bytes()==before and not list(r.glob('.pack-stage-*'))


def test_publish_collision_preserves_existing_folder(bundle,tmp_path):
    _,r,p=bundle;stage=tmp_path/'owned-stage';stage.mkdir();(stage/'new').write_text('NEW')
    before=(Path(p['directory'])/'pack.json').read_bytes()
    with pytest.raises(ValueError,match='already exists'):pm.publish_version(r,stage,p['version_id'])
    assert stage.exists() and (Path(p['directory'])/'pack.json').read_bytes()==before


def test_legacy_reruns_parallel_and_old_flat_files_preserved(tmp_path):
    cfg=tmp_path/'profile.yml';cfg.write_text(yaml.safe_dump({'candidate':{'full_name':PROFILE['name']},'verified_facts':PROFILE['facts']}))
    root=tmp_path/'legacy';root.mkdir();flat=root/'old-cover.md';flat.write_text('SYNTHETIC PRIOR FLAT EDIT')
    writer=CoverLetterWriter(output_dir=root,profile_path=cfg);first=writer.generate(JOB);path=Path(first['output_path']);side=path.with_suffix('.evidence.json')
    path.write_text('SYNTHETIC PRIOR VERSION EDIT');side.write_text('SYNTHETIC PRIOR SIDECAR EDIT')
    with ThreadPoolExecutor(max_workers=5) as pool:out=list(pool.map(lambda _:writer.generate(JOB),range(5)))
    assert len({x['output_path'] for x in out})==5 and all(x['success'] for x in out)
    assert path.read_text()=='SYNTHETIC PRIOR VERSION EDIT' and side.read_text()=='SYNTHETIC PRIOR SIDECAR EDIT'
    assert flat.read_text()=='SYNTHETIC PRIOR FLAT EDIT' and not list(root.glob('.pack-stage-*'))
    for x in out:
        q=Path(x['output_path']);assert q.name.endswith('-cover.md') and q.with_suffix('.evidence.json').exists()
        m=json.loads((q.parent/'draft-version.json').read_text());assert m['version_id']==x['version_id']
        assert all(sha256((q.parent/name).read_bytes()).hexdigest()==h for name,h in m['artifacts'].items())


def test_legacy_failed_sidecar_cleans_new_stage_not_previous(tmp_path,monkeypatch):
    cfg=tmp_path/'profile.yml';cfg.write_text(yaml.safe_dump({'candidate':{'full_name':PROFILE['name']},'verified_facts':PROFILE['facts']}))
    root=tmp_path/'legacy';writer=CoverLetterWriter(output_dir=root,profile_path=cfg);first=writer.generate(JOB);before=Path(first['output_path']).read_bytes()
    monkeypatch.setattr(pm,'write_json',lambda *a,**k:(_ for _ in ()).throw(OSError('synthetic failure')))
    with pytest.raises(OSError):writer.generate(JOB)
    assert Path(first['output_path']).read_bytes()==before and len(list(root.iterdir()))==1


def test_http_owned_root_review_confirmation_and_staleness(web):
    s,_=web;s.ingest([JOB]);job=s.jobs()[0];h={'X-JobHunter-Token':token(web)}
    p=json.loads(request(web,'POST','/api/pack',{'id':job['id']},h)[2]);version=p['version_id']
    listing=json.loads(request(web,'GET','/api/packs?job_id='+job['id'])[2]);assert listing['packs'][0]['version_id']==version
    assert request(web,'GET','/api/pack-inspect?id=../../etc/passwd')[0]==400
    v=json.loads(request(web,'GET','/api/pack-inspect?id='+version+'&root=/etc')[2]);assert v['valid'] and v['review_state']=='pending'
    args={'id':version,'decision':'reviewed','fingerprint':v['fingerprint'],'confirmed':True,'checks':{k:True for k in pm.CHECKS}}
    assert request(web,'POST','/api/pack-review',args)[0]==403
    assert request(web,'POST','/api/pack-review',{**args,'confirmed':False},h)[0]==400
    reviewed=json.loads(request(web,'POST','/api/pack-review',args,h)[2]);assert reviewed['review_state']=='reviewed'
    assert request(web,'POST','/api/pack-review',args,h)[0]==400
    assert s.jobs()[0]['status']=='discovered' and history_count(s)==0

@pytest.mark.parametrize('change',['missing','symlink','bad-shape'])
def test_invalid_history_events_block_without_writes(bundle,tmp_path,change):
    decide(bundle);decide(bundle,'needs_changes');folder=Path(bundle[2]['directory'])/'reviews'
    first=folder/'000001.json'
    if change=='missing':first.unlink()
    elif change=='symlink':
        first.unlink();outside=tmp_path/'outside.json';outside.write_text('{}');first.symlink_to(outside)
    else:first.write_text('[]')
    assert not inspect(bundle)['valid']
    before={p.name:p.lstat().st_size for p in folder.iterdir()}
    with pytest.raises(ValueError):decide(bundle)
    assert {p.name:p.lstat().st_size for p in folder.iterdir()}==before


def test_review_write_failure_keeps_history_and_prior_files(bundle,monkeypatch):
    decide(bundle);folder=Path(bundle[2]['directory']);previous=(folder/'reviews/000001.json').read_bytes()
    monkeypatch.setattr(pm.os,'replace',lambda *a,**k:(_ for _ in ()).throw(OSError('synthetic disk full')))
    with pytest.raises(OSError):decide(bundle,'needs_changes')
    assert (folder/'reviews/000001.json').read_bytes()==previous and len(list((folder/'reviews').iterdir()))==1
    assert inspect(bundle)['review_state']=='reviewed'


def test_review_limit_and_root_symlink(bundle,tmp_path,monkeypatch):
    monkeypatch.setattr(pm,'MAX_REVIEWS',1);decide(bundle)
    with pytest.raises(ValueError,match='limit'):decide(bundle)
    s,r,p=bundle;link=tmp_path/'linked-root';link.symlink_to(r,target_is_directory=True)
    with pytest.raises(ValueError):pm.list_packs(s,link)
    with pytest.raises(ValueError):prepare_pack(s,inspect(bundle)['job_id'],link)
