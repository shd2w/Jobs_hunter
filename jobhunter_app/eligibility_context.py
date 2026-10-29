"""Bounded listing-only review cues. Never decide a person's eligibility."""
import re
from .requirements import classify

VERSION = 'eligibility-context-en-de-ar-1'
MAX_ROWS = 80
MAX_EXCERPT = 1200
FIELD_LIMITS = {'title': 1000, 'location': 2000, 'description': 97000}
CATEGORIES = {
    'experience': {
        'patterns': [r'\b\d{1,2}(?:\s*[-–+]\s*\d{0,2})?\s*(?:years?|yrs?|Jahre[n]?)\b',
                     r'\b(?:experience|Berufserfahrung)\b', r'(?:خبرة|خبرات|سنوات|سنتين|عامين)'],
        'question': 'Check the required duration, domain, alternatives and your documented experience; no years are inferred.'},
    'education': {
        'patterns': [r'\b(?:degree|bachelor[’\']?s?|master[’\']?s?|doctorate|Ph\.?D|diploma|Ausbildung|Studium|Hochschulabschluss|Abschluss)\b',
                     r'(?:بكالوريوس|ماجستير|دكتوراه|شهادة|مؤهل)'],
        'question': 'Check degree level, field, equivalence and experience alternatives; no credential equivalence is inferred.'},
    'language': {
        'patterns': [r'\b(?:English|German|Arabic|Deutsch|Englisch|Arabisch|language|languages|Sprachkenntnisse|Sprachniveau|fluent|fluency|CEFR|[ABC][12])\b',
                     r'(?:العربية|الإنجليزية|الانجليزية|الألمانية|اللغة|بطلاقة)'],
        'question': 'Check the actual language, proficiency and assessment requirement; a declared language is not proof of the required level.'},
    'work_authorization': {
        'patterns': [r'\b(?:visa|sponsorship|work\s+(?:permit|authori[sz]ation|eligibility)|right\s+to\s+work|citizenship|citizens?|security\s+clearance|Arbeitserlaubnis|Visum|Staatsangehörigkeit)\b',
                     r'(?:تصريح العمل|إذن العمل|تأشيرة|الجنسية|كفالة)'],
        'question': 'Verify jurisdiction, work authorization and sponsorship directly with the employer; no citizenship, legal status or clearance is inferred.'},
    'compensation': {
        'patterns': [r'\b(?:salary|compensation|pay\s+range|hourly\s+rate|Gehalt|Vergütung|USD|EUR|EGP|GBP|SAR|AED)\b',
                     r'[$€£]', r'(?:راتب|الراتب|الأجر|الاجر|جنيه|ريال|درهم)'],
        'question': 'Check currency, amount, period, gross/net, benefits and contract type; no salary conversion or currency is inferred from an ambiguous symbol.'},
    'remote_location': {
        'patterns': [r'\b(?:remote|hybrid|on[- ]?site|relocat(?:e|ion)|time\s*zone|residency|residents?\s+of|based\s+in|Homeoffice|Wohnsitz|Umzug)\b',
                     r'(?:عن بعد|هجين|الإقامة|الاقامة|مكان العمل|المنطقة الزمنية)'],
        'question': 'Check permitted residence, working jurisdiction, time zone and on-site obligations; remote does not mean work from anywhere.'},
}
COMPILED = {key: tuple(re.compile(p, re.I) for p in value['patterns']) for key, value in CATEGORIES.items()}


def review_context(job):
    """Exact offsets refer to the original, unnormalized field. No profile consumed."""
    rows = []
    fields = {}
    truncated = False
    for field, limit in FIELD_LIMITS.items():
        original = job.get(field) or ''
        # Canonical validation normally guarantees strings; reject unsupported values.
        if not isinstance(original, str):
            raise ValueError('Eligibility context fields must be text')
        text = original[:limit]
        fields[field] = {'characters': len(original), 'scanned_characters': len(text), 'truncated': len(original) > limit}
        truncated |= fields[field]['truncated']
        offset = 0
        scanned_end = 0
        for line in text.splitlines(keepends=True):
            raw = line.rstrip('\r\n')
            for begin in range(0, len(raw), MAX_EXCERPT):
                excerpt = raw[begin:begin + MAX_EXCERPT]
                scanned_end = offset + begin + len(excerpt)
                for category, patterns in COMPILED.items():
                    if not any(p.search(excerpt) for p in patterns):
                        continue
                    if len(rows) >= MAX_ROWS:
                        truncated = True
                        break
                    label, packs = classify(excerpt)
                    rows.append({'category': category, 'field': field,
                                 'start': offset + begin, 'end': offset + begin + len(excerpt),
                                 'evidence': excerpt, 'cue_classification': label, 'cue_packs': packs,
                                 'candidate_assessment': 'not_assessed'})
                if len(rows) >= MAX_ROWS:
                    truncated = True
                    break
            offset += len(line)
            if len(rows) >= MAX_ROWS:
                break
        # Continue recording field coverage but stop scanning after reaching the row cap.
        if len(rows) >= MAX_ROWS:
            fields[field]['scanned_characters'] = min(len(text), scanned_end)
            for remaining in list(FIELD_LIMITS)[list(FIELD_LIMITS).index(field) + 1:]:
                value = job.get(remaining) or ''
                if not isinstance(value, str):
                    raise ValueError('Eligibility context fields must be text')
                fields[remaining] = {'characters': len(value), 'scanned_characters': 0, 'truncated': bool(value)}
            break
    observed = {r['category'] for r in rows}
    return {'version': VERSION, 'evidence': rows, 'truncated': truncated,
            'field_coverage': fields, 'limits': {'rows': MAX_ROWS, 'excerpt_characters': MAX_EXCERPT, 'field_characters': dict(FIELD_LIMITS)},
            'categories': [{'category': key, 'listing_state': 'observed_mention' if key in observed else 'not_observed_in_bounded_text',
                            'candidate_assessment': 'not_assessed', 'review_question': value['question']} for key, value in CATEGORIES.items()],
            'notice': 'Listing text cues only, not verified employer requirements or a candidate eligibility decision. All categories require human review. Missing mentions are unknown, not permission or failure. Negation, alternatives and mixed clauses can be misread by narrow rules. Long lines are chunked and may split phrases. This evidence never changes scores or overrides explicit exclusions.'}
