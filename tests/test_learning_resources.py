"""Dated official reading, bounded original exercises, safe additive read-only output."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
import socket
from unittest.mock import patch
from urllib.parse import urlsplit
import pytest
from jobhunter_app import learning_resources as lr
from jobhunter_app.matching import SKILLS
from jobhunter_app.store import Store
from tests.test_contextual_learning import snapshot,build,sql,edit
from tests.test_web_local import web,request

CAT=json.loads(lr.CATALOG.read_text())

@pytest.mark.parametrize('skill',list(SKILLS))
def test_authoritative_resource_and_authored_exercise_for_each_canonical_skill(skill):
    r=next(r for r in lr.load()['resources'] if r['skill']==skill)
    assert r['verified_on']=='2026-10-29' and r['language']=='en'
    assert urlsplit(r['url']).hostname in lr.HOSTS and r['publisher'] and r['verification']['observed_excerpt']
    assert 'not an end-to-end' in r['verification']['method']
    ex=r['exercise'];assert re.fullmatch('[a-z0-9-]+',ex['id']) and 'JobHunter authored' in ex['authorship']
    assert len(ex['steps'])==len(ex['self_checks'])==3 and ex['deliverable'] and ex['prerequisites']
    assert 'Manual only' in ex['execution'] and 'not measured' in ex['estimate_notice']


def p(skill='SQL',tier='required_cues'):
    return {'skill':skill,'guidance':{'tier':tier},'vacancies':7,'contexts':{'required':7}}

@pytest.mark.parametrize('tier',('required_cues','preferred_cues'))
def test_optional_practice_does_not_change_priority_or_counts(tier):
    priority=p(tier=tier);before=deepcopy(priority);meta=lr.attach([priority],date(2026,10,29))
    assert {k:priority[k] for k in before}==before
    o=priority['learning_options'];assert o['mode']=='optional_practice' and len(o['resources'])==1 and o['exercise']
    assert meta['available'] and meta['status']=='dated_check' and meta['resource_count']==meta['exercise_count']==17
    assert meta['progress_tracking'] and not meta['network_checks_during_report']

@pytest.mark.parametrize('tier',('negated_only','clarify_first','mention_only','unknown'))
def test_no_practice_promotion_from_negated_ambiguous_plain_or_unknown(tier):
    priority=p(tier=tier);lr.attach([priority],date(2026,10,29));o=priority['learning_options']
    assert o['resources']==[] and o['exercise'] is None and o['mode']!='optional_practice'
    assert o['reason']


def test_unknown_skill_never_gets_a_synthesized_link():
    priority=p('Quantum flower arranging');lr.attach([priority],date(2026,10,29))
    assert priority['learning_options']['mode']=='unsupported' and priority['learning_options']['resources']==[]

@pytest.mark.parametrize('days,status',[(0,'dated_check'),(90,'dated_check'),(91,'review_due'),(500,'review_due')])
def test_review_window_is_explicit_and_does_not_make_runtime_requests(days,status):
    from datetime import timedelta
    with patch('socket.create_connection',side_effect=AssertionError('No network')):
        priority=p();m=lr.attach([priority],date(2026,10,29)+timedelta(days=days))
    assert m['status']==status and priority['learning_options']['catalog_status']==status
    assert priority['learning_options']['resources'][0]['verified_on']=='2026-10-29'


def test_future_review_not_presented_as_verified():
    priority=p();m=lr.attach([priority],date(2026,10,28))
    assert not m['available'] and m['status']=='unavailable' and priority['learning_options']['exercise'] is None

@pytest.mark.parametrize('invalid',['2026-10-29',123,True])
def test_explicit_date_type_errors_are_not_silent(invalid):
    with pytest.raises(ValueError):lr.attach([],invalid)

@pytest.mark.parametrize('path,value',[
 (('schema_version',),True),(('schema_version',),2),(('review_due_days',),0),(('review_due_days',),True),
 (('reviewed_on',),'not-a-date'),(('resources',),[]),
 (('resources',0,'skill'),'Not canonical'),(('resources',0,'skill'),[]),
 (('resources',0,'url'),'javascript:alert(1)'),(('resources',0,'url'),'http://docs.python.org/3/tutorial/'),
 (('resources',0,'url'),'https://docs.python.org.attacker.test/x'),(('resources',0,'url'),'https://u:p@docs.python.org/x'),
 (('resources',0,'url'),'https://docs.python.org:666/x'),(('resources',0,'url'),'https://localhost/x'),
 (('resources',0,'language'),'unknown'),(('resources',0,'kind'),'paid lab'),
 (('resources',0,'verified_on'),'2026-10-28'),(('resources',0,'title'),'x'*2001),
 (('resources',0,'title'),'bad\x00title'),(('resources',0,'verification'),None),
 (('resources',0,'exercise','suggested_minutes'),True),(('resources',0,'exercise','suggested_minutes'),9999),
 (('resources',0,'exercise','steps'),['one']), (('resources',0,'exercise','self_checks'),[]),
 (('resources',0,'exercise','deliverable'),''),(('resources',0,'exercise','prerequisites'),None),
])
def test_corrupt_catalog_fails_closed_without_breaking_context_guidance(tmp_path,monkeypatch,path,value):
    d=deepcopy(CAT);obj=d
    for key in path[:-1]:obj=obj[key]
    obj[path[-1]]=value;file=tmp_path/'catalog.json';file.write_text(json.dumps(d));monkeypatch.setattr(lr,'CATALOG',file)
    priority=p();meta=lr.attach([priority],date(2026,10,29))
    assert not meta['available'] and priority['vacancies']==7 and priority['learning_options']['mode']=='unavailable'
    assert priority['learning_options']['resources']==[] and priority['learning_options']['exercise'] is None

@pytest.mark.parametrize('kind',['missing','invalid_json','too_large','deep_json','not_object','duplicate_skill','duplicate_id','duplicate_exercise_id'])
def test_other_catalog_failures_safe_fallback(tmp_path,monkeypatch,kind):
    file=tmp_path/'catalog.json';data=deepcopy(CAT)
    if kind=='invalid_json':file.write_text('{')
    elif kind=='too_large':file.write_bytes(b'x'*150001)
    elif kind=='deep_json':file.write_text('['*2000+'0'+']'*2000)
    elif kind=='not_object':file.write_text('[]')
    elif kind!='missing':
        if kind=='duplicate_skill':data['resources'][1]['skill']=data['resources'][0]['skill']
        if kind=='duplicate_id':data['resources'][1]['id']=data['resources'][0]['id']
        if kind=='duplicate_exercise_id':data['resources'][1]['exercise']['id']=data['resources'][0]['exercise']['id']
        file.write_text(json.dumps(data))
    monkeypatch.setattr(lr,'CATALOG',file);assert not lr.attach([p()],date(2026,10,29))['available']


def test_returned_options_are_isolated_from_catalog_and_other_calls():
    a=p();b=p();lr.attach([a,b],date(2026,10,29));a['learning_options']['resources'][0]['title']='changed';a['learning_options']['exercise']['steps'].clear()
    assert b['learning_options']['resources'][0]['title']!='changed' and len(b['learning_options']['exercise']['steps'])==3
    c=p();lr.attach([c],date(2026,10,29));assert len(c['learning_options']['exercise']['steps'])==3


def store(tmp_path):
    s=Store(tmp_path/'learning.sqlite3');s.save_profile({'name':'Synthetic','skills':[],'facts':[]});return s


def test_all_skills_report_read_only_no_network_no_automatic_candidate_facts(tmp_path):
    s=store(tmp_path);s.ingest([{'title':'Synthetic Engineer','company':'Synthetic','url':f'https://example.org/resources/{i}','description':skill+' required.'} for i,skill in enumerate(SKILLS)]);s.evaluate();before=snapshot(s)
    with patch('socket.create_connection',side_effect=AssertionError('No network')):
        r=s.learning()
    assert snapshot(s)==before and r['vacancies_reviewed']==17 and set(r['contextual_order'])==set(SKILLS)
    assert all(x['learning_options']['exercise'] and x['learning_options']['mode']=='optional_practice' for x in r['priorities'])
    assert r['capabilities']=={'contextual_guidance':True,'verified_resources':True,'exercise_catalog':True,'learning_progress':True}
    assert s.profile()['facts']==[] and s.profile()['skills']==[]

@pytest.mark.parametrize('text,mode',[
 ('SQL required.','optional_practice'),('SQL preferred.','optional_practice'),('SQL not required.','not_recommended'),
 ('SQL required. SQL not required.','clarify_first'),('SQL required or optional.','clarify_first'),('We use SQL.','clarify_first'),
])
def test_context_to_practice_gate(tmp_path,text,mode):
    s=store(tmp_path);r=build(s,[text]);assert sql(r)['learning_options']['mode']==mode
    assert bool(sql(r)['learning_options']['resources'])==(mode=='optional_practice')

@pytest.mark.parametrize('field,value',[('requirements_truncated',True),('requirements',[]),('fingerprints',{})])
def test_limited_stale_or_missing_context_cannot_select_practice(tmp_path,field,value):
    s=store(tmp_path);build(s,['SQL required.']);edit(s,lambda m:m.update({field:value}));r=s.learning()
    assert sql(r)['contexts']['unclassified']==1 and sql(r)['learning_options']['mode']=='clarify_first'
    assert sql(r)['learning_options']['exercise'] is None


def test_profile_exclusion_and_alias_mapping_use_existing_population(tmp_path):
    s=store(tmp_path);s.save_profile({'name':'Synthetic','skills':['Python'],'facts':[],'excluded_title_terms':['Senior']})
    s.ingest([{'title':'Engineer','company':'Synthetic','url':'https://example.org/a','description':'maschinelles lernen erforderlich.'},
              {'title':'Senior Engineer','company':'Synthetic','url':'https://example.org/b','description':'Java required.'}]);s.evaluate();r=s.learning()
    assert r['vacancies_reviewed']==1 and [p['skill'] for p in r['priorities']]==['Machine learning']
    assert r['priorities'][0]['learning_options']['resources'][0]['id']=='sklearn-started'
    s.save_profile({'name':'Other','skills':['Machine learning','Java'],'facts':[]},'other');s.evaluate('other')
    assert s.learning('other')['priorities']==[] and s.learning()==r


def test_empty_guidance_does_not_auto_assign_catalog_tasks(tmp_path):
    s=store(tmp_path);r=s.learning();assert r['priorities']==[] and r['resource_catalog']['resource_count']==17
    assert r['capabilities']['learning_progress']


def test_http_readonly_resource_data_and_ui_asset(web):
    s,server=web;s.save_profile({'name':'Synthetic','skills':[],'facts':[]});build(s,['SQL required.'])
    before=snapshot(s);code,headers,body=request(web,'GET','/api/learning');r=json.loads(body)
    assert code==200 and sql(r)['learning_options']['resources'][0]['publisher']=='PostgreSQL Global Development Group'
    assert snapshot(s)==before
    assert b'learning-catalog' in request(web,'GET','/')[2] and b'self_checks' in request(web,'GET','/learning.js')[2]


def test_cost_account_and_retrieval_limits_are_explicit():
    rows={r['skill']:r for r in lr.load()['resources']}
    assert 'pay' in rows['AWS']['verification']['observed_excerpt'] and 'No cloud' in rows['AWS']['exercise']['setup_and_cost']
    assert 'license' in rows['Excel']['access_notes'] and 'Paper' in rows['Excel']['exercise']['setup_and_cost']
    assert 'license' in rows['Docker']['access_notes'] and 'no Docker' in rows['Docker']['exercise']['setup_and_cost']
    assert 'no LLM' in rows['RAG']['exercise']['self_checks'][2]
    for key in ('Communication','Project management','Leadership'):assert 'account' in rows[key]['access_notes']
