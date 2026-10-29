"""Explicit private fact-to-listing links; no independent semantic verification."""
from copy import deepcopy
from hashlib import sha256
import json
import re

FORMAT=1
NOTICE=('User-attested connections, not independent fact, semantic relevance, qualification or eligibility verification. '
        'Exact excerpts can be incomplete, negated or ambiguous; review the full original listing. '
        'Reasons remain private pack metadata, never new candidate claims or cover prose.')


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def fact_id(fact):
    return digest({k:fact[k] for k in ('text','source','verified')})


def preview(job,profile):
    from .documents import _authorized,_text
    if not isinstance(job,dict) or not isinstance(profile,dict):raise ValueError('Expected job and profile objects')
    if not _text(profile.get('name'),300):raise ValueError('Configure a candidate name first')
    if not _text(job.get('title'),1000) or not _text(job.get('company'),1000):raise ValueError('Employer or role mismatch')
    target={k:job.get(k,'') for k in ('title','company','url','description')}
    if any(not isinstance(v,str) or len(v)>200000 or any(0xD800<=ord(c)<=0xDFFF for c in v) for v in target.values()):raise ValueError('Invalid listing text')
    facts=[{'id':fact_id(f),'text':f['text'],'source':f['source']} for f in _authorized(profile)]
    body={'format':FORMAT,'target':target,'candidate_name':profile['name'].strip(),'facts':facts}
    return {**body,'preview_fingerprint':digest(body),'limit':3,'quote_limit':1000,'reason_limit':1000,'notice':NOTICE}


def resolve(job,profile,mapping):
    from .documents import _authorized,_text
    if (not isinstance(mapping,dict) or set(mapping)!={'format','preview_fingerprint','confirmed','links'}
            or type(mapping['format']) is not int or mapping['format']!=FORMAT or mapping['confirmed'] is not True):
        raise ValueError('Use an explicitly confirmed format-1 evidence map')
    p=preview(job,profile)
    fp=mapping['preview_fingerprint']
    if not isinstance(fp,str) or not re.fullmatch('[a-f0-9]{64}',fp) or fp!=p['preview_fingerprint']:
        raise ValueError('Evidence preview changed; refresh and review the links')
    links=mapping['links']
    if not isinstance(links,list) or not 1<=len(links)<=3:raise ValueError('Map one to three distinct verified facts')
    authorized={fact_id(f):f for f in _authorized(profile)};selected=[];bound=[];seen=set()
    for link in links:
        if not isinstance(link,dict) or set(link)!={'fact_id','field','start','end','quote','reason'}:raise ValueError('Invalid evidence link fields')
        fid=link['fact_id'];field=link['field'];start,end=link['start'],link['end']
        if not isinstance(fid,str) or fid not in authorized or fid in seen:raise ValueError('Choose distinct current verified facts')
        if not isinstance(field,str) or field not in ('title','description'):raise ValueError('Link to listing title or description')
        text=p['target'][field]
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text) or end-start>1000:raise ValueError('Invalid listing excerpt offsets')
        if not _text(link['quote'],1000,multiline=True) or text[start:end]!=link['quote']:raise ValueError('Listing excerpt must match exact current text and offsets')
        if not _text(link['reason'],1000,multiline=True):raise ValueError('Explain the evidence connection in at most 1000 characters')
        seen.add(fid);fact=authorized[fid];selected.append(deepcopy(fact));bound.append({**deepcopy(link),'text':fact['text'],'source':fact['source']})
    return selected,{'format':FORMAT,'status':'user_attested','preview_fingerprint':fp,'links':bound,'notice':NOTICE}


def automatic(job,profile,selected=None):
    """Compatibility only. Skill overlap is a cue, never a relevance verdict."""
    from .documents import _authorized
    from .matching import observed_skills
    skills=set(observed_skills((job.get('title','') if isinstance(job.get('title',''),str) else '')+'\n'+(job.get('description','') if isinstance(job.get('description',''),str) else '')))
    records=_authorized(profile)
    overlap=lambda f:sorted(skills.intersection(observed_skills(f['text'])))
    if selected is None:records=sorted([f for f in records if overlap(f)],key=lambda f:-len(overlap(f)))[:3]
    else:
        bytext={f['text']:f for f in records}
        if not isinstance(selected,list) or not 1<=len(selected)<=3 or not all(isinstance(t,str) and t in bytext for t in selected) or len(set(selected))!=len(selected):raise ValueError('Select distinct verified facts')
        records=[bytext[t] for t in selected]
    if not records or any(not overlap(f) for f in records):raise ValueError('No recognized listing-skill cue for selected evidence; use an explicit evidence map')
    return deepcopy(records),{'format':FORMAT,'status':'lexical_cues_only','links':[{'fact_id':fact_id(f),'skills':overlap(f)} for f in records],
        'notice':'Compatibility selection from recognized skill mentions only; not an explicit user mapping or semantic relevance assessment. Negation and context need human review. Use an explicit evidence map for a reviewed connection.'}


def load(path):
    """Bound private CLI input before JSON parsing; never interpret paths in reasons."""
    from pathlib import Path
    try:
        with Path(path).open('rb') as stream:raw=stream.read(65537)
        if len(raw)>65536:raise ValueError('Evidence map file exceeds 64 KiB')
        value=json.loads(raw.decode('utf-8-sig'))
        if not isinstance(value,dict):raise ValueError('Expected an evidence map object')
        return value
    except (UnicodeError,RecursionError,json.JSONDecodeError) as exc:
        raise ValueError('Invalid evidence map JSON') from None
