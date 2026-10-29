"""P6-VAL: supported-contract checks, not an arbitrary prose or truth checker."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import pytest
import yaml
from jobhunter_app.documents import cover_draft,validate_cover,validate_cover_report,prepare_pack,VALIDATOR_VERSION
from jobhunter_app.store import Store
from agents.cover_letter import CoverLetterWriter
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request,token


def report(content=None,job=None,profile=None,facts=None):
    return validate_cover_report(content if content is not None else cover_draft(JOB,PROFILE)['content'],
                                 JOB if job is None else job,PROFILE if profile is None else profile,
                                 [PROFILE['facts'][0]['text']] if facts is None else facts)


def test_explicit_success_checks_and_hash_binding():
    d=cover_draft(JOB,PROFILE);v=d['validation_report']
    assert v==report() and v['valid'] and v['validator']==VALIDATOR_VERSION
    assert {x['id'] for x in v['checks']}=={'candidate_identity','application_target','selected_evidence','exact_quotations','supported_template','word_limit','target_context','evidence_relevance'}
    assert all(x['passed'] for x in v['checks']) and v['issues']==[]
    assert v['review_required'] and 'not independent' in v['truth_status']
    assert v['bindings']['content_sha256']==sha256(d['content'].encode()).hexdigest()
    assert v['bindings']['selected_count']==1 and validate_cover(d['content'],JOB,PROFILE,[PROFILE['facts'][0]['text']])==[]


@pytest.mark.parametrize('edit',[
    lambda x:x+'\nI have a doctorate.',lambda x:'I have a doctorate.\n'+x,
    lambda x:x.replace('Kind regards,','I have ten years of experience.\nKind regards,'),
    lambda x:x.replace('The following source-backed examples','I led a team. The following source-backed examples'),
    lambda x:x.replace('I am applying for the','I am not applying for the'),
    lambda x:x.replace('I am applying for the','I am applying for a different role, not the'),
    lambda x:x.replace(JOB['title'],'Wrong role',1)+'\n'+JOB['title'],
    lambda x:x.replace(JOB['company'],'Wrong employer',1)+'\n'+JOB['company'],
    lambda x:x.replace(PROFILE['name'],'Wrong candidate'),
    lambda x:x.replace('I built a Python project.','I built a SQL project.'),
    lambda x:x.replace('“','"').replace('”','"'),
    lambda x:x+' ',lambda x:x.replace('\n','\r\n'),lambda x:'',
])
def test_reject_any_unvalidated_prose_or_format_edit(edit):
    v=report(edit(cover_draft(JOB,PROFILE)['content']))
    assert not v['valid'] and v['issues'] and v['bindings'] is None
    assert not next(c for c in v['checks'] if c['id']=='supported_template')['passed']


@pytest.mark.parametrize('facts',[[],None,'text',{},[None],[{}],[['x']],['not attested'],[PROFILE['facts'][0]['text']]*2,[PROFILE['facts'][0]['text']]*4])
def test_fail_closed_selection(facts):
    v=validate_cover_report(cover_draft(JOB,PROFILE)['content'],JOB,PROFILE,facts)
    assert not v['valid'] and v['bindings'] is None
    assert not next(c for c in v['checks'] if c['id']=='selected_evidence')['passed']


@pytest.mark.parametrize('bad',[None,False,1,[],{},'',' ','\nadded claim','Candidate\rX','A\u2028B','A\u2029B','A\u202eB','A\x00B','A\ud800'])
@pytest.mark.parametrize('field',['name','title','company'])
def test_reject_invalid_candidate_or_target_labels(field,bad):
    p=deepcopy(PROFILE);j=deepcopy(JOB)
    (p if field=='name' else j)[field]=bad
    assert not report(job=j,profile=p)['valid']
    with pytest.raises(ValueError):cover_draft(j,p)


@pytest.mark.parametrize('change',[
    {'verified':False},{'verified':'true'},{'verified':1},{'source':''},{'source':' '},
    {'source':None},{'source':[]},{'text':''},{'text':' '},{'text':None},{'text':['x']},
    {'text':'x\x00y'},{'source':'source\ud800'}])
def test_invalid_or_revoked_facts_cannot_authorize_claim(change):
    p=deepcopy(PROFILE);p['facts'][0].update(change)
    assert not report(profile=p)['valid']
    with pytest.raises(ValueError):cover_draft(JOB,p)


@pytest.mark.parametrize('value',[None,[],{},False,42])
def test_malformed_top_level_objects_fail_closed(value):
    for j,p in [(value,PROFILE),(JOB,value)]:
        v=validate_cover_report('text',j,p,[])
        assert not v['valid'] and v['bindings'] is None
        with pytest.raises(ValueError):cover_draft(j,p)


@pytest.mark.parametrize('content',[None,False,{},[],42])
def test_nontext_content_reports_issues(content):
    v=validate_cover_report(content,JOB,PROFILE,[PROFILE['facts'][0]['text']])
    assert not v['valid'] and v['bindings'] is None


def test_exact_unicode_markup_quotes_and_multiline_evidence():
    p={'name':'Synthetic Zoë أحمد','facts':[{'text':'I built “Python” <script>not executable</script>.\nZweite Zeile: تطبيق.','source':'Synthetic «record»\nPage 2','verified':True}]}
    j={**JOB,'title':'Développeur «Python»','company':'شركة & <example>'}
    d=cover_draft(j,p);assert d['evidence']==p['facts'] and p['facts'][0]['text'] in d['content']
    assert d==cover_draft(j,p) and d['validation_report']['valid']
    assert not validate_cover(d['content'],j,p,[p['facts'][0]['text']])


def test_three_distinct_facts_stable_ranking_and_binding():
    p=deepcopy(PROFILE)
    p['facts']=[{'text':f'I built Python example {i}.','source':f'Synthetic source {i}','verified':True} for i in range(4)]
    p['facts'].insert(1,{**p['facts'][0],'source':'Second source for same text'})
    d=cover_draft(JOB,p)
    assert [x['text'] for x in d['evidence']]==[f'I built Python example {i}.' for i in range(3)]
    assert d['evidence'][0]['source']=='Synthetic source 0'
    assert d['validation_report']['bindings']['selected_count']==3


@pytest.mark.parametrize('field',['source','name','url','description','text'])
def test_bindings_change_when_bound_input_changes(field):
    p=deepcopy(PROFILE);j=deepcopy(JOB);before=cover_draft(j,p)
    if field in ('source','text'):p['facts'][0][field]+=' changed'
    elif field=='name':p['name']+=' changed'
    else:j[field]=j.get(field,'')+' changed'
    after=cover_draft(j,p)
    assert before['validation_report']['bindings']['contract_sha256']!=after['validation_report']['bindings']['contract_sha256']
    if field in ('source','url','description'):assert before['content']==after['content']
    # A changed source alone is still user attestation, not automatically false.
    assert after['validation_report']['valid']


@pytest.mark.parametrize('field',['url','description'])
@pytest.mark.parametrize('bad',[None,{},False,'surrogate\ud800'])
def test_invalid_optional_target_context_never_bound(field,bad):
    j={**JOB,field:bad};v=report(job=j)
    assert not v['valid'] and v['bindings'] is None
    with pytest.raises(ValueError):cover_draft(j,PROFILE)


def test_word_limit_boundary():
    base=cover_draft(JOB,PROFILE)['word_count']-len(PROFILE['facts'][0]['text'].split())
    def p(n):return {**PROFILE,'facts':[{'text':' '.join(['Python']+['word']*(n-1)),'source':'Synthetic','verified':True}]}
    assert cover_draft(JOB,p(350-base))['word_count']==350
    with pytest.raises(ValueError,match='350'):cover_draft(JOB,p(351-base))


def test_pack_report_and_failure_no_output_or_original_edit(tmp_path):
    s=Store(tmp_path/'synthetic.sqlite3');original=tmp_path/'original.pdf';original.write_bytes(b'%PDF-1.4\nSYNTHETIC OPAQUE BYTES')
    p={**PROFILE,'original_cv':str(original)};s.save_profile(p);s.ingest([JOB]);job=s.jobs()[0];before=original.read_bytes()
    result=prepare_pack(s,job['id'],tmp_path/'packs');folder=Path(result['directory']);side=json.loads((folder/'preparation.json').read_text())
    assert result['validation_report']==side['cover']['validation_report']
    assert side['cover']['validation_report']['bindings']['content_sha256']==sha256((folder/'cover-letter-draft.txt').read_bytes()).hexdigest()
    assert (folder/'original-cv.pdf').read_bytes()==original.read_bytes()==before
    s.save_profile({**p,'name':'Synthetic\nInjected claim'});blocked=tmp_path/'blocked'
    with pytest.raises(ValueError):prepare_pack(s,job['id'],blocked)
    assert not blocked.exists() and original.read_bytes()==before


def test_legacy_writer_report_and_rejection(tmp_path):
    cfg=tmp_path/'synthetic.yml';cfg.write_text(yaml.safe_dump({'candidate':{'full_name':PROFILE['name']},'verified_facts':PROFILE['facts']}))
    writer=CoverLetterWriter(output_dir=tmp_path/'out',profile_path=cfg);d=writer.generate(JOB)
    assert d['success'] and d['model_used']=='local-grounded-template'
    side=json.loads(Path(d['output_path']).with_suffix('.evidence.json').read_text())
    assert side['validation_report']['valid'] and side['review_required']
    assert not writer.generate({**JOB,'company':'Wrong\nInjected claim'})['success']


def test_http_pack_exposes_valid_report_and_blocks_invalid_profile(web):
    s,_=web;s.ingest([JOB]);job=s.jobs()[0];headers={'X-JobHunter-Token':token(web)}
    status,_,raw=request(web,'POST','/api/pack',{'id':job['id']},headers)
    assert status==200 and json.loads(raw)['validation_report']['valid']
    root=Path(json.loads(raw)['directory']).parent;before=list(root.iterdir())
    s.save_profile({**PROFILE,'name':'Synthetic\nInjected claim'})
    assert request(web,'POST','/api/pack',{'id':job['id']},headers)[0]==400
    assert list(root.iterdir())==before


def test_cli_pack_report_and_rejection(tmp_path):
    root=Path(__file__).resolve().parents[1];db=tmp_path/'cli.sqlite3';s=Store(db);s.save_profile(PROFILE);s.ingest([JOB]);job=s.jobs()[0]
    args=[sys.executable,str(root/'run_local.py'),'--db',str(db),'pack',job['id'],'--output',str(tmp_path/'packs')]
    done=subprocess.run(args,cwd=root,text=True,capture_output=True,timeout=30)
    assert done.returncode==0,done.stderr
    data=json.loads(done.stdout);assert data['review_required'] and data['validation_report']['valid']
    s.save_profile({**PROFILE,'facts':[]});again=subprocess.run(args,cwd=root,text=True,capture_output=True,timeout=30)
    assert again.returncode==2 and len(list((tmp_path/'packs').iterdir()))==1
