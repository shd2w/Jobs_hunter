"""Conservative local requirement cues with exact evidence; not semantic parsing."""
import re
from .matching import SKILLS,contains

PACK_VERSION='en-de-ar-cues-1'
MAX_EVIDENCE_ROWS=300
PACKS={
 'en':{'required':[r'\brequired\b',r'\bmandatory\b',r'\bmust\b',r'\bessential\b'],
       'preferred':[r'\bpreferred\b',r'\bdesirable\b',r'\bnice.to.have\b',r'\boptional\b'],
       'not_required':[r'\bnot\s+(?:strictly\s+)?required\b',r'\bno\b[^,;]{0,50}?\brequired\b',r'\bneed not\b',r'\bnot\s+(?:strictly\s+)?(?:mandatory|essential)\b'],
       'head_required':r'^(?:requirements|required skills|essential skills|must have)\s*:\s*$',
       'head_preferred':r'^(?:preferred skills|nice to have|desirable skills)\s*:\s*$'},
 'de':{'required':[r'\berforderlich\b',r'\bzwingend\b',r'\bvoraussetzung\b',r'\bmuss\b'],
       'preferred':[r'\bwünschenswert\b',r'\bvon vorteil\b',r'\boptional\b'],
       'not_required':[r'\bnicht\s+(?:zwingend\s+)?erforderlich\b',r'\bkeine?\b[^,;]{0,50}?\berforderlich\b',r'\bnicht\s+zwingend\b'],
       'head_required':r'^(?:anforderungen|voraussetzungen)\s*:\s*$',
       'head_preferred':r'^(?:wünschenswert|von vorteil)\s*:\s*$'},
 'ar':{'required':[r'مطلوب',r'إلزامي',r'يشترط',r'ضروري'],
       'preferred':[r'يفضل',r'يُفضل',r'ميزة إضافية',r'اختياري'],
       'not_required':[r'غير\s+(?:مطلوب|ضروري|إلزامي)',r'لا\s+يشترط',r'ليس\s+مطلوب'],
       'head_required':r'^(?:المتطلبات|المهارات المطلوبة)\s*:\s*$',
       'head_preferred':r'^(?:المهارات المفضلة|يفضل)\s*:\s*$'}
}


def classify(clause, inherited=None):
    labels=set();packs=[]
    for name,pack in PACKS.items():
        # Remove only the negated phrase before looking for remaining positive cues.
        # A second required cue remains conflicting rather than being overwritten.
        cleaned=clause
        negative=False
        for pattern in pack['not_required']:
            if re.search(pattern,cleaned,re.I): negative=True;cleaned=re.sub(pattern,' ',cleaned,flags=re.I)
        found=[]
        if negative: found.append('not_required')
        if any(re.search(x,cleaned,re.I) for x in pack['required']): found.append('required')
        if any(re.search(x,clause,re.I) for x in pack['preferred']): found.append('preferred')
        if found: labels.update(found);packs.append(name)
    if labels.intersection({'required','preferred'}) and re.search(r'\b(?:if|unless|or|not|falls|sofern|wenn|oder|nicht|kein|keine)\b|(?:إذا|في حال|أو|غير|لا يشترط)',clause,re.I):
        # Recognized simple negation alone is retained below. Conditional, alternative
        # or conflicting phrasing is not promoted to an individual hard requirement.
        if labels != {'not_required'}: return 'ambiguous',packs
    if len(labels)>1:return 'ambiguous',packs
    if labels:return next(iter(labels)),packs
    return inherited or 'mentioned',packs


def extract(description,profile):
    evidence='\n'.join(x['text'] for x in profile.get('facts',[]) if x.get('verified') is True)
    declared='\n'.join(profile.get('skills',[]));rows=[];inherited=None
    lexicon=dict(SKILLS)
    for skill in profile.get('skills',[]):
        if not any(skill.casefold()==s.casefold() for s in lexicon): lexicon[skill]=[skill]
    # Preserve exact substring offsets. A blank line resets a narrow list heading.
    offset=0
    for line in description.splitlines(keepends=True):
        raw=line.rstrip('\r\n')
        if not raw.strip():inherited=None;offset+=len(line);continue
        heading=None
        for pack in PACKS.values():
            if re.fullmatch(pack['head_required'],raw.strip(),re.I):heading='required'
            if re.fullmatch(pack['head_preferred'],raw.strip(),re.I):heading='preferred'
        if heading:inherited=heading;offset+=len(line);continue
        # An unrelated heading ends inheritance rather than making all prose mandatory.
        if raw.strip().endswith(':'):inherited=None
        for part in re.finditer(r'[^.;!?\n؛。]+',raw):
            clause=part.group();start=offset+part.start();end=offset+part.end()
            names=[s for s,a in lexicon.items() if any(contains(clause,x) for x in a)]
            if not names:continue
            label,packs=classify(clause,inherited)
            for skill in names:
                aliases=lexicon[skill]
                support='verified_fact_mention' if any(contains(evidence,a) for a in aliases) else 'declared_skill' if any(contains(declared,a) for a in aliases) else 'not_recorded'
                rows.append({'skill':skill,'classification':label,'evidence':clause,'start':start,'end':end,'cue_packs':packs,
                             'candidate_evidence':support,'notice':'Mention evidence only; proficiency and eligibility are not established.'})
                if len(rows)>=MAX_EVIDENCE_ROWS:return rows
        if inherited and not raw.lstrip().startswith(('-','*','•')): inherited=None
        offset+=len(line)
    return rows
