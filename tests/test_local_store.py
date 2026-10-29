"""Isolated local workflow tests. No original candidate data or live APIs."""
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import pytest
from jobhunter_app.store import Store, STATES
from jobhunter_app.intake import parse_jobs, export_jobs
from jobhunter_app.validation import normalize_job, public_url, validate_ai_evaluation
from jobhunter_app.matching import contains, match_job, keyword_recommendations
from jobhunter_app.documents import cover_draft, prepare_pack, validate_cover
from jobhunter_app.migration import migrate

JOB = {'title': 'Python Developer', 'company': 'Example', 'url': 'https://example.com/jobs/1', 'description': 'Python and SQL; communication preferred.'}
PROFILE = {'name': 'Test Candidate', 'skills': ['Python'], 'facts': [{'text': 'I built a Python project.', 'source': 'User project record', 'verified': True}]}

@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path/'app.sqlite3')
    s.save_profile(PROFILE)
    return s


def test_schema_and_integrity(store):
    with store.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_refuses_newer_schema(tmp_path):
    path=tmp_path/'new.sqlite3'
    with sqlite3.connect(path) as db: db.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError): Store(path)


def test_intake_preview_idempotence_and_provenance(store):
    assert store.ingest([JOB], dry_run=True)['inserted'] == 1
    assert store.summary()['total_jobs'] == 0
    store.ingest([JOB], source='one')
    assert store.ingest([{**JOB, 'url': JOB['url']+'?utm_source=x#fragment'}], source='two')['updated']==1
    assert store.summary()['total_jobs']==1
    with store.connect() as db: assert db.execute('SELECT COUNT(*) FROM sightings').fetchone()[0]==2


def test_partial_import_and_no_description_loss(store):
    r=store.ingest([JOB, {'title': 'Invalid'}])
    assert (r['inserted'],r['invalid'])==(1,1)
    store.ingest([{**JOB,'description':''}])
    assert store.jobs()[0]['description']==JOB['description']


def test_same_title_different_location_not_merged(store):
    store.ingest([JOB,{**JOB,'url':'https://example.com/jobs/2','location':'Berlin'}])
    assert store.summary()['total_jobs']==2


def test_duplicate_rows_in_preview(store):
    r=store.ingest([JOB,JOB],dry_run=True)
    assert (r['inserted'],r['updated'])==(1,1)


def test_matching_scoping_and_invalidation(store):
    store.ingest([JOB]);store.evaluate()
    assert store.jobs()[0]['match']['score_percent']==100
    store.save_profile({'name':'Other','skills':['Rust'],'facts':[]},'other');store.evaluate('other')
    assert store.jobs(profile_id='other')[0]['match']['score_percent']==0
    store.save_profile({**PROFILE,'skills':['SQL']})
    assert store.jobs()[0]['match'] is None
    assert store.jobs(profile_id='other')[0]['match'] is not None


def test_updates_invalidate_matches(store):
    store.ingest([JOB]);store.evaluate();store.ingest([{**JOB,'description':'SQL only'}])
    assert store.jobs()[0]['match'] is None


def test_application_history_idempotent_and_scoped(store):
    store.ingest([JOB]);job_id=store.jobs()[0]['id']
    store.set_status(job_id,'saved',notes='note',deadline='2026-12-01')
    store.set_status(job_id,'saved',notes='updated note')
    store.set_status(job_id,'applied')
    with store.connect() as db: assert db.execute('SELECT COUNT(*) FROM status_history').fetchone()[0]==2
    assert store.summary()['status_counts']['applied']==1
    store.save_profile({'name':'Other'},'other')
    assert store.jobs(profile_id='other')[0]['status']=='discovered'

@pytest.mark.parametrize('status',STATES)
def test_valid_statuses(store,status):
    store.ingest([JOB]);store.set_status(store.jobs()[0]['id'],status)
    assert store.jobs()[0]['status']==status


def test_invalid_application_is_atomic(store):
    store.ingest([JOB]);job_id=store.jobs()[0]['id']
    with pytest.raises(ValueError): store.set_status(job_id,'nonsense')
    with pytest.raises(ValueError): store.set_status(job_id,'saved',deadline='tomorrow')
    with pytest.raises(sqlite3.IntegrityError): store.set_status('missing','saved')
    assert store.jobs()[0]['status']=='discovered'


def test_concurrent_intake(store):
    def ingest(i): return store.ingest([{**JOB,'url':f'https://example.com/jobs/{i}'}])
    with ThreadPoolExecutor(max_workers=6) as ex: list(ex.map(ingest,range(30)))
    assert store.summary()['total_jobs']==30


def test_backup_reopen_and_no_overwrite(store,tmp_path):
    store.ingest([JOB]);path=tmp_path/'backup.sqlite3';store.backup(path)
    assert Store(path).summary()['total_jobs']==1
    with pytest.raises(ValueError):store.backup(path)
    with pytest.raises(ValueError):store.backup(store.path)

@pytest.mark.parametrize('value',['file:///etc/passwd','javascript:alert(1)','http://localhost/a','https://127.0.0.1/a','http://10.0.0.1/a','http://169.254.169.254/a','http://[::1]/a','https://user:secret@example.com/a','https://example.com:9443/a','https://example.com/\nheader','https://example.com:wrong/a',''])
def test_unsafe_url_rejected(value):
    with pytest.raises(ValueError):public_url(value)

@pytest.mark.parametrize('field,value',[('title',''),('company',None),('description',{}),('title','x'*301),('url',None)])
def test_malformed_job_rejected(field,value):
    with pytest.raises(ValueError):normalize_job({**JOB,field:value})

@pytest.mark.parametrize('profile',[{'skills':'Python'},{'skills':[False]},{'skills':['']},{'facts':[{'text':'claim','verified':'true','source':'x'}]},{'facts':[{'text':'claim','verified':True}]},{'name':False},{'original_cv':False},{'unexpected':'x'}])
def test_profile_validation(store,profile):
    with pytest.raises(ValueError):store.save_profile(profile)
    assert store.profile()==PROFILE


def test_no_skills_no_fake_score():
    assert match_job(JOB, {})['score_percent'] is None
    assert match_job(JOB, {})['eligibility']=='needs_review'


def test_multilingual_and_token_boundaries():
    k=keyword_recommendations('تعلم الآلة and Datenanalyse plus Python','Python')
    assert 'Machine learning' in k['observed'] and 'Data analysis' in k['observed']
    assert k['supported']==['Python']
    assert not contains('JavaScript','Java')
    assert contains('Need C++ experience','C++')


def test_learning_denominator(store):
    store.ingest([JOB,{**JOB,'url':'https://example.com/2','title':'Senior Python'}])
    store.save_profile({**PROFILE,'excluded_title_terms':['senior']});store.evaluate()
    learning=store.learning()
    assert learning['vacancies_reviewed']==1
    assert any(x['skill']=='SQL' and x['vacancies']==1 for x in learning['priorities'])

@pytest.mark.parametrize('format,payload',[('json',json.dumps([JOB]).encode()),('jsonl',(json.dumps(JOB)+'\n').encode()),('csv',b'title,company,url\nDeveloper,Example,https://example.com/1\n')])
def test_parsers(format,payload):
    assert len(parse_jobs(payload,format))==1

@pytest.mark.parametrize('format,payload',[('pickle',b'xx'),('json',b'{}'),('json',b'invalid'),('jsonl',b'{'),('json',b' '* (10*1024*1024+1))])
def test_invalid_import(format,payload):
    with pytest.raises(ValueError):parse_jobs(payload,format)


def test_csv_formula_and_json_export(store):
    store.ingest([{**JOB,'title':'=HYPERLINK("bad")'}])
    rows=list(csv.DictReader(io.StringIO(export_jobs(store,'csv').decode('utf-8-sig'))))
    assert rows[0]['title'].startswith("'=")
    assert json.loads(export_jobs(store))[0]['title'].startswith('=')


def test_export_is_not_silently_truncated(store):
    store.ingest([{**JOB,'url':f'https://example.com/{i}'} for i in range(1001)])
    assert len(json.loads(export_jobs(store)))==1001


def test_cover_grounded_and_untrusted_fact_excluded():
    p={**PROFILE,'facts':PROFILE['facts']+[{'text':'I invented an award.','verified':False,'source':'unknown'}]}
    d=cover_draft(JOB,p)
    assert 'I built a Python project.' in d['content']
    assert 'award' not in d['content']
    assert d['review_required'] is True
    assert validate_cover(d['content'],JOB,p,['unsupported claim'])

@pytest.mark.parametrize('profile',[{}, {'name':'Test'}, {'name':'Test','facts':[{'text':'x','verified':False,'source':'x'}]}])
def test_cover_refuses_missing_evidence(profile):
    with pytest.raises(ValueError):cover_draft(JOB,profile)


def test_cover_word_limit():
    p={**PROFILE,'facts':[{'text':'word '*400,'source':'test','verified':True}]}
    with pytest.raises(ValueError):cover_draft(JOB,p)


def test_pack_original_cv_unchanged(store,tmp_path):
    original=tmp_path/'original.pdf';original.write_bytes(b'%PDF-original candidate bytes')
    store.save_profile({**PROFILE,'original_cv':str(original)});store.ingest([JOB])
    data=prepare_pack(store,store.jobs()[0]['id'],tmp_path/'packs')
    assert (Path(data['directory'])/'original-cv.pdf').read_bytes()==original.read_bytes()
    assert data['original_cv']['unchanged'] is True


def test_pack_invalid_original_rolls_back(store,tmp_path):
    original=tmp_path/'original.pdf';original.write_text('not a pdf')
    store.save_profile({**PROFILE,'original_cv':str(original)});store.ingest([JOB])
    with pytest.raises(ValueError):prepare_pack(store,store.jobs()[0]['id'],tmp_path/'packs')
    assert list((tmp_path/'packs').iterdir())==[]


def test_migration_preview_backup_idempotence(store,tmp_path):
    legacy=tmp_path/'legacy';legacy.mkdir();path=legacy/'evaluations.json';path.write_text(json.dumps([JOB]))
    original=path.read_bytes();preview=migrate(store,legacy)
    assert preview['preview']['inserted']==1 and store.summary()['total_jobs']==0
    applied=migrate(store,legacy,dry_run=False)
    assert (Path(applied['backup'])/'evaluations.json').read_bytes()==original
    assert path.read_bytes()==original
    assert migrate(store,legacy,dry_run=False)['result']['updated']==1
    assert store.summary()['total_jobs']==1


def test_migration_invalid_data_never_applies(store,tmp_path):
    p=tmp_path/'legacy';p.mkdir();(p/'evaluations.json').write_text('broken')
    assert migrate(store,p)['file_errors']
    with pytest.raises(ValueError):migrate(store,p,dry_run=False)
    assert store.summary()['total_jobs']==0


def test_rejects_invalid_ai_output():
    good={'global_score':4,'scores':{k:4 for k in ['skills_match','education_match','location','language','growth']},'recommendation':'apply','match_highlights':[],'gaps':[],'reasoning':'evidence','german_level_required':'none'}
    assert validate_ai_evaluation(good)
    for value in [True, float('nan'),float('inf'),9,'4',None]:
        assert not validate_ai_evaluation({**good,'global_score':value})
    assert not validate_ai_evaluation({'global_score':4})
    assert not validate_ai_evaluation([good])
