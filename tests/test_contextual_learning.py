"""Source-bound guidance counts, conservative contexts, isolation and no writes."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from jobhunter_app.store import Store
from jobhunter_app.learning import LABELS, SAMPLE_LIMIT, EXCERPT_LIMIT, fingerprint
from tests.test_web_local import web,request

P={'name':'Synthetic Learner','skills':['Python'],'facts':[]}
J={'title':'Synthetic Engineer','company':'Synthetic Employer','url':'https://example.org/context','description':'SQL required.'}

@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'learning.sqlite3');s.save_profile(P);return s

def build(s,descriptions):
    s.ingest([{**J,'url':f'https://example.org/context/{i}','description':d} for i,d in enumerate(descriptions)])
    s.evaluate();return s.learning()

def sql(r):return next(p for p in r['priorities'] if p['skill']=='SQL')

def edit(s,func):
    with s.connect() as db:
        row=db.execute('SELECT profile_id,job_id,data FROM matches ORDER BY job_id LIMIT 1').fetchone()
        value=json.loads(row['data']);func(value)
        db.execute('UPDATE matches SET data=? WHERE profile_id=? AND job_id=?',(json.dumps(value),row['profile_id'],row['job_id']))

def snapshot(s):
    with s.connect() as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {n:[tuple(r) for r in db.execute('SELECT * FROM "'+n+'" ORDER BY rowid')] for n in tables}

@pytest.mark.parametrize('text,category,tier',[
 ('SQL required','required','required_cues'),('SQL preferred','preferred','preferred_cues'),
 ('SQL not required','not_required','negated_only'),('We use SQL','mentioned','mention_only'),
 ('SQL required or Docker preferred','ambiguous','clarify_first'),
 ('SQL required. SQL not required.','mixed','clarify_first'),
 ('SQL required. We use SQL.','mixed','clarify_first'),
 ('SQL erforderlich','required','required_cues'),('SQL wünschenswert','preferred','preferred_cues'),
 ('SQL nicht erforderlich','not_required','negated_only'),('SQL مطلوب','required','required_cues'),
 ('يفضل SQL','preferred','preferred_cues'),('SQL غير مطلوب','not_required','negated_only'),
 ('لا يشترط SQL','not_required','negated_only'),
 ('Requirements:\n- SQL','required','required_cues'),('Anforderungen:\n- SQL','required','required_cues'),
 ('المتطلبات:\n- SQL','required','required_cues'),
])
def test_context_categories_keep_legacy_mentions(store,text,category,tier):
    r=build(store,[text]);p=sql(r)
    assert r['vacancies_reviewed']==1 and p['vacancies']==1
    assert p['contexts'][category]==1 and sum(p['contexts'].values())==1
    assert p['guidance']['tier']==tier and p['evidence_samples']
    for e in p['evidence_samples']:
        assert text[e['start']:e['end']]==e['evidence']
        assert e['vacancy_context']==category and e['candidate_evidence']=='not_recorded'


def test_duplicate_clauses_and_cached_rows_count_once_per_vacancy(store):
    build(store,['SQL required. SQL required.','SQL preferred. SQL preferred.'])
    edit(store,lambda m:m['requirements'].extend(deepcopy(m['requirements'])))
    r=store.learning();p=sql(r)
    assert r['vacancies_reviewed']==2 and p['vacancies']==2
    assert p['contexts']['required']==1 and p['contexts']['preferred']==1
    assert p['evidence_coverage']['observed_valid_clause_rows']==4
    edit(store,lambda m:m['keywords']['learning_gaps'].extend(m['keywords']['learning_gaps']))
    assert sql(store.learning())['vacancies']==2


def test_separate_contextual_order_not_a_change_to_frequency_counts(store):
    r=build(store,['SQL not required.']*4+['Docker preferred.','Git required.','JavaScript in our stack.'])
    assert [(p['skill'],p['vacancies']) for p in r['priorities']]==[('SQL',4),('Docker',1),('Git',1),('JavaScript',1)]
    assert r['contextual_order']==['Git','Docker','JavaScript','SQL']
    assert sql(r)['guidance']['tier']=='negated_only' and 'No study priority' in sql(r)['next_step']
    assert all(sum(p['contexts'].values())==p['vacancies'] for p in r['priorities'])


def test_mixed_across_different_vacancies_is_not_same_as_intra_listing_mixed(store):
    r=build(store,['SQL required','SQL not required','SQL preferred','SQL required; SQL not required'])
    p=sql(r);assert p['contexts']['required']==p['contexts']['preferred']==p['contexts']['not_required']==p['contexts']['mixed']==1
    assert p['guidance']['tier']=='required_cues' and p['vacancies']==4 and r['vacancies_reviewed']==4


def test_profile_support_aliases_and_exclusions(store):
    store.save_profile({**P,'facts':[{'text':'I built an SQL example','source':'Synthetic','verified':True}], 'excluded_title_terms':['Senior']})
    store.ingest([{**J,'description':'SQL required. maschinelles lernen bevorzugt. JavaScript required.'},
                  {**J,'title':'Senior Developer','url':'https://example.org/excluded','description':'Docker required.'}]);store.evaluate()
    r=store.learning();assert r['vacancies_reviewed']==1 and r['coverage']['excluded_vacancies']==1
    assert {p['skill'] for p in r['priorities']}=={'Machine learning','JavaScript'}
    assert 'Java' not in r['contextual_order'] and 'SQL' not in r['contextual_order']
    store.save_profile({**P,'skills':['Python','SQL','Machine learning','JavaScript','Docker']},'other');store.evaluate('other')
    assert store.learning('other')['priorities']==[] and store.learning('other')['vacancies_reviewed']==2
    assert store.learning()==r


def test_unverified_fact_not_promoted_to_support(store):
    store.save_profile({**P,'facts':[{'text':'I use SQL','source':'Synthetic','verified':False}]})
    assert sql(build(store,['SQL required']))['evidence_samples'][0]['candidate_evidence']=='not_recorded'


@pytest.mark.parametrize('change',['job','profile','matcher','language_pack','eligibility_context','missing'])
def test_stale_input_version_context_does_not_change_legacy_counts_or_auto_write(store,change):
    build(store,['SQL required'])
    def alter(m):
        if change=='missing':m.pop('fingerprints')
        else:m['fingerprints'][change]='stale synthetic value'
    edit(store,alter);before=snapshot(store);r=store.learning();p=sql(r)
    assert r['vacancies_reviewed']==p['vacancies']==1 and p['contexts']['unclassified']==1
    assert p['guidance']['tier']=='clarify_first' and p['evidence_samples']==[]
    assert r['coverage']['stale_or_unverifiable_context_vacancies']==1 and snapshot(store)==before


@pytest.mark.parametrize('badrow',[None,{}, {'classification':[]}, {'classification':'required','skill':'SQL','start':True,'end':2},
 {'skill':'SQL','classification':'not_a_label','start':0,'end':12}])
def test_malformed_clause_rows_are_not_promoted(store,badrow):
    build(store,['SQL required']);edit(store,lambda m:m['requirements'].append(badrow))
    r=store.learning();p=sql(r)
    assert p['contexts']['unclassified']==1 and p['guidance']['tier']=='clarify_first'
    assert r['coverage']['invalid_evidence_rows']==1 and r['coverage']['limited_context_vacancies']==1


@pytest.mark.parametrize('field,value',[('evidence','wrong quote'),('start',-1),('end',999),('cue_packs',['unknown']),('candidate_evidence','expert')])
def test_invalid_exact_evidence_is_rejected(store,field,value):
    build(store,['SQL required']);edit(store,lambda m:m['requirements'][0].update({field:value}))
    p=sql(store.learning());assert p['contexts']['unclassified']==1 and p['evidence_samples']==[]


@pytest.mark.parametrize('field,value',[('requirements',None),('requirements_truncated',True),('requirements_truncated',None)])
def test_missing_or_limited_context_not_a_positive_priority(store,field,value):
    build(store,['SQL required']);edit(store,lambda m:m.update({field:value}));r=store.learning()
    assert sql(r)['contexts']['unclassified']==1 and r['coverage']['limited_context_vacancies']==1


def test_real_parser_cap_and_source_sample_bounds(store):
    text='SQL required.\n'*305
    p=sql(build(store,[text]));assert p['vacancies']==1 and p['contexts']['unclassified']==1
    assert all(e['vacancy_context']=='unclassified' for e in p['evidence_samples'])
    long='SQL required '+('synthetic '*120)
    p=sql(build(store,[long]));assert any(e['excerpt_truncated'] for e in p['evidence_samples'])
    jobs={j['id']:j for j in store.jobs()}
    for e in p['evidence_samples']:
        assert len(e['evidence'])<=EXCERPT_LIMIT and jobs[e['job_id']]['description'][e['start']:e['end']]==e['evidence']


def test_balanced_samples_are_limited_not_complete_and_order_is_deterministic(store):
    r=build(store,['SQL required']*5+['SQL preferred']*4+['SQL not required']*3+['We use SQL']*3+['SQL required or Docker preferred']*3+['SQL required; SQL not required']*3)
    p=sql(r);assert p['vacancies']==21 and len(p['evidence_samples'])<=SAMPLE_LIMIT and p['evidence_coverage']['samples_limited']
    assert len({e['vacancy_context'] for e in p['evidence_samples']})==6 and store.learning()==r
    assert sum(p['contexts'].values())==21


def test_listing_update_invalidates_matches_without_learning_rematching(store):
    build(store,['SQL required']);store.ingest([{**J,'url':'https://example.org/context/0','description':'SQL not required'}])
    before=snapshot(store);r=store.learning();assert r['vacancies_reviewed']==0 and r['coverage']['unmatched_vacancies']==1
    assert snapshot(store)==before


def test_read_only_all_tables_and_no_invented_resource_progress_capabilities(store):
    build(store,['SQL required']);before=snapshot(store);r=store.learning()
    assert snapshot(store)==before and r['capabilities']=={'contextual_guidance':True,'verified_resources':True,'exercise_catalog':True,'learning_progress':True}
    assert 'not mean unable' in r['notice'] and not any(k in r for k in ('resources','exercises','progress'))


@pytest.mark.parametrize('bad',['not json','[]','null','{"keywords":null}', '{"keywords":{"learning_gaps":[null]}}'])
def test_invalid_match_records_are_explicitly_omitted(store,bad):
    build(store,['SQL required'])
    with store.connect() as db:db.execute('UPDATE matches SET data=?',(bad,))
    r=store.learning();assert r['vacancies_reviewed']==0 and r['coverage']['invalid_match_rows']==1 and r['priorities']==[]


def test_empty_no_profile_and_missing_context_are_honest(store):
    r=store.learning('absent');assert r['vacancies_reviewed']==0 and not r['coverage']['profile_present']
    build(store,['SQL required']);edit(store,lambda m:m.update(requirements=[]))
    r=store.learning();assert sql(r)['contexts']['unclassified']==1 and not sql(r)['evidence_samples']


def test_http_read_only_guidance_and_asset(web):
    s,_=web;s.ingest([J]);s.evaluate();before=snapshot(s)
    status,_,body=request(web,'GET','/api/learning');r=json.loads(body)
    assert status==200 and r['method']=='contextual skill guidance v1' and sql(r)['contexts']['required']==1
    assert snapshot(s)==before and request(web,'GET','/learning.js')[0]==200


def test_fingerprint_invalid_unicode_not_a_source_claim():
    assert fingerprint({'text':'\ud800'}) is None
