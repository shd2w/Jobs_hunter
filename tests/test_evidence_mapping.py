"""Exact explicit links are user judgments, not semantic or truth verification."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
from jobhunter_app.evidence_mapping import preview,resolve,automatic,fact_id
from jobhunter_app.documents import cover_draft,validate_cover_report,prepare_pack
from jobhunter_app.pack_management import inspect_pack,review_pack
from jobhunter_app.store import Store
from tests.test_local_store import PROFILE,JOB
from tests.test_web_local import web,request,token


def mapping(job=JOB,profile=PROFILE,field='description',quote='Python',reason='My project demonstrates the requested programming skill.',indices=None):
 p=preview(job,profile);start=job[field].index(quote)
 return {'format':1,'preview_fingerprint':p['preview_fingerprint'],'confirmed':True,'links':[{'fact_id':f['id'],'field':field,'start':start,'end':start+len(quote),'quote':quote,'reason':reason} for i,f in enumerate(p['facts']) if i in (indices if indices is not None else [0])]}


def test_readonly_preview_explicit_order_and_exact_metadata():
 p=deepcopy(PROFILE);p['facts'] += [{'text':'I coordinated a pottery workshop.','source':'Synthetic workshop record','verified':True}]
 before=deepcopy((JOB,p));pr=preview(JOB,p);assert len(pr['facts'])==2 and len(pr['preview_fingerprint'])==64
 m=mapping(profile=p,indices=[1]);d=cover_draft(JOB,p,m)
 assert d['evidence']==[p['facts'][1]] and d['relevance']['status']=='user_attested'
 assert d['relevance']['links'][0]['quote']=='Python' and d['evidence_mapping']==m
 assert p['facts'][1]['text'] in d['content'] and p['facts'][0]['text'] not in d['content']
 assert m['links'][0]['reason'] not in d['content'] and (JOB,p)==before
 assert d['validation_report']['valid'] and d['validation_report']['bindings']['relevance_sha256']
 assert validate_cover_report(d['content'],JOB,p,[p['facts'][1]['text']],m)==d['validation_report']
 assert 'not independent' in d['relevance']['notice']


def test_automatic_never_fills_with_unrelated_facts_or_claims_relevance():
 p={**PROFILE,'facts':PROFILE['facts']+[{'text':'I completed a pottery workshop.','source':'Synthetic','verified':True}]}
 d=cover_draft(JOB,p);assert d['evidence']==PROFILE['facts']
 assert d['relevance']['status']=='lexical_cues_only' and 'are relevant' not in d['content']
 with pytest.raises(ValueError,match='explicit evidence map'):cover_draft(JOB,{**p,'facts':p['facts'][1:]})
 bad=validate_cover_report(d['content'],JOB,p,[p['facts'][1]['text']]);assert not bad['valid'] and bad['bindings'] is None


@pytest.mark.parametrize('change',[{'name':'Changed'},{'facts':[]},{'facts':[{'text':'I built another Python project.','source':'User project record','verified':True}]},{'facts':[{'text':PROFILE['facts'][0]['text'],'source':'Changed source','verified':True}]},{'facts':[{'text':PROFILE['facts'][0]['text'],'source':'User project record','verified':False}]}])
def test_changed_identity_fact_source_or_revocation_stales_preview(change):
 with pytest.raises(ValueError):resolve(JOB,{**PROFILE,**change},mapping())


@pytest.mark.parametrize('field',['title','company','url','description'])
def test_changed_target_stales_preview(field):
 with pytest.raises(ValueError,match='preview changed'):resolve({**JOB,field:JOB[field]+' changed'},PROFILE,mapping())


@pytest.mark.parametrize('key,value',[("format",2),("format",True),("confirmed",False),("confirmed",1),("confirmed","true"),("preview_fingerprint",'x'),('links',[]),('links',None),('links',{}),('links','x')])
def test_invalid_map_top_level(key,value):
 m=mapping();m[key]=value
 with pytest.raises(ValueError):resolve(JOB,PROFILE,m)


@pytest.mark.parametrize('key,value',[('fact_id','a'*64),('fact_id',[]),('field','company'),('field',[]),('start',True),('start',-1),('start',1.5),('end',999999),('end',False),('end',0),('quote','python'),('quote',''),('quote',None),('quote','x'*1001),('reason',''),('reason',' '),('reason','x'*1001),('reason','x\x00y'),('reason','x\ud800y')])
def test_invalid_exact_link(key,value):
 m=mapping();m['links'][0][key]=value
 with pytest.raises(ValueError):resolve(JOB,PROFILE,m)


@pytest.mark.parametrize('top',[None,[],False,'x',42])
def test_invalid_mapping_objects(top):
 with pytest.raises(ValueError):resolve(JOB,PROFILE,top)


def test_unknown_keys_duplicate_over_limit_and_selected_order():
 m=mapping();m['extra']=True
 with pytest.raises(ValueError):resolve(JOB,PROFILE,m)
 m=mapping();m['links'][0]['extra']='x'
 with pytest.raises(ValueError):resolve(JOB,PROFILE,m)
 for n in (2,4):
  m=mapping();m['links']*=n
  with pytest.raises(ValueError):resolve(JOB,PROFILE,m)
 p={**PROFILE,'facts':[{'text':f'Fact {i}','source':f'Source {i}','verified':True} for i in range(4)]}
 m=mapping(profile=p,indices=[0,1,2]);m['links'].reverse();d=cover_draft(JOB,p,m)
 assert d['evidence']==list(reversed(p['facts'][:3])) and d['validation_report']['bindings']['selected_count']==3
 wrong=validate_cover_report(d['content'],JOB,p,[f['text'] for f in p['facts'][:3]],m);assert not wrong['valid']


def test_exact_repeated_occurrence_unicode_codepoints_and_literal_markup():
 job={**JOB,'description':'😀 وظيفة Python required.\nPython preferred.'}
 reason='صلة <img src=x onerror=window.BAD_MAPPING=1> مع الدليل'
 m=mapping(job=job,reason=reason);m['links'][0]['start']=job['description'].rindex('Python');m['links'][0]['end']=m['links'][0]['start']+6
 d=cover_draft(job,PROFILE,m);assert d['relevance']['links'][0]['start']==25
 assert d['relevance']['links'][0]['reason']==reason and reason not in d['content']
 assert m==d['evidence_mapping'];d['evidence_mapping']['links'][0]['reason']='mutation';assert m['links'][0]['reason']==reason


def test_reason_changes_binding_not_cover_prose_and_detached_preview():
 m=mapping();a=cover_draft(JOB,PROFILE,m);m['links'][0]['reason']='Different reviewed explanation';b=cover_draft(JOB,PROFILE,m)
 assert a['content']==b['content'] and a['validation_report']['bindings']['contract_sha256']!=b['validation_report']['bindings']['contract_sha256']
 p=preview(JOB,PROFILE);p['facts'][0]['text']='mutated';assert preview(JOB,PROFILE)['facts'][0]['text']==PROFILE['facts'][0]['text']


def test_duplicate_fact_uses_first_authorized_source_and_rejects_unverified():
 p={**PROFILE,'facts':[PROFILE['facts'][0],{**PROFILE['facts'][0],'source':'Second source'},{'text':'Fake','source':'S','verified':False}]}
 assert len(preview(JOB,p)['facts'])==1 and preview(JOB,p)['facts'][0]['source']==PROFILE['facts'][0]['source']


def test_title_only_mapping_no_lexicon_required():
 job={**JOB,'title':'Workshop Coordinator','description':''};p={**PROFILE,'facts':[{'text':'I organized an exhibition.','source':'Synthetic record','verified':True}]}
 with pytest.raises(ValueError):cover_draft(job,p)
 d=cover_draft(job,p,mapping(job,p,field='title',quote='Coordinator'));assert d['validation_report']['valid']


def test_explicit_link_wordlimit_still_enforced():
 p={**PROFILE,'facts':[{'text':' '.join(['word']*350),'source':'Synthetic','verified':True}]}
 with pytest.raises(ValueError,match='350'):cover_draft(JOB,p,mapping(profile=p))


def test_mapping_pack_persists_and_current_inspection_blocks_changes(tmp_path):
 s=Store(tmp_path/'a.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();job=s.jobs()[0]
 before=(s.profile(),s.jobs(),s.summary());m=mapping(job);root=tmp_path/'packs';d=prepare_pack(s,job['id'],root,evidence_mapping=m);folder=Path(d['directory']);side=json.loads((folder/'preparation.json').read_text())
 assert side['cover']['evidence_mapping']==m and side['cover']['relevance']['status']=='user_attested'
 inspected=inspect_pack(s,root,d['version_id']);assert inspected['valid'] and inspected['evidence_relevance']==side['cover']['relevance']
 assert (s.profile(),s.jobs(),s.summary())==before
 backed=Store(s.backup(tmp_path/'backup.sqlite3'));assert inspect_pack(backed,root,d['version_id'])['valid']
 s.save_profile({**PROFILE,'facts':[{**PROFILE['facts'][0],'source':'Changed source'}]});assert not inspect_pack(s,root,d['version_id'])['valid']
 assert json.loads((folder/'preparation.json').read_text())==side


def test_invalid_stale_mapping_creates_no_output_and_no_cv_changes(tmp_path):
 s=Store(tmp_path/'a.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0];m=mapping(job);m['links'][0]['quote']='SQL'
 root=tmp_path/'packs'
 with pytest.raises(ValueError):prepare_pack(s,job['id'],root,evidence_mapping=m)
 assert not root.exists()


def test_no_network_or_candidate_store_writes(monkeypatch,tmp_path):
 import socket
 monkeypatch.setattr(socket,'create_connection',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No network')))
 s=Store(tmp_path/'a.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0]
 with s.connect() as db:before='\n'.join(db.iterdump())
 pr=preview(job,s.profile());d=cover_draft(job,s.profile(),mapping(job));assert d['validation_report']['valid']
 with s.connect() as db:assert '\n'.join(db.iterdump())==before


def test_http_preview_csrf_exact_mapping_and_private_profile(web):
 s,_=web;s.ingest([JOB]);job=s.jobs()[0];path='/api/cover-evidence?id='+job['id']
 status,_,raw=request(web,'GET',path);assert status==200;pr=json.loads(raw);assert pr['facts'][0]['text']==PROFILE['facts'][0]['text']
 m=mapping(job);payload={'id':job['id'],'evidence_mapping':m}
 assert request(web,'POST','/api/pack',payload)[0]==403
 status,_,raw=request(web,'POST','/api/pack',payload,{'X-JobHunter-Token':token(web)});assert status==200
 result=json.loads(raw);assert result['validation_report']['relevance']['status']=='user_attested'
 m['links'][0]['reason']=''
 assert request(web,'POST','/api/pack',payload,{'X-JobHunter-Token':token(web)})[0]==400
 assert request(web,'GET','/evidence-mapping.js')[0]==200
 assert b'evidence-mapping' in request(web,'GET','/')[2]


def test_pack_mapping_tamper_and_selected_evidence_rebinding_blocked(tmp_path):
 from jobhunter_app.pack_management import digest
 s=Store(tmp_path/'a.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0];d=prepare_pack(s,job['id'],tmp_path/'packs',evidence_mapping=mapping(job));folder=Path(d['directory'])
 meta=folder/'preparation.json';data=json.loads(meta.read_text());data['cover']['evidence_mapping']['links'][0]['reason']='Changed explanation';meta.write_text(json.dumps(data));manifest=folder/'pack.json';v=json.loads(manifest.read_text());v['artifacts']['preparation.json']=sha256(meta.read_bytes()).hexdigest();manifest.write_text(json.dumps(v))
 assert not inspect_pack(s,tmp_path/'packs',d['version_id'])['valid']


@pytest.mark.parametrize('raw',[b'x',b'null',b'[]',b'['*2000,b'\xff',b' '*65537])
def test_cli_json_file_failures_bounded(tmp_path,raw):
 from jobhunter_app.evidence_mapping import load
 path=tmp_path/'mapping.json';path.write_bytes(raw)
 with pytest.raises(ValueError):load(path)


def test_cli_loader_bom_and_no_execution(tmp_path):
 from jobhunter_app.evidence_mapping import load
 path=tmp_path/'mapping.json';m=mapping(reason='file:///tmp/private <script>no execution</script>');path.write_text(json.dumps(m),encoding='utf-8-sig');assert load(path)==m


def test_explicit_negative_or_ambiguous_text_is_not_automatically_endorsed():
 job={**JOB,'description':'Python not required.'};d=cover_draft(job,PROFILE,mapping(job,quote=job['description']))
 assert d['validation_report']['valid'] and 'negated or ambiguous' in d['relevance']['notice']
 assert d['relevance']['status']=='user_attested' # No semantic requirement or eligibility inference.


def test_changed_unselected_fact_stales_whole_preview():
 p={**PROFILE,'facts':PROFILE['facts']+[{'text':'Other fact','source':'Synthetic','verified':True}]};m=mapping(profile=p);p['facts'][1]['source']='changed'
 with pytest.raises(ValueError,match='preview changed'):resolve(JOB,p,m)


def test_legacy_writer_explicit_mapping_and_zero_overlap_rejection(tmp_path):
 import yaml
 from agents.cover_letter import CoverLetterWriter
 p={**PROFILE,'facts':[{'text':'I coordinated a workshop.','source':'Synthetic record','verified':True}]}
 cfg=tmp_path/'p.yml';cfg.write_text(yaml.safe_dump({'candidate':{'full_name':p['name']},'verified_facts':p['facts']}));writer=CoverLetterWriter(output_dir=tmp_path/'drafts',profile_path=cfg)
 assert not writer.generate(JOB)['success'] and not (tmp_path/'drafts').exists()
 d=writer.generate(JOB,evidence_mapping=mapping(profile=p));assert d['success'] and d['relevance']['status']=='user_attested'
 side=json.loads(Path(d['output_path']).with_suffix('.evidence.json').read_text());assert side['evidence_mapping']==mapping(profile=p)


def test_mapping_reason_edit_changes_inspection_binding_even_same_cover(tmp_path):
 s=Store(tmp_path/'a.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0];m=mapping(job);a=prepare_pack(s,job['id'],tmp_path/'packs',evidence_mapping=m)
 m['links'][0]['reason']='Another personal explanation';b=prepare_pack(s,job['id'],tmp_path/'packs',evidence_mapping=m)
 assert a['version_id']!=b['version_id'] and (Path(a['directory'])/'cover-letter-draft.txt').read_bytes()==(Path(b['directory'])/'cover-letter-draft.txt').read_bytes()
 assert a['validation_report']['bindings']['contract_sha256']!=b['validation_report']['bindings']['contract_sha256']


def test_explicit_null_map_http_never_falls_back(web):
 s,_=web;s.ingest([JOB]);job=s.jobs()[0]
 assert request(web,'POST','/api/pack',{'id':job['id'],'evidence_mapping':None},{'X-JobHunter-Token':token(web)})[0]==400
