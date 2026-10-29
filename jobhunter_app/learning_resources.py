"""Bundled, dated public-reading catalog. Never fetches links or executes exercises."""
from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
from .matching import SKILLS

CATALOG = Path(__file__).with_name('learning_catalog.json')
HOSTS = frozenset(('docs.python.org','www.postgresql.org','developer.mozilla.org','www.typescriptlang.org',
                  'scikit-learn.org','pandas.pydata.org','www.open.edu','docs.docker.com','aws.amazon.com',
                  'git-scm.com','support.microsoft.com','react.dev','dev.java','learn.microsoft.com'))
NOTICE = ('Optional public reading and JobHunter-authored practice, not a requirement, course endorsement, '
          'qualification or verified candidate fact. No runtime link check, installation, execution, upload or completion record. '
          'Free reading does not include every linked tool, lab, account, certificate or cloud service.')


def _text(value, limit=2000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise ValueError('Invalid catalog text')
    if any(0xD800<=ord(c)<=0xDFFF for c in value):raise ValueError('Invalid catalog text')


def _texts(value, minimum=1, maximum=5):
    if not isinstance(value,list) or not minimum<=len(value)<=maximum:raise ValueError('Invalid catalog list')
    for item in value:_text(item,1200)


def _day(value):
    if not isinstance(value,str) or len(value)!=10:raise ValueError('Invalid catalog date')
    result=date.fromisoformat(value)
    if result.isoformat()!=value:raise ValueError('Invalid catalog date')
    return result


def _validate(data):
    if not isinstance(data,dict) or type(data.get('schema_version')) is not int or data.get('schema_version')!=1:raise ValueError('Unsupported catalog')
    _text(data['version'],80);_day(data['reviewed_on']);_text(data['verification_scope']);_text(data['exercise_authorship'])
    if type(data.get('review_due_days')) is not int or not 1<=data['review_due_days']<=365:raise ValueError('Invalid review interval')
    rows=data.get('resources')
    if not isinstance(rows,list) or len(rows)!=len(SKILLS):raise ValueError('Incomplete catalog')
    ids,skills,exercise_ids=set(),set(),set()
    for r in rows:
        if not isinstance(r,dict) or r.get('skill') not in SKILLS:raise ValueError('Unknown catalog skill')
        for key in ('id','title','publisher','url','access_notes','kind'):_text(r[key])
        if r['id'] in ids or r['skill'] in skills:raise ValueError('Duplicate catalog identity')
        ids.add(r['id']);skills.add(r['skill'])
        if r.get('language')!='en' or r.get('kind')!='public reading':raise ValueError('Unsupported resource kind')
        if _day(r['verified_on'])!=_day(data['reviewed_on']):raise ValueError('Inconsistent review date')
        u=urlsplit(r['url'])
        if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):raise ValueError('Unsafe catalog URL')
        _texts(r['topics']);v=r['verification']
        for k in ('method','observed_excerpt','scope'):_text(v[k])
        ex=r['exercise']
        for k in ('id','title','authorship','objective','deliverable','setup_and_cost','execution','estimate_notice'):_text(ex[k])
        if ex['id'] in exercise_ids:raise ValueError('Duplicate exercise identity')
        exercise_ids.add(ex['id'])
        _texts(ex['prerequisites']);_texts(ex['steps'],3,5);_texts(ex['self_checks'],3,5)
        if type(ex['suggested_minutes']) is not int or not 15<=ex['suggested_minutes']<=180:raise ValueError('Invalid practice estimate')
    if skills!=set(SKILLS):raise ValueError('Incomplete catalog')
    return data


def load():
    """Read a bounded local package asset; corrupt data never creates generated links."""
    if CATALOG.stat().st_size>150_000:raise ValueError('Catalog too large')
    return _validate(json.loads(CATALOG.read_text(encoding='utf-8')))


def attach(priorities, as_of=None):
    today=as_of if as_of is not None else datetime.now(timezone.utc).date()
    if type(today) is not date:raise ValueError('Catalog review date must be a calendar date')
    try:
        data=load();reviewed=_day(data['reviewed_on']);age=(today-reviewed).days
        if age<0:raise ValueError('Catalog review date is in the future')
        rows={r['skill']:r for r in data['resources']}
        meta={'available':True,'version':data['version'],'reviewed_on':data['reviewed_on'],'as_of':today.isoformat(),
              'review_due_days':data['review_due_days'],'status':'review_due' if age>data['review_due_days'] else 'dated_check',
              'resource_count':len(rows),'exercise_count':len(rows),'covered_skills':list(rows),'notice':NOTICE,
              'verification_scope':data['verification_scope'],'exercise_authorship':data['exercise_authorship'],
              'network_checks_during_report':False,'progress_tracking':True}
    except (OSError,ValueError,KeyError,TypeError,OverflowError,RecursionError):
        rows={};meta={'available':False,'status':'unavailable','resource_count':0,'exercise_count':0,'covered_skills':[],
                      'notice':'Bundled resource catalog unavailable or invalid; no replacement links or exercises were generated. '+NOTICE,
                      'network_checks_during_report':False,'progress_tracking':True}
    for p in priorities:
        tier=p['guidance']['tier'];row=rows.get(p['skill'])
        mode=('unavailable' if not meta['available'] else 'unsupported' if row is None else
              'not_recommended' if tier=='negated_only' else 'clarify_first' if tier not in ('required_cues','preferred_cues') else 'optional_practice')
        reason={'unavailable':'The packaged catalog could not be validated. No runtime lookup was attempted.',
                'unsupported':'No curated resource is available for this exact skill. No URL was invented.',
                'not_recommended':'Negated-only mentions do not create a study recommendation.',
                'clarify_first':'Clarify the original listing and your goals first; uncertain, mixed-only or plain mentions do not select practice.',
                'optional_practice':'Current required/preferred cues permit an optional practice suggestion; review the full source and your existing evidence first.'}[mode]
        public=deepcopy(row) if mode=='optional_practice' else None
        exercise=public.pop('exercise') if public else None
        p['learning_options']={'mode':mode,'reason':reason,'resources':[public] if public else [],'exercise':exercise,
                               'notice':NOTICE,'catalog_status':meta['status']}
    return meta
