"""Explainable bounded coverage and comparable source-quality observations."""
import json
from .store import now


def coverage(tasks):
    cells={}
    for task in tasks:
        query=task.get('query')
        if not query: continue
        key=(query['text'],query['region'],query['language'])
        cells.setdefault(key,[]).append(task)
    result=[]
    for (text,region,language),attempts in cells.items():
        usable=sum(x.get('result',{}).get('valid_records',0) for x in attempts)
        result.append({'query':text,'region':region,'language':language,
            'usable_records':usable,'states':[x['status'] for x in attempts],
            'gap':not bool(usable),'next_action':'Try remaining generated variant/source when eligible' if not usable else 'Due refresh only',
            'notice':'Bounded observed query scope; not market recall or legal eligibility'})
    return result


def priority(task, history=()):
    # Exploration remains explicit: unknown sources never penalized for zero history.
    if task.get('lead_id'): return (0,0,task['id'])
    prior=[x for x in history if x['source_id']==task['source_id']]
    yield_count=sum(x.get('result',{}).get('new_confirmed_relevant_groups',0) for x in prior)
    return (1 if not prior else 2,-min(yield_count,10),task['order'])


def observe(store, source_id, signature, result=None, error=None):
    result=result or {}
    outcome='failed' if error else 'invalid' if result.get('invalid',0) else 'valid_empty' if not result.get('valid_records',0) else 'usable'
    with store.connect() as db:
        db.execute('INSERT INTO search_quality VALUES(?,?,?,?,?,?,?)',
            (source_id,signature,now(),result.get('valid_records',0),result.get('invalid',0),outcome,str(error or '')[:100]))
        recent=db.execute('SELECT outcome FROM search_quality WHERE source_id=? AND signature=? ORDER BY observed_at DESC LIMIT 3',(source_id,signature)).fetchall()
    degraded=len(recent)==3 and all(x['outcome'] in ('invalid','failed') for x in recent)
    return {'state':'degraded' if degraded else 'observed','outcome':outcome,
        'reason':'three comparable failed/invalid observations' if degraded else 'insufficient degradation evidence; empty is not broken'}
