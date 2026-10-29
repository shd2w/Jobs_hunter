"""Explainable lexical matching. No semantic or eligibility claims are inferred."""
from __future__ import annotations
import re
import unicodedata

# Configurable extension point; compact default technical + transferable lexicon.
SKILLS = {
    'Python': ['python'], 'SQL': ['sql'], 'JavaScript': ['javascript'], 'TypeScript': ['typescript'],
    'Machine learning': ['machine learning', 'maschinelles lernen', 'تعلم الآلة'],
    'Data analysis': ['data analysis', 'datenanalyse', 'تحليل البيانات'],
    'Communication': ['communication', 'kommunikation', 'تواصل'],
    'Project management': ['project management', 'projektmanagement', 'إدارة المشاريع'],
    'Docker': ['docker'], 'AWS': ['aws', 'amazon web services'], 'Git': ['git'],
    'Excel': ['excel'], 'React': ['react'], 'Java': ['java'], 'C++': ['c++'],
    'RAG': ['retrieval augmented generation', 'rag'], 'Leadership': ['leadership', 'führung'],
}


def contains(text: str, phrase: str) -> bool:
    text = unicodedata.normalize('NFKC', text).casefold()
    phrase = unicodedata.normalize('NFKC', phrase).casefold()
    return bool(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text))


def observed_skills(text: str, lexicon: dict | None = None) -> list[str]:
    return [name for name, aliases in (lexicon or SKILLS).items() if any(contains(text, a) for a in aliases)]


def keyword_recommendations(description: str, candidate_evidence: str = '') -> dict:
    found = observed_skills(description)
    supported = [s for s in found if any(contains(candidate_evidence, a) for a in SKILLS[s])]
    return {'observed': found, 'supported': supported,
            'learning_gaps': [s for s in found if s not in supported],
            'notice': 'Keyword mentions are not mandatory requirements. Add only skills supported by your real experience. No CV is changed.'}


def lexical_v1(job: dict, profile: dict) -> dict:
    evidence = '\n'.join(f['text'] for f in profile.get('facts', []) if f.get('verified') is True)
    evidence += '\n' + '\n'.join(profile.get('skills', []))
    keywords = keyword_recommendations(job.get('description', ''), evidence)
    target_skills = profile.get('skills', [])
    matched = [s for s in target_skills if contains(job.get('description', '') + ' ' + job['title'], s)]
    denominator = len(target_skills)
    score = round(100 * len(matched) / denominator) if denominator else None
    uncertainties = ['Work authorization, qualifications, salary and language eligibility require review.']
    excluded = [term for term in profile.get('excluded_title_terms', []) if contains(job['title'], term)]
    return {'method': 'deterministic lexical v1', 'score_percent': score,
            'matched_profile_skills': matched, 'profile_skill_count': denominator,
            'eligibility': 'excluded_by_config' if excluded else 'needs_review',
            'exclusion_evidence': excluded, 'uncertainties': uncertainties,
            'keywords': keywords, 'explanation': f'{len(matched)} of {denominator} configured skills mentioned; not an AI suitability score.'}


MATCHER_VERSION = 'deterministic contextual lexical v2.2'


def match_job(job: dict, profile: dict) -> dict:
    """Retain the skill-count contract; add a distinct preference ranking signal."""
    from hashlib import sha256
    import json
    from .match_config import validate,DEFAULT_WEIGHTS
    from .requirements import extract,PACK_VERSION,MAX_EVIDENCE_ROWS
    from .eligibility_context import review_context,VERSION as CONTEXT_VERSION
    config=validate(profile.get('matching',{}),profile.get('skills',[]))
    result=lexical_v1(job,profile)
    requirements=extract(job.get('description',''),profile)
    checks=[]
    for term in profile.get('excluded_title_terms',[]):
        checks.append({'kind':'excluded_title','term':term,'state':'exclude' if contains(job['title'],term) else 'not_observed','field':'title','evidence':job['title'] if contains(job['title'],term) else ''})
    norm=lambda x:unicodedata.normalize('NFKC',x).casefold().strip()
    for term in config.get('excluded_companies',[]):
        hit=bool(job.get('company')) and norm(job['company'])==norm(term)
        checks.append({'kind':'excluded_company','term':term,'state':'exclude' if hit else 'not_observed' if job.get('company') else 'unknown','field':'company','evidence':job.get('company','') if hit else ''})
    for term in config.get('excluded_location_terms',[]):
        value=job.get('location','');hit=contains(value,term)
        checks.append({'kind':'excluded_location','term':term,'state':'exclude' if hit else 'not_observed' if value else 'unknown','field':'location','evidence':value if hit else ''})
    listing=job['title']+'\n'+job.get('description','')
    for term in config.get('required_listing_terms',[]):
        hit=contains(listing,term)
        checks.append({'kind':'required_listing_mention','term':term,'state':'observed_mention' if hit else 'unknown','field':'title/description','evidence':term if hit else '',
                       'notice':'Presence is only a text mention, not a positive requirement or eligibility finding; absence is not proof of failure.'})
    exclusions=[x for x in checks if x['state']=='exclude']
    result['eligibility']='excluded_by_config' if exclusions else 'needs_review'
    result['exclusion_evidence']=[x['term'] for x in exclusions]
    dimensions={};skills=profile.get('skills',[]);skill_weights=config.get('skill_weights',{})
    if skills:
        weighted=[]
        for skill in skills:
            canonical=next((s for s,a in SKILLS.items() if norm(skill)==norm(s)),skill)
            aliases=SKILLS.get(canonical,[skill])
            mentions=[x for x in requirements if norm(x['skill'])==norm(canonical)]
            positive=any(x['classification'] in ('required','preferred','mentioned') for x in mentions)
            # Titles contain no explicit requirements; count a token/alias mention only.
            hit=positive or any(contains(job['title'],a) for a in aliases)
            weighted.append({'skill':skill,'weight':skill_weights.get(skill,1),'observed_positive_or_unqualified_mention':hit})
        total=sum(x['weight'] for x in weighted)
        dimensions['skills']={'score':sum(x['weight'] for x in weighted if x['observed_positive_or_unqualified_mention'])/total,'items':weighted,'known':bool(listing.strip())}
    for field,key in (('title','preferred_title_terms'),('location','preferred_location_terms')):
        terms=config.get(key,[])
        if terms:
            value=job.get(field,'');hits=[x for x in terms if contains(value,x)]
            dimensions[field]={'score':len(hits)/len(terms),'matched':hits,'configured':terms,'known':bool(value),'notice':'Missing field contributes zero; unknown is not an exclusion.'}
    weights={**DEFAULT_WEIGHTS,**config.get('weights',{})}
    denominator=sum(weights[k] for k in dimensions)
    ranking=round(100*sum(v['score']*weights[k] for k,v in dimensions.items())/denominator,2) if denominator else None
    for k,v in dimensions.items():v['dimension_weight']=weights[k]
    fingerprint=lambda value:sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    result.update({'method':MATCHER_VERSION,'eligibility_context':review_context(job),'requirements':requirements,'requirements_truncated':len(requirements)>=MAX_EVIDENCE_ROWS,'hard_constraint_checks':checks,
                   'ranking':{'score_percent':ranking,'dimensions':dimensions,'weight_denominator':denominator,'excluded':bool(exclusions),
                              'notice':'Weighted lexical preferences only, not suitability, probability or legal eligibility. Unknown active fields remain in the denominator. Hard exclusions always take precedence.'},
                   'fingerprints':{'job':fingerprint(job),'profile':fingerprint(profile),'matcher':MATCHER_VERSION,'language_pack':PACK_VERSION,'eligibility_context':CONTEXT_VERSION},
                   'ats_advice':{'observed_required_skills':sorted({x['skill'] for x in requirements if x['classification']=='required'}),
                                 'not_recorded_required_mentions':sorted({x['skill'] for x in requirements if x['classification']=='required' and x['candidate_evidence']=='not_recorded'}),
                                 'notice':'Review the cited clauses; add only accurate evidence you can support. Not recorded does not mean unable. No CV is changed.'}})
    if len(requirements)>=MAX_EVIDENCE_ROWS: result['uncertainties'].append('Context evidence limited to 300 rows; later clauses may not contribute to weighted preference evidence. Review the full listing.')
    result['uncertainties'] += ['Requirement cues cover only narrow English/German/Arabic phrases. Mixed clauses, proficiency, years, degrees, remote jurisdictions, salary and legal eligibility need human review.']
    result['explanation'] += ' Weighted lexical preferences: '+(str(ranking)+'%' if ranking is not None else 'not configured')+'. '+('Excluded by explicit settings; ranking cannot override this.' if exclusions else 'No proven eligibility conclusion.')
    return result
