"""Local workflow settings and descriptive tracking counts; no outcome inference."""
import json
import math
from datetime import date
from .store import dump,now
from .followups import calendar_day

DEFAULTS={'enabled':False,'include_job_details':False,'days':7,'max_items':5,'threshold':60}


def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Unknown workflow preference')
    value={**DEFAULTS,**value}
    if any(type(value[k]) is not bool for k in ('enabled','include_job_details')):raise ValueError('Notification choices must be explicit booleans')
    if type(value['days']) is not int or not 0<=value['days']<=365:raise ValueError('Digest horizon must be 0–365 days')
    if type(value['max_items']) is not int or not 1<=value['max_items']<=10:raise ValueError('Digest detail count must be 1–10')
    if type(value['threshold']) not in (int,float) or not 0<=value['threshold']<=100 or not math.isfinite(value['threshold']):raise ValueError('Digest threshold must be 0–100')
    return value


def settings(store,profile_id='default',value=None):
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Configure a profile first')
        if value is not None:
            db.execute('BEGIN IMMEDIATE')
            config=validate(value)
            prior=db.execute('SELECT data FROM workflow_settings WHERE profile_id=?',(profile_id,)).fetchone()
            stored=json.loads(prior[0]) if prior else {}
            payload={**config}
            for namespace in ('saved_searches','learning_progress','automatic_discovery'):
                if namespace in stored:payload[namespace]=stored[namespace]
            db.execute('INSERT INTO workflow_settings VALUES(?,?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(profile_id,dump(payload),now()))
            store.audit(db,'workflow_settings_saved',{'profile_id':profile_id})
            return config
        row=db.execute('SELECT data FROM workflow_settings WHERE profile_id=?',(profile_id,)).fetchone()
        stored=json.loads(row[0]) if row else {}
        for namespace in ('saved_searches','learning_progress','automatic_discovery'):
            stored.pop(namespace,None)
        return validate(stored)


def report(store,profile_id='default',today=None):
    current=calendar_day(today) if today is not None else date.today()
    with store.connect() as db:
        rows=db.execute('SELECT status,COUNT(*) count FROM applications WHERE profile_id=? GROUP BY status',(profile_id,)).fetchall()
        counts={r['status']:r['count'] for r in rows}
        total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        tracked=sum(counts.values());applied=counts.get('applied',0)
        ever=db.execute("SELECT COUNT(DISTINCT job_id) FROM status_history WHERE profile_id=? AND new_status='applied'",(profile_id,)).fetchone()[0]
        interviews=db.execute("SELECT COUNT(DISTINCT job_id) FROM status_history WHERE profile_id=? AND new_status='interview'",(profile_id,)).fetchone()[0]
        offers=db.execute("SELECT COUNT(DISTINCT job_id) FROM status_history WHERE profile_id=? AND new_status='offer'",(profile_id,)).fetchone()[0]
    return {'reference_day':current.isoformat(),'generated_at':now(),'local_jobs':total,'explicitly_tracked_jobs':tracked,'never_explicitly_tracked_jobs':total-tracked,
            'current_status_counts':counts,'currently_applied':applied,'ever_marked_applied':ever,'ever_marked_interview':interviews,'ever_marked_offer':offers,
            'notice':'All counts describe locally stored jobs and this profile’s explicit current states or recorded history. Ever counts are distinct jobs that reached that state, not a dated cohort or conversion rate; selecting a reference day does not reconstruct historical snapshots; they can overlap. No inferred submissions, employer verification or hiring probability.'}
