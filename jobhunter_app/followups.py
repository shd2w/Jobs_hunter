"""Local calendar-day inbox. No scheduler, network calls or recruiter messages."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import re
import uuid
from .store import now


def calendar_day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('Use a complete calendar date YYYY-MM-DD')
    try: return date.fromisoformat(value)
    except ValueError as exc: raise ValueError('Invalid calendar date') from exc


def save(store, job_id, title, due, notes='', profile_id='default', followup_id=None):
    calendar_day(due)
    if not isinstance(title,str) or not title.strip() or len(title)>300 or '\x00' in title: raise ValueError('Follow-up title must contain 1–300 characters')
    if not isinstance(notes,str) or len(notes)>2000 or '\x00' in notes: raise ValueError('Follow-up notes must be at most 2,000 characters')
    if not isinstance(job_id,str): raise ValueError('Job ID required')
    if followup_id is not None and (not isinstance(followup_id,str) or len(followup_id)>100): raise ValueError('Invalid follow-up ID')
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM jobs WHERE id=?',(job_id,)).fetchone(): raise ValueError('Unknown job')
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(profile_id,)).fetchone(): raise ValueError('Unknown profile')
        if followup_id:
            prior=db.execute('SELECT job_id FROM followups WHERE id=? AND profile_id=?',(followup_id,profile_id)).fetchone()
            if not prior or prior['job_id']!=job_id: raise ValueError('Unknown follow-up for this profile and job')
            db.execute('UPDATE followups SET title=?,due=?,notes=?,updated_at=? WHERE id=? AND profile_id=?',(title.strip(),due,notes,now(),followup_id,profile_id))
        else:
            if db.execute('SELECT COUNT(*) FROM followups WHERE profile_id=?',(profile_id,)).fetchone()[0]>=10000: raise ValueError('Follow-up limit reached for this profile')
            followup_id=uuid.uuid4().hex
            db.execute('INSERT INTO followups VALUES(?,?,?,?,?,?,?,?)',(followup_id,profile_id,job_id,title.strip(),due,notes,0,now()))
        store.audit(db,'followup_saved',{'id':followup_id,'profile_id':profile_id,'job_id':job_id})
    return {'id':followup_id,'saved':True}


def complete(store, followup_id, completed=True, profile_id='default'):
    if type(completed) is not bool or not isinstance(followup_id,str): raise ValueError('Explicit completion boolean and follow-up ID required')
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM followups WHERE id=? AND profile_id=?',(followup_id,profile_id)).fetchone(): raise ValueError('Unknown follow-up for this profile')
        db.execute('UPDATE followups SET completed=?,updated_at=? WHERE id=? AND profile_id=?',(int(completed),now(),followup_id,profile_id))
        store.audit(db,'followup_completion_changed',{'id':followup_id,'profile_id':profile_id,'completed':completed})
    return {'id':followup_id,'completed':completed}


def digest(store, profile_id='default', today=None, days=7, offset=0, limit=100, include_completed=False):
    current=calendar_day(today) if today is not None else date.today()
    if type(days) is not int or not 0<=days<=3650: raise ValueError('Horizon must be 0–3650 days')
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=1000: raise ValueError('Invalid inbox pagination')
    if type(include_completed) is not bool: raise ValueError('Invalid completion filter')
    try: cutoff=(current+timedelta(days=days)).isoformat()
    except OverflowError as exc: raise ValueError('Date horizon is out of range') from exc
    current=current.isoformat()
    with store.connect() as db:
        records=db.execute('''SELECT 'deadline' kind,j.id id,j.id job_id,j.title job_title,j.company,j.url,
         'Application deadline' title,a.deadline due,'' notes,0 completed,a.status
         FROM applications a JOIN jobs j ON j.id=a.job_id
         WHERE a.profile_id=? AND a.deadline<>'' AND a.status IN ('discovered','saved','reviewing','preparing','ready')
         UNION ALL SELECT 'followup',f.id,f.job_id,j.title,j.company,j.url,f.title,f.due,f.notes,f.completed,COALESCE(a.status,'discovered')
         FROM followups f JOIN jobs j ON j.id=f.job_id LEFT JOIN applications a ON a.job_id=f.job_id AND a.profile_id=f.profile_id
         WHERE f.profile_id=? AND (? OR f.completed=0)''',(profile_id,profile_id,int(include_completed))).fetchall()
    items=[]; invalid=0
    for record in records:
        row=dict(record)
        try: calendar_day(row['due'])
        except ValueError: invalid+=1;continue
        if row['due']>cutoff: continue
        row['completed']=bool(row['completed'])
        row['timing']='completed' if row['completed'] else 'overdue' if row['due']<current else 'today' if row['due']==current else 'upcoming'
        items.append(row)
    items.sort(key=lambda r:(r['completed'],r['due'],r['kind'],r['id']))
    counts={key:sum(r['timing']==key for r in items) for key in ('overdue','today','upcoming','completed')}
    return {'today':current,'through':cutoff,'days':days,'counts':counts,'total':len(items),'invalid_dates':invalid,
            'items':items[offset:offset+limit],'offset':offset,'has_more':offset+limit<len(items),
            'notice':'Calendar-day view, opened manually. No background notifications or messages are sent.'}

