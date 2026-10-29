"""Private manual exercise records. No candidate evidence, grading or network calls."""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re
import uuid
from urllib.parse import urlsplit
from .store import dump, now
from .learning_resources import HOSTS

KEY='learning_progress'
MAX_ITEMS=50
STATES=('planned','in_progress','paused','completed')
NOTICE=('Personal self-records only, not independently verified learning, qualifications or candidate facts. '
        'Nothing is run, uploaded, added to evidence/CVs or submitted. Private notes are local text. '
        'Completion and timestamps describe the current saved self-record, not a complete activity history.')
TEXT_KEYS=('skill','catalog_version','resource_id','resource_title','publisher','resource_url','checked_on','access_notes',
           'exercise_id','exercise_title','objective','deliverable','setup_and_cost','authorship','execution')
LIST_KEYS=('prerequisites','steps','self_checks')
RECORD_KEYS={'id','snapshot','snapshot_hash','status','notes','revision','created_at','updated_at','completed_at'}


def _text(value,limit=2000,empty=False):
    if (not isinstance(value,str) or len(value)>limit or (not empty and not value.strip())
            or any((ord(c)<32 and c not in '\n\t') or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in value)):
        raise ValueError('Invalid learning text or length')
    return value


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Invalid learning record ID')
    return value


def _hash(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{64}',value):raise ValueError('Invalid learning fingerprint')
    return value


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def offer_fingerprint(priority):
    options=priority['learning_options']
    if options['mode']!='optional_practice':return None
    return digest({'skill':priority['skill'],'contexts':priority['contexts'],'guidance':priority['guidance'],
                   'samples':priority['evidence_samples'],'options':{k:v for k,v in options.items() if k!='plan_fingerprint'}})


def _snapshot(priority,catalog):
    o=priority['learning_options'];r=o['resources'][0];e=o['exercise']
    return {'skill':priority['skill'],'catalog_version':catalog['version'],'resource_id':r['id'],
            'resource_title':r['title'],'publisher':r['publisher'],'resource_url':r['url'],'checked_on':r['verified_on'],'access_notes':r['access_notes'],
            'exercise_id':e['id'],'exercise_title':e['title'],'objective':e['objective'],'prerequisites':deepcopy(e['prerequisites']),
            'steps':deepcopy(e['steps']),'deliverable':e['deliverable'],'self_checks':deepcopy(e['self_checks']),
            'setup_and_cost':e['setup_and_cost'],'authorship':e['authorship'],'execution':e['execution']}


def _snapshot_valid(s):
    if not isinstance(s,dict) or set(s)!=set(TEXT_KEYS+LIST_KEYS):raise ValueError('Invalid stored exercise snapshot')
    for key in TEXT_KEYS:_text(s[key])
    if len(s['checked_on'])!=10 or date.fromisoformat(s['checked_on']).isoformat()!=s['checked_on']:raise ValueError('Invalid resource check date')
    u=urlsplit(s['resource_url'])
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):raise ValueError('Invalid stored reading URL')
    for key in LIST_KEYS:
        v=s[key]
        if not isinstance(v,list) or not (1 if key=='prerequisites' else 3)<=len(v)<=5:raise ValueError('Invalid stored practice list')
        for text in v:_text(text,1200)


def _stamp(value):
    _text(value,80)
    d=datetime.fromisoformat(value)
    if d.tzinfo is None or d.utcoffset().total_seconds()!=0:raise ValueError('Invalid learning timestamp')
    return d


def _read(db,profile_id):
    if not db.execute('SELECT 1 FROM profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Configure a profile first')
    row=db.execute('SELECT data FROM workflow_settings WHERE profile_id=?',(profile_id,)).fetchone()
    try:data=json.loads(row[0]) if row else {}
    except (ValueError,TypeError,RecursionError):raise ValueError('Invalid workflow settings; preserve and restore a backup') from None
    if not isinstance(data,dict):raise ValueError('Invalid workflow settings')
    namespace=data.get(KEY,{'version':1,'items':[]})
    if (not isinstance(namespace,dict) or set(namespace)!={'version','items'} or type(namespace['version']) is not int
            or namespace['version']!=1 or not isinstance(namespace['items'],list) or len(namespace['items'])>MAX_ITEMS):
        raise ValueError('Invalid learning-progress collection; no reset was attempted')
    items=namespace['items'];ids=set();hashes=set()
    for item in items:
        try:
            if not isinstance(item,dict) or set(item)!=RECORD_KEYS:raise ValueError('Invalid stored learning record')
            _id(item['id']);_hash(item['snapshot_hash']);_snapshot_valid(item['snapshot'])
            if digest(item['snapshot'])!=item['snapshot_hash']:raise ValueError('Changed stored exercise snapshot')
            if item['id'] in ids or item['snapshot_hash'] in hashes:raise ValueError('Duplicate learning record')
            ids.add(item['id']);hashes.add(item['snapshot_hash']);_text(item['notes'],empty=True)
            if not isinstance(item['status'],str) or item['status'] not in STATES:raise ValueError('Invalid learning status')
            if type(item['revision']) is not int or not 1<=item['revision']<=1_000_000:raise ValueError('Invalid learning revision')
            created,updated=_stamp(item['created_at']),_stamp(item['updated_at'])
            if updated<created:raise ValueError('Invalid learning timestamps')
            if item['status']=='completed':
                completed=_stamp(item['completed_at'])
                if not created<=completed<=updated:raise ValueError('Invalid completion timestamp')
            elif item['completed_at']!='':raise ValueError('Unexpected completion timestamp')
        except (KeyError,TypeError,UnicodeError,OverflowError) as exc:
            raise ValueError('Invalid stored learning record; preserve a backup') from None
    return data,items


def _write(store,db,profile_id,data,items,event,item):
    data[KEY]={'version':1,'items':items}
    db.execute('INSERT INTO workflow_settings VALUES(?,?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
               (profile_id,dump(data),now()))
    store.audit(db,event,{'profile_id':profile_id,'id':item['id'],'revision':item['revision'],'status':item['status']})


def listing(store,profile_id='default'):
    with store.connect() as db:
        _,items=_read(db,profile_id)
    return {'items':items,'statuses':list(STATES),'limit':MAX_ITEMS,'notice':NOTICE,'snapshot_policy':'Saved exercise snapshots never auto-refresh from current matching or catalog content.'}


def create(store,skill,preview_fingerprint,profile_id='default'):
    _text(skill,80);_hash(preview_fingerprint)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');data,items=_read(db,profile_id)
        # Writer lock prevents profile/match edits between re-reading the offer and saving.
        report=store.learning(profile_id)
        priority=next((p for p in report['priorities'] if p['skill']==skill),None)
        if priority is None or priority['learning_options']['mode']!='optional_practice':raise ValueError('No current practice offer; refresh guidance')
        if offer_fingerprint(priority)!=preview_fingerprint:raise ValueError('Practice preview changed; refresh guidance before saving')
        snapshot=_snapshot(priority,report['resource_catalog']);_snapshot_valid(snapshot);h=digest(snapshot)
        prior=next((x for x in items if x['snapshot_hash']==h),None)
        if prior:return prior  # Idempotent save never resets private notes or completion.
        if len(items)>=MAX_ITEMS:raise ValueError('At most 50 saved practices per profile')
        t=now();item={'id':uuid.uuid4().hex,'snapshot':snapshot,'snapshot_hash':h,'status':'planned','notes':'',
                     'revision':1,'created_at':t,'updated_at':t,'completed_at':''};items.append(item)
        _write(store,db,profile_id,data,items,'learning_practice_saved',item)
        return item


def _revision(value):
    if type(value) is not int or not 1<=value<=1_000_000:raise ValueError('Expected a current learning revision')


def update(store,record_id,value,expected_revision,profile_id='default'):
    _id(record_id);_revision(expected_revision)
    if not isinstance(value,dict) or set(value)!={'status','notes','completed_attested'}:raise ValueError('Use status, notes and completed_attested only')
    status=value['status'];notes=_text(value['notes'],empty=True)
    if not isinstance(status,str) or status not in STATES:raise ValueError('Unknown learning status')
    if type(value['completed_attested']) is not bool:raise ValueError('Completion choice must be an explicit boolean')
    if status=='completed' and not value['completed_attested']:raise ValueError('Confirm that you completed practice and reviewed its self-checks')
    if status!='completed' and value['completed_attested']:raise ValueError('Completion confirmation applies only to completed practice')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');data,items=_read(db,profile_id)
        item=next((x for x in items if x['id']==record_id),None)
        if item is None:raise ValueError('Learning record not found')
        if item['revision']!=expected_revision:raise ValueError('Learning record changed; refresh before saving')
        if item['status']==status and item['notes']==notes:return item
        if item['revision']>=1_000_000:raise ValueError('Learning revision limit reached; export a backup before deleting or re-saving')
        t=max(_stamp(now()),_stamp(item['updated_at'])).isoformat();item.update(status=status,notes=notes,revision=item['revision']+1,updated_at=t,
            completed_at=(item['completed_at'] or t) if status=='completed' else '')
        _write(store,db,profile_id,data,items,'learning_practice_updated',item);return item


def delete(store,record_id,expected_revision,confirmed=False,profile_id='default'):
    _id(record_id);_revision(expected_revision)
    if confirmed is not True:raise ValueError('Confirm learning-record deletion')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');data,items=_read(db,profile_id)
        item=next((x for x in items if x['id']==record_id),None)
        if item is None:raise ValueError('Learning record not found')
        if item['revision']!=expected_revision:raise ValueError('Learning record changed; refresh before deleting')
        _write(store,db,profile_id,data,[x for x in items if x['id']!=record_id],'learning_practice_deleted',item)
    return {'deleted':True}
