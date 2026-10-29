"""Read-only aggregate reporting. Current snapshots are not historical cohorts."""
import csv
import io
import json
from datetime import datetime,timedelta,timezone
from .followups import calendar_day
from .store import STATES,now

MAX_DAYS=366
ACTIVE=('discovered','saved','reviewing','preparing','ready')
NOTICE=('Current states and due-item completion are snapshots at generation time, not states as of the selected end date. '
        'Activity counts recorded status changes in inclusive UTC calendar days; repeated visits count as separate events. '
        'Distinct-job counts across statuses or days overlap and must not be added. Missing history is unknown, not proof of no activity. '
        'Due dates are stored calendar dates, not exact closing times; completed follow-ups are not completion events in the window. '
        'No inferred submissions, employer verification, conversion rates or hiring probabilities.')

def window(start=None,end=None):
    last=calendar_day(end) if end is not None else datetime.now(timezone.utc).date()
    try:first=calendar_day(start) if start is not None else last-timedelta(days=29)
    except OverflowError as exc:raise ValueError('Date window is out of range; choose a start date') from exc
    days=(last-first).days+1
    if not 1<=days<=MAX_DAYS:raise ValueError('Choose an inclusive window of 1–366 days')
    return first,last,days

def _stamp(value):
    if not isinstance(value,str) or len(value)>64 or 'T' not in value:raise ValueError('Invalid timestamp')
    try:
        d=datetime.fromisoformat(value)
        if d.tzinfo is None or d.utcoffset() is None:raise ValueError('Timestamp requires a timezone')
        return d.astimezone(timezone.utc).date()
    except (ValueError,OverflowError,TypeError) as exc:raise ValueError('Invalid timestamp') from exc

def report(store,profile_id='default',start=None,end=None):
    first,last,days=window(start,end);first_s,last_s=first.isoformat(),last.isoformat()
    daily={(first+timedelta(days=i)).isoformat():{'date':(first+timedelta(days=i)).isoformat(),'events':0,'jobs':set()} for i in range(days)}
    event_states={s:{'status':s,'events':0,'jobs':set()} for s in STATES}
    seen=set();invalid_time=unknown_history=outside=history_rows=valid_history=0;earliest=latest=None
    due={'active_deadlines':0,'unfinished_followups':0,'completed_followups':0}
    invalid_due={'active_deadlines':0,'followups':0};outside_due={'active_deadlines':0,'followups':0}
    with store.connect() as db:
        db.execute('BEGIN')
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Configure a profile first')
        generated=now();total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        counts={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM applications WHERE profile_id=? GROUP BY status',(profile_id,))}
        tracked=sum(counts.values());unknown_current=sum(n for s,n in counts.items() if s not in STATES)
        for row in db.execute('SELECT job_id,new_status,changed_at FROM status_history WHERE profile_id=?',(profile_id,)):
            history_rows+=1;state=row['new_status']
            if state not in event_states:unknown_history+=1;continue
            try:day=_stamp(row['changed_at']).isoformat()
            except ValueError:invalid_time+=1;continue
            valid_history+=1;earliest=min(earliest,day) if earliest else day;latest=max(latest,day) if latest else day
            if not first_s<=day<=last_s:outside+=1;continue
            job=row['job_id'];event_states[state]['events']+=1;event_states[state]['jobs'].add(job)
            daily[day]['events']+=1;daily[day]['jobs'].add(job);seen.add(job)
        for row in db.execute("SELECT deadline FROM applications WHERE profile_id=? AND deadline<>'' AND status IN (?,?,?,?,?)",(profile_id,*ACTIVE)):
            try:day=calendar_day(row['deadline']).isoformat()
            except ValueError:invalid_due['active_deadlines']+=1;continue
            if first_s<=day<=last_s:due['active_deadlines']+=1
            else:outside_due['active_deadlines']+=1
        for row in db.execute('SELECT due,completed FROM followups WHERE profile_id=?',(profile_id,)):
            try:day=calendar_day(row['due']).isoformat()
            except ValueError:invalid_due['followups']+=1;continue
            if first_s<=day<=last_s:due['completed_followups' if row['completed'] else 'unfinished_followups']+=1
            else:outside_due['followups']+=1
    states=[{'status':s,'jobs':counts.get(s,0)} for s in STATES]
    events=[{'status':s,'events':v['events'],'distinct_jobs':len(v['jobs'])} for s,v in event_states.items()]
    by_day=[{'date':v['date'],'events':v['events'],'distinct_jobs':len(v['jobs'])} for v in daily.values()]
    n=sum(r['events'] for r in events)
    assert n==sum(r['events'] for r in by_day)
    assert tracked==sum(r['jobs'] for r in states)+unknown_current
    assert history_rows==n+outside+invalid_time+unknown_history
    return {'version':'outcomes-1','generated_at':generated,'window':{'start':first_s,'end':last_s,'inclusive_days':days,'activity_timezone':'UTC','due_dates':'stored calendar dates'},
            'snapshot':{'local_jobs':total,'explicitly_tracked_jobs':tracked,'untracked_jobs':total-tracked,'unknown_status_jobs':unknown_current,'current_statuses':states},
            'activity':{'events':n,'distinct_jobs':len(seen),'by_status':events,'daily':by_day},'due_items':due,
            'coverage':{'history_rows':history_rows,'valid_known_status_rows':valid_history,'earliest_recorded_utc_day':earliest,'latest_recorded_utc_day':latest,'outside_window_events':outside,'invalid_timestamp_rows_omitted':invalid_time,'unknown_history_status_rows_omitted':unknown_history,'invalid_due_dates_omitted':invalid_due,'outside_window_due_items':outside_due},
            'notice':NOTICE,'privacy':'Aggregate counts only. No job identifiers, titles, employers, URLs, search names, candidate evidence, CVs, task titles or private notes.'}

def export(store,profile_id='default',start=None,end=None,format='json'):
    if format not in ('json','csv'):raise ValueError('Use JSON or CSV for aggregate reports')
    data=report(store,profile_id,start,end)
    if format=='json':return (json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf-8')
    out=io.StringIO(newline='');writer=csv.writer(out,lineterminator='\r\n');writer.writerow(['section','label','value','distinct_jobs','window_start','window_end','generated_at'])
    def row(section,label,value,distinct=''):writer.writerow([section,label,value,distinct,data['window']['start'],data['window']['end'],data['generated_at']])
    row('metadata','notice',data['notice']);row('metadata','privacy',data['privacy']);row('metadata','activity_timezone','UTC');row('metadata','due_dates','stored calendar dates')
    for k,v in data['snapshot'].items():
        if k!='current_statuses':row('snapshot',k,v)
    for x in data['snapshot']['current_statuses']:row('current_status',x['status'],x['jobs'])
    row('activity','all_events',data['activity']['events'],data['activity']['distinct_jobs'])
    for x in data['activity']['by_status']:row('activity_status',x['status'],x['events'],x['distinct_jobs'])
    for x in data['activity']['daily']:row('activity_day',x['date'],x['events'],x['distinct_jobs'])
    for k,v in data['due_items'].items():row('due_snapshot',k,v)
    for k,v in data['coverage'].items():
        if isinstance(v,dict):
            for sub,n in v.items():row('coverage',k+':'+sub,n)
        else:row('coverage',k,'' if v is None else v)
    return out.getvalue().encode('utf-8')
