"""Authoritative evaluation boundary. AI scores and lexical ranks are NOT equivalent.

Local batch matching retains its public matches contract. AI is explicit per request;
no scheduler, GET or fallback can authorize a provider. Legacy delivery stays outside.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import uuid
from filelock import FileLock, Timeout
from contextlib import contextmanager
from .store import dump, now

VERSION = 'evaluation-service-1'
WEIGHTS = {'skills_match': .30, 'education_match': .20, 'location': .20, 'language': .20, 'growth': .10}
POLICIES = ('accept_all', 'reject_b1_plus', 'reject_b2_plus_only', 'reject_unless_bilingual')

@dataclass(frozen=True)
class EvaluationOptions:
    method: str = 'local'
    allow_provider: bool = False
    fallback: bool = False
    threshold: float = 3.5
    german_policy: str = 'accept_all'

    def __post_init__(self):
        if self.method not in ('local', 'ai') or any(type(x) is not bool for x in (self.allow_provider, self.fallback)):
            raise ValueError('Invalid evaluation method or consent')
        if type(self.threshold) not in (float, int) or not math.isfinite(self.threshold) or not 1 <= self.threshold <= 5:
            raise ValueError('AI threshold must be finite and between 1 and 5')
        if self.german_policy not in POLICIES:
            raise ValueError('Invalid German policy')

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) - {'method','allow_provider','fallback','threshold','german_policy'}:
            raise ValueError('Unknown evaluation option')
        return cls(**value)


def weighted_score(scores):
    if not isinstance(scores, dict) or any(type(scores.get(k)) not in (int,float) or not math.isfinite(scores[k]) or not 1 <= scores[k] <= 5 for k in WEIGHTS):
        raise ValueError('Invalid AI scoring dimensions')
    return round(sum(scores[k]*w for k,w in WEIGHTS.items()), 1)


def apply_policy(evaluation, job, policy='accept_all'):
    """Vacancy preference, not proof of candidate proficiency or legal eligibility."""
    if policy not in POLICIES: raise ValueError('Invalid German policy')
    result = dict(evaluation)
    level = result.get('german_level_required', 'none')
    reject = (policy == 'reject_b1_plus' and level in ('B1','B2+')) or (policy == 'reject_b2_plus_only' and level == 'B2+')
    if policy == 'reject_unless_bilingual' and (level in ('B1','B2+') or result.get('german_required')):
        jd = job.get('description','').lower()
        reject = not any(x in jd for x in ('english','englisch'))
    result['german_policy'] = policy
    result['policy_rejected'] = bool(reject)
    if reject:
        result['pre_policy_score'] = result['global_score']
        result.update(global_score=0, recommendation='skip_german')
    return result


def evaluate_prepared(job, evaluator, german_policy='accept_all'):
    """Common AI/policy entry point for legacy and SQLite callers.

    Evaluator owns strict model response validation and report compatibility.
    Compatible injected evaluators may return a minimal legacy result; never used
    as a way around validation of actual model JSON.
    """
    result = evaluator.evaluate(job)
    if not result.get('success'):
        return {k:v for k,v in result.items() if k != 'raw_response'}
    score = result.get('global_score')
    if type(score) not in (int,float) or not math.isfinite(score) or not 1 <= score <= 5:
        return {'success':False, 'error':'Invalid evaluation score; job remains pending', 'url':job.get('url','')}
    if 'scores' in result: result['global_score'] = weighted_score(result['scores'])
    result = apply_policy(result, job, german_policy)
    result.update(evaluation_method='ai', score_scale='1–5 weighted suitability; policy rejection 0', service_version=VERSION)
    return result


def candidate_context(profile):
    """Explicit adapter: no ambient YAML/CV reads and no invented candidate facts."""
    cfg = profile.get('matching',{})
    facts = [f['text'] for f in profile.get('facts',[]) if f.get('verified') is True]
    return {
        'candidate': {'full_name':profile.get('name','Not provided')},
        'skills': {'technical':profile.get('skills',[]), 'non_technical':[]},
        'languages':profile.get('languages',[]) or 'Not provided',
        'preferences': {'locations':cfg.get('preferred_location_terms',[])},
        'target_roles': {'primary':cfg.get('preferred_title_terms',[])},
    }, '\n'.join(facts) or 'No verified candidate narrative supplied. Skills/languages are explicit profile entries; other facts unknown.'


def make_evaluator(profile):
    from agents.evaluator import Evaluator
    context, narrative = candidate_context(profile)
    return Evaluator.from_context(context, narrative)


def local_result(job, profile):
    from .matching import match_job
    return match_job(job, profile)


def local_batch(store, profile_id='default', pending_only=False):
    from .matching import MATCHER_VERSION
    with store.connect() as db:
        p = db.execute('SELECT data FROM profiles WHERE id=?',(profile_id,)).fetchone()
        if not p: raise ValueError('Configure a profile before matching')
        profile = json.loads(p[0]); count = 0
        query = 'SELECT j.id,j.data FROM jobs j LEFT JOIN matches m ON m.job_id=j.id AND m.profile_id=? WHERE m.job_id IS NULL' if pending_only else 'SELECT id,data FROM jobs'
        for row in db.execute(query,(profile_id,) if pending_only else ()).fetchall():
            result = local_result(json.loads(row['data']),profile)
            db.execute('INSERT INTO matches VALUES(?,?,?,?) ON CONFLICT(profile_id,job_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (profile_id,row['id'],dump(result),now())); count += 1
        store.audit(db,'contextual_matching_completed',{'profile_id':profile_id,'jobs':count})
    return {'evaluated':count,'method':MATCHER_VERSION}


def fingerprint(job, profile, options):
    # Exclude DB observation metadata and original local filesystem references.
    job = {k:v for k,v in job.items() if k not in ('id','first_seen','last_seen','match','evaluation','status','notes','deadline')}
    profile = {k:v for k,v in profile.items() if k != 'original_cv'}
    return hashlib.sha256(dump([VERSION,job,profile,options.__dict__]).encode()).hexdigest()


def _exists(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='evaluation_meta'").fetchone())


def initialize(store):
    """Only an explicit evaluation action creates this backed-up v1 extension."""
    with store.connect() as db:
        if _exists(db):
            if db.execute('SELECT version FROM evaluation_meta').fetchone()[0] != 1: raise ValueError('Unsupported evaluation schema')
            return
    store.backup(str(store.path)+'.before-evaluation-v1-'+uuid.uuid4().hex+'.bak')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS evaluation_meta(version INTEGER NOT NULL)')
        if not db.execute('SELECT 1 FROM evaluation_meta').fetchone(): db.execute('INSERT INTO evaluation_meta VALUES(1)')
        db.execute('CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,job_id TEXT NOT NULL,fingerprint TEXT NOT NULL,created_at TEXT NOT NULL,data TEXT NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS evaluations_job ON evaluations(profile_id,job_id,created_at)')


def latest(store, job_id, profile_id='default'):
    with store.connect() as db:
        if not _exists(db): return None
        row = db.execute('SELECT data FROM evaluations WHERE profile_id=? AND job_id=? ORDER BY rowid DESC LIMIT 1',(profile_id,job_id)).fetchone()
    if not row: return None
    result = observed_status(store,json.loads(row[0]))
    result['stale'] = result['fingerprint'] != fingerprint(store.job(job_id),store.profile(profile_id),EvaluationOptions.parse(result['options']))
    return result


def observed_status(store, result):
    if result.get('status') != 'running': return result
    try:
        with FileLock(str(store.path)+'.evaluation.lock',timeout=0):
            result = dict(result)
            result['status'] = 'partial'
            result['error'] = {'code':'evaluation_interrupted','message':'No evaluator owns this running receipt; completion was not committed. Retry explicitly.'}
    except Timeout:
        pass
    return result


@contextmanager
def evaluation_lock(store):
    try:
        with FileLock(str(store.path)+'.evaluation.lock',timeout=0):
            yield
    except Timeout as exc:
        raise ValueError('Another evaluation is running; wait for it to finish') from exc


def evaluate(store, job_id, profile_id='default', options=None):
    options = options or EvaluationOptions()
    if not isinstance(options,EvaluationOptions): raise ValueError('Expected evaluation options')
    # One cross-interface/cross-process boundary, not a second HTTP-only lock.
    with evaluation_lock(store):
        job = store.job(job_id); profile = store.profile(profile_id)
        if not profile: raise ValueError('Configure a profile before evaluation')
        initialize(store)
        stamp = fingerprint(job,profile,options)
        result = {'schema_version':1,'service_version':VERSION,'job_id':job_id,'profile_id':profile_id,
                  'fingerprint':stamp,'options':dict(options.__dict__),'started_at':now(),
                  'requested_method':options.method,'method':None,'status':'pending','score':None,'score_scale':None,
                  'threshold':options.threshold if options.method=='ai' else None,'warnings':[],'error':None}
        identity = uuid.uuid4().hex
        result['finished_at'] = None
        result['status'] = 'running'
        with store.connect() as db:
            # Only this process can own the evaluation lock. Leftover running
            # receipts are interrupted, not completed, after a prior crash.
            for old in db.execute("SELECT id,data FROM evaluations WHERE json_extract(data,'$.status')='running'").fetchall():
                prior = json.loads(old['data'])
                if prior.get('status') == 'running':
                    prior.update(status='partial',finished_at=now())
                    prior.setdefault('warnings',[]).append('Previous process stopped before evaluation completion.')
                    db.execute('UPDATE evaluations SET data=? WHERE id=?',(dump(prior),old['id']))
            db.execute('INSERT INTO evaluations VALUES(?,?,?,?,?,?)',(identity,profile_id,job_id,stamp,result['started_at'],dump(result)))
        local = local_result(job,profile)
        if options.method == 'local':
            result.update(method='local',status='completed_local',local=local,score_scale='lexical ranking only; not AI suitability')
        elif not options.allow_provider:
            result['status'] = 'pending'
            result['error'] = {'code':'provider_consent_required','message':'Explicit provider consent required; no provider was called.'}
        elif not job.get('description'):
            result['status'] = 'pending'
            result['error'] = {'code':'description_required','message':'Description unavailable; retrieval is a separate stage.'}
        elif local.get('eligibility') == 'excluded_by_config':
            result.update(status='completed_local',method='local',local=local,classification='excluded',
                          score_scale='hard preference exclusion; AI not called')
        else:
            try:
                evaluated = evaluate_prepared(job,make_evaluator(profile),options.german_policy)
                if not evaluated.get('success'): raise ValueError('AI evaluation failed')
                result.update(method='ai',status='completed_ai',ai=evaluated,score=evaluated['global_score'],
                              score_scale='1–5 weighted suitability; policy rejection 0',
                              classification='rejected' if evaluated.get('policy_rejected') else 'above_threshold' if evaluated['global_score']>=options.threshold else 'below_threshold')
            except Exception as exc:
                # Raw provider exceptions may contain credentials or request bodies.
                result['error'] = {'code':'ai_evaluation_failed','type':type(exc).__name__,
                                   'message':'AI provider unavailable or response invalid; inspect local provider setup.'}
                if options.fallback:
                    result.update(method='local',status='completed_fallback',local=local,score_scale='lexical ranking only; not comparable to AI 1–5')
                else: result['status'] = 'failed'
        # A profile/job changed during a slow provider request cannot become current.
        if fingerprint(store.job(job_id),store.profile(profile_id),options) != stamp:
            result.update(status='partial'); result['warnings'].append('Inputs changed during evaluation; result is stale.')
        result['finished_at'] = now()
        with store.connect() as db:
            db.execute('UPDATE evaluations SET data=? WHERE id=?',(dump(result),identity))
            if result['status'] in ('completed_local','completed_fallback') and 'local' in result:
                db.execute('INSERT INTO matches VALUES(?,?,?,?) ON CONFLICT(profile_id,job_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(profile_id,job_id,dump(result['local']),now()))
            store.audit(db,'evaluation_completed',{'profile_id':profile_id,'job_id':job_id,'status':result['status'],'method':result['method']})
        # Persistence errors intentionally propagate; never return false success.
        return result


def summary(store, profile_id='default'):
    """Latest-per-job counts, explicitly distinguishing stale and unrequested work."""
    with store.connect() as db:
        total = db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        if not _exists(db): return {'not_requested':total,'status_counts':{},'stale':0}
        rows = db.execute('SELECT e.data,j.data AS job_data FROM evaluations e JOIN jobs j ON j.id=e.job_id WHERE e.profile_id=? AND e.rowid IN (SELECT MAX(rowid) FROM evaluations WHERE profile_id=? GROUP BY job_id)',(profile_id,profile_id)).fetchall()
        profile = store.profile(profile_id)
    counts={};stale=0
    for row in rows:
        r=observed_status(store,json.loads(row['data']))
        changed=r['fingerprint']!=fingerprint(json.loads(row['job_data']),profile,EvaluationOptions.parse(r['options']))
        if changed:stale+=1
        else:counts[r['status']]=counts.get(r['status'],0)+1
    return {'not_requested':total-len(rows),'status_counts':counts,'stale':stale,
            'notice':'Latest evaluation per job; local and AI are separate methods. Not requested is not a failed AI request.'}
