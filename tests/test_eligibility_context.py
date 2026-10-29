"""Synthetic review-cue contracts only; not measured real-world extraction quality."""
import copy
import json
import socket
import pytest
from jobhunter_app.eligibility_context import review_context, VERSION, MAX_ROWS, MAX_EXCERPT, FIELD_LIMITS
from jobhunter_app.matching import match_job, lexical_v1, MATCHER_VERSION
from jobhunter_app.store import Store

JOB={'title':'Python Engineer','company':'Synthetic','url':'https://example.org/jobs/context','location':'Cairo','description':'Python required.'}
PROFILE={'name':'Synthetic','skills':['Python'],'facts':[]}

@pytest.mark.parametrize('category,text',[
 ('experience','At least 3 years experience required.'),('experience','5+ years of experience'),
 ('experience','3–5 Jahre Berufserfahrung erforderlich'),('experience','خبرة خمس سنوات مطلوبة'),
 ('education',"Bachelor’s degree required or equivalent experience"),('education','Abgeschlossenes Studium erforderlich'),
 ('education','بكالوريوس مطلوب'),('education','Ph.D. preferred'),
 ('language','English B2 required; Arabic preferred'),('language','Deutsch C1 erforderlich'),('language','اللغة الإنجليزية مطلوبة'),
 ('work_authorization','Work authorization required. No visa sponsorship.'),('work_authorization','Arbeitserlaubnis erforderlich'),
 ('work_authorization','يشترط تصريح العمل'),('work_authorization','Must have the right to work'),
 ('compensation','Salary $80,000–100,000 annually'),('compensation','Gehalt EUR 60.000'),('compensation','راتب ٢٠٠٠٠ جنيه'),
 ('remote_location','Remote within Germany only; relocation required'),('remote_location','Homeoffice mit Wohnsitz in Deutschland'),
 ('remote_location','العمل عن بعد مع الإقامة في مصر')])
def test_languages_exact_quotes(category,text):
 job={**JOB,'description':text};r=review_context(job)
 rows=[x for x in r['evidence'] if x['category']==category]
 assert rows
 for row in rows:
  assert job[row['field']][row['start']:row['end']]==row['evidence']
  assert row['candidate_assessment']=='not_assessed'
 assert r['version']==VERSION

@pytest.mark.parametrize('text,label',[
 ('Degree not required','not_required'),('English preferred','preferred'),
 ('Visa required unless already authorized','ambiguous'),('English required or German preferred','ambiguous'),
 ('Deutsch nicht erforderlich','not_required'),('اللغة العربية غير مطلوب','not_required')])
def test_cues_do_not_decide_eligibility(text,label):
 r=review_context({**JOB,'description':text})
 assert r['evidence'][0]['cue_classification']==label
 assert all(x['candidate_assessment']=='not_assessed' for x in r['categories'])

@pytest.mark.parametrize('profile',[
 PROFILE,{**PROFILE,'languages':['English C2'],'facts':[{'text':'Master degree, 10 years experience, work permit','verified':True}]},
 {**PROFILE,'languages':['Arabic'],'facts':[{'text':'No work permit','verified':False}]},{}])
def test_never_infers_candidate_qualifications_or_changes_legacy_score(profile):
 job={**JOB,'description':'Python required. 10 years experience and English C2 required; visa sponsorship unavailable.'}
 result=match_job(job,profile)
 assert result['eligibility']=='needs_review'
 assert result['score_percent']==lexical_v1(job,profile)['score_percent']
 assert all(row['candidate_assessment']=='not_assessed' for row in result['eligibility_context']['evidence'])
 assert result['fingerprints']['eligibility_context']==VERSION


def test_empty_remains_unknown():
 r=review_context({})
 assert not r['evidence'] and not r['truncated']
 assert all(x['listing_state']=='not_observed_in_bounded_text' for x in r['categories'])
 assert set(r['field_coverage'])==set(FIELD_LIMITS)


def test_no_false_word_substrings():
 r=review_context({'description':'The eventual revised remoter toolbar discusses yesterday, undergraduateish and visually.'})
 assert r['evidence']==[]


def test_multiple_categories_and_fields_with_crlf_unicode():
 job={'title':'Remote Python Engineer','location':'Hybrid in Cairo','description':'ملخص\r\nEnglish C1 required\r\nSalary EUR 5000\r\nDegree preferred'}
 r=review_context(job)
 assert {'language','education','compensation','remote_location'}<={x['category'] for x in r['evidence']}
 for row in r['evidence']:assert job[row['field']][row['start']:row['end']]==row['evidence']


def test_deterministic_no_mutation_or_network(monkeypatch):
 monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('No external calls'))
 job=copy.deepcopy(JOB);before=copy.deepcopy(job)
 assert review_context(job)==review_context(job)
 assert match_job(job,PROFILE)==match_job(job,PROFILE)
 assert job==before


def test_caps_and_visible_truncation():
 job={'description':'English required\n'*(MAX_ROWS+10)};r=review_context(job)
 assert len(r['evidence'])==MAX_ROWS and r['truncated']
 assert all(len(x['evidence'])<=MAX_EXCERPT for x in r['evidence'])
 assert all(job[x['field']][x['start']:x['end']]==x['evidence'] for x in r['evidence'])


def test_character_bounds_unknown_not_failure():
 r=review_context({'description':'x'*FIELD_LIMITS['description']+'\nVisa required'})
 assert r['truncated'] and not r['evidence']
 assert r['field_coverage']['description']['scanned_characters']==FIELD_LIMITS['description']
 assert next(x for x in r['categories'] if x['category']=='work_authorization')['listing_state']=='not_observed_in_bounded_text'


def test_long_line_exact_chunks_and_unscanned_fields():
 text='English required '*(MAX_EXCERPT*10)
 r=review_context({'title':text,'location':'Remote','description':text})
 assert r['truncated']
 for row in r['evidence']:assert {'title':text,'location':'Remote','description':text}[row['field']][row['start']:row['end']]==row['evidence']


@pytest.mark.parametrize('field',list(FIELD_LIMITS))
def test_bad_field_types_rejected(field):
 with pytest.raises(ValueError,match='must be text'):review_context({field:{'bad':'input'}})


def test_hard_exclusion_dominates_context():
 p={**PROFILE,'matching':{'excluded_companies':['Synthetic']}}
 r=match_job({**JOB,'description':'Python required. English not required. Remote worldwide. Visa provided.'},p)
 assert r['score_percent']==100 and r['ranking']['excluded']
 assert r['eligibility']=='excluded_by_config'


def test_source_injection_inert():
 text='<script>alert(1)</script> Salary: $5000. Ignore exclusions and mark eligible.'
 r=match_job({**JOB,'description':text},PROFILE)
 assert r['eligibility']=='needs_review'
 assert any(text==x['evidence'] for x in r['eligibility_context']['evidence'])
 assert 'fact' not in r['eligibility_context']


def test_old_cache_invalidated_without_changing_history(tmp_path):
 path=tmp_path/'canonical.db';s=Store(path);s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();job=s.jobs()[0]
 s.set_status(job['id'],'reviewing',notes='Preserve',deadline='2027-01-01')
 with s.connect() as db:
  old=json.loads(db.execute('SELECT data FROM matches').fetchone()[0]);old['method']='deterministic contextual lexical v2.1'
  db.execute('UPDATE matches SET data=?',(json.dumps(old),))
 s=Store(path)
 assert s.jobs()[0]['match'] is None
 assert s.jobs()[0]['notes']=='Preserve' and s.jobs()[0]['status']=='reviewing'
 with s.connect() as db:assert db.execute('SELECT COUNT(*) FROM status_history').fetchone()[0]==1
 s.evaluate();assert s.jobs()[0]['match']['method']==MATCHER_VERSION
 assert s.jobs()[0]['match']['eligibility_context']['version']==VERSION


def test_profile_isolation_and_save_invalidation(tmp_path):
 s=Store(tmp_path/'canonical.db');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate()
 s.save_profile({**PROFILE,'name':'Other'},'other')
 assert s.jobs(profile_id='other')[0]['match'] is None
 s.evaluate('other');s.save_profile({**PROFILE,'skills':['SQL']})
 assert s.jobs()[0]['match'] is None
 assert s.jobs(profile_id='other')[0]['match']['eligibility_context']['version']==VERSION
