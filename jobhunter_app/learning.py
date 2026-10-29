"""Read-only contextual guidance over stored matches, not market/ability inference."""
from hashlib import sha256
import json
from .matching import MATCHER_VERSION
from .requirements import PACK_VERSION, MAX_EVIDENCE_ROWS
from .eligibility_context import VERSION as CONTEXT_VERSION
from .validation import public_url

VERSION = 'contextual skill guidance v1'
LABELS = ('required','preferred','mixed','ambiguous','mentioned','not_required','unclassified')
CLAUSE_LABELS = {'required','preferred','not_required','ambiguous','mentioned'}
SAMPLE_LIMIT = 8
EXCERPT_LIMIT = 600
SCOPE = 'Current locally matched, non-excluded vacancies; keyword mentions, not mandatory requirements.'
NOTICE = ('Narrow rule-based listing cues, not verified employer requirements, proficiency, eligibility or market demand. '
          'Not recorded does not mean unable. Context buckets count distinct vacancies and sum to the skill mention count; '
          'counts overlap across skills. Samples are limited; review the full original listing. No CV is changed.')


def fingerprint(value):
    try:
        return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()
    except (ValueError, TypeError, UnicodeError):
        return None


def object_json(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def _rows(match, description):
    raw = match.get('requirements')
    if not isinstance(raw, list):
        return [], 0, True
    invalid, rows, seen = 0, [], set()
    for row in raw[:MAX_EVIDENCE_ROWS]:
        if (not isinstance(row, dict) or not isinstance(row.get('classification'),str) or row['classification'] not in CLAUSE_LABELS
                or not isinstance(row.get('skill'), str) or not row['skill'].strip()
                or type(row.get('start')) is not int or type(row.get('end')) is not int
                or not 0 <= row['start'] < row['end'] <= len(description)
                or not isinstance(row.get('evidence'), str) or description[row['start']:row['end']] != row['evidence']
                or row.get('candidate_evidence') not in ('declared_skill','verified_fact_mention','not_recorded')
                or not isinstance(row.get('cue_packs'), list)
                or any(not isinstance(x,str) or x not in ('en','de','ar') for x in row['cue_packs'])):
            invalid += 1
            continue
        key = (row['skill'],row['start'],row['end'],row['classification'])
        if key not in seen:
            rows.append(row)
            seen.add(key)
    limited = (match.get('requirements_truncated') is not False or len(raw) >= MAX_EVIDENCE_ROWS
               or invalid > 0)
    return rows, invalid, limited


def _guide(counts):
    if counts['required']:
        tier, rank = 'required_cues', 0
        action = 'Review the required-cue excerpts against your own evidence. If relevant to your goals, practise a demonstrable task; record only evidence you can support.'
    elif counts['preferred']:
        tier, rank = 'preferred_cues', 1
        action = 'Check the preferred-cue excerpts and your goals before choosing optional practice. These cues are not proof of a mandatory qualification.'
    elif counts['mixed'] or counts['ambiguous'] or counts['unclassified']:
        tier, rank = 'clarify_first', 2
        action = 'Clarify the full listing and your existing evidence before deciding what to study. Mixed, ambiguous or unavailable context is not promoted to a requirement.'
    elif counts['mentioned']:
        tier, rank = 'mention_only', 3
        action = 'Ask whether these plain mentions matter to your target roles. A mention alone does not establish a requirement or a personal skill deficit.'
    else:
        tier, rank = 'negated_only', 4
        action = 'No study priority is inferred from these negated-only mentions. Review the original clauses and your personal goals instead.'
    rationale = ('Distinct vacancy buckets: ' + ', '.join(f'{k}={counts[k]}' for k in LABELS) +
                 '. Display order uses required cues, then preferred cues, clarify-first, mention-only, negated-only; '
                 'within tiers: required count, preferred count, total mentions descending, then skill name. Not a suitability score.')
    return {'tier':tier, 'order_tier':rank, 'rationale':rationale}, action


def report(store, profile_id='default'):
    totals = {}
    coverage = {'matched_rows':0, 'excluded_vacancies':0, 'invalid_match_rows':0,
                'current_context_vacancies':0, 'stale_or_unverifiable_context_vacancies':0,
                'limited_context_vacancies':0, 'invalid_evidence_rows':0,
                'sample_limit_per_skill':SAMPLE_LIMIT, 'excerpt_character_limit':EXCERPT_LIMIT}
    denominator = 0
    with store.connect() as db:
        # One consistent read snapshot; no rematch, cache write, audit event or profile change.
        db.execute('BEGIN')
        p = db.execute('SELECT data FROM profiles WHERE id=?',(profile_id,)).fetchone()
        profile = object_json(p['data']) if p else None
        profile_fp = fingerprint(profile) if profile is not None else None
        coverage['profile_present'] = profile is not None
        total_jobs = db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        query = '''SELECT m.job_id,m.data AS match_data,j.data AS job_data
                   FROM matches m JOIN jobs j ON j.id=m.job_id WHERE m.profile_id=? ORDER BY m.job_id'''
        for record in db.execute(query,(profile_id,)):
            coverage['matched_rows'] += 1
            match, job = object_json(record['match_data']), object_json(record['job_data'])
            if match is None or job is None:
                coverage['invalid_match_rows'] += 1
                continue
            if match.get('eligibility') == 'excluded_by_config':
                coverage['excluded_vacancies'] += 1
                continue
            keywords = match.get('keywords')
            gaps = keywords.get('learning_gaps') if isinstance(keywords, dict) else None
            if (not isinstance(gaps, list) or any(not isinstance(s,str) or not s.strip() or
                    any(0xD800 <= ord(c) <= 0xDFFF for c in s) for s in gaps)):
                coverage['invalid_match_rows'] += 1
                continue
            denominator += 1
            gaps = sorted({s for s in gaps if isinstance(s,str) and s.strip()})
            fp = match.get('fingerprints')
            job_fp = fingerprint(job)
            fresh = (profile_fp is not None and job_fp is not None and match.get('method') == MATCHER_VERSION and isinstance(fp,dict)
                     and fp.get('job') == job_fp and fp.get('profile') == profile_fp
                     and fp.get('matcher') == MATCHER_VERSION and fp.get('language_pack') == PACK_VERSION
                     and fp.get('eligibility_context') == CONTEXT_VERSION)
            coverage['current_context_vacancies' if fresh else 'stale_or_unverifiable_context_vacancies'] += 1
            description = job.get('description','')
            rows, invalid, limited = _rows(match,description) if fresh and isinstance(description,str) else ([],0,True)
            coverage['invalid_evidence_rows'] += invalid
            if fresh and limited:
                coverage['limited_context_vacancies'] += 1
            by_skill = {}
            for row in rows:
                by_skill.setdefault(row['skill'],[]).append(row)
            for skill in gaps:
                item = totals.setdefault(skill, {'vacancies':0, 'contexts':dict.fromkeys(LABELS,0),
                                                'buckets':{k:[] for k in LABELS}, 'source_rows':0})
                item['vacancies'] += 1
                evidence = by_skill.get(skill,[])
                labels = {r['classification'] for r in evidence}
                category = ('unclassified' if not fresh or limited or not labels else
                            next(iter(labels)) if len(labels)==1 else 'mixed')
                item['contexts'][category] += 1
                try:
                    url = public_url(job.get('url',''))
                except ValueError:
                    url = ''
                for row in evidence:
                    item['source_rows'] += 1
                    if len(item['buckets'][category]) >= 2:
                        continue
                    end = min(row['end'],row['start']+EXCERPT_LIMIT)
                    item['buckets'][category].append({
                        'job_id':record['job_id'], 'title':job.get('title',''), 'company':job.get('company',''),
                        'url':url, 'field':'description', 'skill':skill, 'classification':row['classification'],
                        'vacancy_context':category, 'candidate_evidence':row['candidate_evidence'],
                        'evidence':description[row['start']:end], 'start':row['start'], 'end':end,
                        'clause_end':row['end'], 'excerpt_truncated':end<row['end'],
                        'cue_packs':row['cue_packs'],
                        'notice':'Label applies to the stored full clause, potentially with an inherited heading; inspect the full original. Unclassified context is not used as a positive priority.'})
        coverage['unmatched_vacancies'] = max(0,total_jobs-coverage['matched_rows'])
    priorities = []
    for skill, item in sorted(totals.items(),key=lambda x:(-x[1]['vacancies'],x[0])):
        # Balanced, deterministic samples, not an exhaustive list of clauses/jobs.
        samples = []
        for i in range(2):
            for label in LABELS:
                if i < len(item['buckets'][label]) and len(samples)<SAMPLE_LIMIT:
                    samples.append(item['buckets'][label][i])
        guidance, next_step = _guide(item['contexts'])
        priorities.append({'skill':skill, 'vacancies':item['vacancies'], 'next_step':next_step,
                           'contexts':item['contexts'], 'guidance':guidance, 'evidence_samples':samples,
                           'evidence_coverage':{'sampled_excerpts':len(samples), 'observed_valid_clause_rows':item['source_rows'],
                                                'samples_limited':len(samples)<item['source_rows'],
                                                'unclassified_vacancies':item['contexts']['unclassified']}})
    ordered = sorted(priorities,key=lambda p:(p['guidance']['order_tier'],-p['contexts']['required'],
                                             -p['contexts']['preferred'],-p['vacancies'],p['skill'].casefold(),p['skill']))
    from .learning_resources import attach
    catalog = attach(priorities)
    from .learning_progress import offer_fingerprint
    for priority in priorities:
        priority['learning_options']['plan_fingerprint'] = offer_fingerprint(priority)
    return {'vacancies_reviewed':denominator, 'scope':SCOPE, 'priorities':priorities,
            'method':VERSION, 'contextual_order':[p['skill'] for p in ordered], 'coverage':coverage,
            'notice':NOTICE, 'resource_catalog':catalog, 'capabilities':{'contextual_guidance':True, 'verified_resources':catalog['available'],
                                           'exercise_catalog':catalog['available'], 'learning_progress':True}}
