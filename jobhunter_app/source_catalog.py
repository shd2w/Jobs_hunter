"""Evidence catalog distinct from authoritative executable source approvals."""
from dataclasses import asdict
import json
from .store import dump, now
from .sources import Source, register

PUBLIC_ATS=('greenhouse','lever','ashby','smartrecruiters','workday')


def record(store, lead):
    from .discovery_state import ensure
    ensure(store)
    with store.connect() as db:
        prior=db.execute('SELECT evidence,state FROM source_leads WHERE id=?',(lead.id,)).fetchone()
        evidence=json.loads(prior['evidence']) if prior else []
        item=asdict(lead)
        if item not in evidence: evidence=(evidence+[item])[-100:]
        db.execute('INSERT INTO source_leads VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET evidence=excluded.evidence,updated_at=excluded.updated_at',
            (lead.id,lead.kind,lead.identifier,lead.url,'recognized' if lead.kind else 'unsupported',dump(evidence),now()))
    return lead.id


def activate(store, lead, approve_public_ats=False):
    """An explicit operator family policy permits NEW ATS bindings, never resets a pause."""
    if not lead.kind: return {'state':'unsupported','reason':'No reviewed collection family'}
    source=Source(lead.kind,lead.identifier)
    with store.connect() as db: existing=db.execute('SELECT approved FROM sources WHERE id=?',(source.id,)).fetchone()
    if existing:
        allowed=bool(existing['approved'])
    else:
        allowed=bool(approve_public_ats and lead.kind in PUBLIC_ATS)
        register(store,lead.kind,lead.identifier,allowed)
    state='available' if allowed else 'needs_access'
    with store.connect() as db:
        db.execute('UPDATE source_leads SET state=?,updated_at=? WHERE id=?',(state,now(),lead.id))
        if allowed and not existing: store.audit(db,'autonomy_public_ats_policy',{'source':source.id,'explicit_operator_policy':True})
    return {'state':state,'source_id':source.id,'reason':'Bounded validation collection required' if allowed else 'Existing pause or explicit terms/access approval required'}


def assessed(store, lead_id, result, profile_id="default"):
    valid=result.get('valid_records',0)
    from .matching import contains
    profile=store.profile(profile_id)
    wanted=profile.get('skills',[])+profile.get('matching',{}).get('preferred_title_terms',[])
    with store.connect() as db:
        binding=db.execute('SELECT kind,identifier FROM source_leads WHERE id=?',(lead_id,)).fetchone()
        source_id=Source(binding['kind'],binding['identifier']).id
        records=db.execute('SELECT j.title,j.description FROM jobs j JOIN sightings s ON s.job_id=j.id WHERE s.source=? LIMIT 100',(source_id,)).fetchall()
    hits=[term for term in wanted if any(contains(row['title']+' '+row['description'],term) for row in records)]
    fit='relevant_evidence' if hits else 'low_relevance' if wanted and valid else 'unknown'
    state='active' if valid else 'under_assessment'
    with store.connect() as db: db.execute('UPDATE source_leads SET state=?,updated_at=? WHERE id=?',(state,now(),lead_id))
    return {'state':state,'valid_records':valid,'profile_fit':fit,'evidence_terms':hits,'usefulness':'vacancies_observed_relevance_requires_matching' if valid else 'uncertain_no_usable_vacancy'}
