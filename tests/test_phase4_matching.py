"""Reviewed synthetic clauses; no real vacancy/candidate or model/network call."""
import copy
import json
import math
import pytest
from jobhunter_app.matching import match_job,contains,MATCHER_VERSION,keyword_recommendations
from jobhunter_app.requirements import extract
from jobhunter_app.store import Store

JOB={'title':'Python Engineer','company':'Fixture Co','url':'https://example.org/jobs/phase4','description':'Python required; SQL preferred.','location':'Cairo'}
PROFILE={'name':'Synthetic QA','skills':['Python'],'facts':[]}

@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'test.db');s.save_profile(PROFILE);return s

@pytest.mark.parametrize('text,label',[
 ('Python required','required'),('Python mandatory','required'),('Python preferred','preferred'),
 ('Python is optional','preferred'),('Python not required','not_required'),('No Python experience required','not_required'),
 ('Python required and SQL preferred','ambiguous'),('No Python required, SQL required','ambiguous'),
 ('Python erforderlich','required'),('Python wünschenswert','preferred'),('Python nicht erforderlich','not_required'),
 ('Keine Python Kenntnisse erforderlich','not_required'),('Python ist zwingend erforderlich','required'),
 ('Python مطلوب','required'),('يفضل Python','preferred'),('Python غير مطلوب','not_required'),
 ('لا يشترط Python','not_required'),('Python مطلوب ويفضل SQL','ambiguous'),('We use Python','mentioned'),
])
def test_context_classification_exact_evidence(text,label):
    row=extract(text,PROFILE)[0];assert row['classification']==label
    assert text[row['start']:row['end']]==row['evidence']
    assert row['candidate_evidence']=='declared_skill'

def test_distinct_clauses_and_not_recorded():
    rows=extract('Python required; SQL preferred. Docker not required.',PROFILE)
    assert [(x['skill'],x['classification']) for x in rows]==[('Python','required'),('SQL','preferred'),('Docker','not_required')]
    assert rows[1]['candidate_evidence']=='not_recorded'

@pytest.mark.parametrize('header',['Requirements:','Anforderungen:','المتطلبات:'])
def test_heading_bullets_and_reset(header):
    text=header+'\n- Python\n- SQL\n\nDocker'
    rows=extract(text,PROFILE)
    assert [x['classification'] for x in rows]==['required','required','mentioned']
    assert all(text[x['start']:x['end']]==x['evidence'] for x in rows)

def test_verified_fact_mention_not_unverified_claim():
    p={**PROFILE,'skills':[],'facts':[{'text':'SQL project','source':'Synthetic','verified':True},{'text':'Docker','source':'Synthetic','verified':False}]}
    rows=extract('SQL required; Docker required',p)
    assert [x['candidate_evidence'] for x in rows]==['verified_fact_mention','not_recorded']

def test_keyword_typescript_not_javascript():
    assert keyword_recommendations('TypeScript','TypeScript')['observed']==['TypeScript']
    assert not contains('JavaScript','Java')

def test_ranking_weights_and_legacy_denominator():
    p={**PROFILE,'skills':['Python','SQL'],'matching':{'skill_weights':{'Python':3,'SQL':1},'preferred_title_terms':['engineer'],'preferred_location_terms':['Berlin'],'weights':{'skills':60,'title':30,'location':10}}}
    r=match_job({**JOB,'description':'Python required'},p)
    assert r['score_percent']==50 # Retained lexical count, not weighted ranking.
    assert r['ranking']['score_percent']==75 # .75*60 + 1*30 + 0*10
    assert r['ranking']['weight_denominator']==100
    assert r['eligibility']=='needs_review' and r['method']==MATCHER_VERSION

@pytest.mark.parametrize('matching',[
 {'excluded_companies':['fixture co']},{'excluded_location_terms':['Cairo']},
])
def test_hard_exclusion_beats_perfect_ranking(matching):
    r=match_job(JOB,{**PROFILE,'matching':matching})
    assert r['ranking']['score_percent']==100 and r['ranking']['excluded']
    assert r['eligibility']=='excluded_by_config' and r['exclusion_evidence']
    assert any(x['state']=='exclude' and x['evidence'] for x in r['hard_constraint_checks'])

def test_legacy_title_exclusion_retained():
    r=match_job(JOB,{**PROFILE,'excluded_title_terms':['Engineer']})
    assert r['eligibility']=='excluded_by_config' and r['exclusion_evidence']==['Engineer']

def test_company_exact_not_substring():
    assert match_job(JOB,{**PROFILE,'matching':{'excluded_companies':['Fixture']}})['eligibility']=='needs_review'

def test_missing_is_unknown_not_exclusion_or_inflated_score():
    p={**PROFILE,'matching':{'preferred_location_terms':['Cairo'],'excluded_location_terms':['Berlin'],'required_listing_terms':['visa sponsorship'],'weights':{'skills':50,'location':50}}}
    r=match_job({**JOB,'location':''},p)
    assert r['ranking']['score_percent']==50
    assert r['eligibility']=='needs_review'
    assert [x['state'] for x in r['hard_constraint_checks']]==['unknown','unknown']
    assert not r['ranking']['dimensions']['location']['known']

def test_no_inputs_no_fabricated_score():
    r=match_job(JOB,{})
    assert r['score_percent'] is None and r['ranking']['score_percent'] is None
    assert r['eligibility']=='needs_review'

def test_negated_or_ambiguous_requirement_not_rewarded():
    for text in ('Python not required','Python required and SQL preferred'):
        r=match_job({**JOB,'title':'Engineer','description':text},PROFILE)
        assert r['ranking']['score_percent']==0
        assert r['score_percent']==100 # Text is still a mention; old denominator remains explicit.

@pytest.mark.parametrize('text',['تحليل البيانات مطلوب','Datenanalyse erforderlich'])
def test_multilingual_skill_alias_ranking(text):
    r=match_job({**JOB,'title':'Analyst','description':text},{'skills':['Data analysis']})
    assert r['ranking']['score_percent']==100 and r['requirements'][0]['skill']=='Data analysis'

def test_custom_skill_context():
    r=match_job({**JOB,'title':'Engineer','description':'Rust not required'},{'skills':['Rust']})
    assert r['ranking']['score_percent']==0 and r['requirements'][0]['classification']=='not_required'

@pytest.mark.parametrize('matching',[
 [],{'unknown':[]},{'weights':{'skills':0}},{'weights':{'skills':True}},
 {'weights':{'skills':float('nan')}},{'weights':{'skills':float('inf')}},{'weights':{'skills':101}},
 {'weights':{'unknown':1}},{'skill_weights':{'Rust':2}},{'skill_weights':{'Python':-1}},
 {'preferred_title_terms':'engineer'},{'preferred_title_terms':['']},{'excluded_companies':[False]},
 {'required_listing_terms':['a\nb']},{'preferred_location_terms':['x'*101]},
])
def test_invalid_matching_settings_no_mutation(store,matching):
    with pytest.raises(ValueError):store.save_profile({**PROFILE,'matching':matching})
    assert store.profile()==PROFILE

def test_profile_scoping_invalidation_and_fingerprints(store):
    store.ingest([JOB]);store.evaluate();r=store.jobs()[0]['match'];assert r['fingerprints']['matcher']==MATCHER_VERSION
    store.save_profile({**PROFILE,'matching':{'excluded_companies':['Fixture Co']}},'other');store.evaluate('other')
    assert store.jobs(profile_id='other')[0]['match']['eligibility']=='excluded_by_config'
    store.save_profile({**PROFILE,'matching':{'preferred_title_terms':['Lead']}})
    assert store.jobs()[0]['match'] is None and store.jobs(profile_id='other')[0]['match'] is not None
    store.evaluate();assert store.jobs()[0]['match']['fingerprints']['profile']!=r['fingerprints']['profile']
    store.ingest([{**JOB,'description':'SQL required'}]);assert store.jobs()[0]['match'] is None
    store.evaluate();assert store.jobs()[0]['match']['fingerprints']['job']!=r['fingerprints']['job']

def test_deterministic_unchanged_inputs_and_no_network(monkeypatch):
    monkeypatch.setattr('socket.create_connection',lambda *a,**k:pytest.fail('No matching network calls'))
    p=copy.deepcopy(PROFILE);j=copy.deepcopy(JOB)
    a=match_job(j,p);b=match_job(j,p)
    assert a==b and j==JOB and p==PROFILE
    assert 'SQL' not in a['ats_advice']['not_recorded_required_mentions']
    assert all('eligibility' in x['notice'] for x in a['requirements'])

def test_advice_not_recorded_is_not_inability():
    r=match_job({**JOB,'description':'SQL required'},PROFILE)
    assert r['ats_advice']['not_recorded_required_mentions']==['SQL']
    assert 'does not mean unable' in r['ats_advice']['notice']

def test_matcher_upgrade_invalidates_only_derived_cache(store):
    store.ingest([JOB]);store.evaluate();job=store.jobs()[0];store.set_status(job['id'],'saved',notes='User state remains')
    with store.connect() as db:
        old={**job['match'],'method':'deterministic lexical v1'}
        db.execute('UPDATE matches SET data=?',(json.dumps(old),))
    reopened=Store(store.path)
    assert reopened.jobs()[0]['match'] is None and reopened.jobs()[0]['status']=='saved'
    assert reopened.jobs()[0]['notes']=='User state remains'
    assert reopened.summary()['matched_jobs']==0
    reopened.evaluate();assert reopened.jobs()[0]['match']['method']==MATCHER_VERSION

@pytest.mark.parametrize('text,label',[
 ('Python not mandatory','not_required'),('Python not essential','not_required'),
 ('Python nicht zwingend','not_required'),('Python غير إلزامي','not_required'),
 ('Python is not a required skill','ambiguous'),('Python not preferred','ambiguous'),
 ('Python required if joining our ML team','ambiguous'),('Python or SQL required','ambiguous'),
 ('Python oder SQL erforderlich','ambiguous'),('Python مطلوب إذا انضممت للفريق','ambiguous'),
 ('Python أو SQL مطلوب','ambiguous'),('Python required or equivalent experience','ambiguous'),
])
def test_condition_alternative_and_negation_are_not_overclaimed(text,label):
    assert extract(text,PROFILE)[0]['classification']==label

def test_large_listing_evidence_is_bounded_and_disclosed():
    r=match_job({**JOB,'description':'Python required. '*1000},PROFILE)
    assert len(r['requirements'])==300 and r['requirements_truncated']
    assert any('300 rows' in x for x in r['uncertainties'])
