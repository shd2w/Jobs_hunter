"""Deterministic, bounded intent-to-query contracts. No model or YAML writes."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

VERSION = 'intent-1'
ROLES = {
    'backend': {'signals': ('python', 'sql', 'backend', 'django', 'fastapi'),
                'en': ('Python Developer', 'Backend Engineer'),
                'de': ('Python Entwickler', 'Backend Entwickler'),
                'ar': ('مطور بايثون', 'مهندس برمجيات')},
    'data': {'signals': ('analytics', 'data', 'pandas', 'statistics'),
             'en': ('Data Analyst', 'Data Engineer'),
             'de': ('Datenanalyst', 'Dateningenieur'), 'ar': ('محلل بيانات', 'مهندس بيانات')},
    'software': {'signals': ('software', 'java', 'javascript', 'typescript', 'c++'),
                 'en': ('Software Engineer', 'Software Developer'),
                 'de': ('Softwareentwickler', 'Softwareingenieur'), 'ar': ('مهندس برمجيات', 'مطور برمجيات')},
}


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class QuerySpec:
    profile_id: str
    intent_version: str
    text: str
    region: str
    language: str
    provider: str
    evidence: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    remote: bool = False
    limit: int = 20
    pages: int = 2
    adapter_version: str = 'jobspy-1'

    def __post_init__(self):
        from scanners.jobspy_registry import SITES
        if self.provider not in SITES or self.language not in ('en', 'de', 'ar'):
            raise ValueError('Unsupported query provider/language')
        for value in (self.profile_id, self.intent_version, self.text, self.region):
            if not isinstance(value, str) or not value.strip() or len(value) > 300 or any(ord(c) < 32 for c in value):
                raise ValueError('Invalid query field')
        if type(self.limit) is not int or not 1 <= self.limit <= 50 or type(self.pages) is not int or not 1 <= self.pages <= 5:
            raise ValueError('Invalid query bounds')
        if type(self.remote) is not bool: raise ValueError('Remote must be explicit boolean')

    @property
    def signature(self): return fingerprint(asdict(self))

    def parameters(self):
        from scanners.jobspy_scanner import bounded_search
        from .expanded_sources import config
        result = bounded_search(config(), self.provider, self.text, self.region, self.limit)
        result.update(pages=self.pages, is_remote=self.remote, fetch_description=True)
        return result


def plan(profile, profile_id='default', regions=(), languages=(), max_queries=8):
    """Return explicit coverage limitations rather than invent profile facts."""
    if not 1 <= max_queries <= 100: raise ValueError('Query budget must be 1..100')
    matching = profile.get('matching', {})
    roles = matching.get('preferred_title_terms', [])
    skills = profile.get('skills', [])
    intent = {'profile': profile, 'regions': list(regions), 'languages': list(languages), 'version': VERSION}
    version = fingerprint(intent)
    locales = list(languages) or [x for x in profile.get('languages', []) if x in ('en','de','ar')] or ['en']
    places = list(regions) or matching.get('preferred_location_terms', []) or ['Remote']
    if len(locales) > 5 or len(places) > 10: raise ValueError('Too many search regions/languages')
    evidence = tuple(roles + skills)
    haystack = ' '.join(evidence).casefold()
    families = [key for key, value in ROLES.items() if any(signal in haystack for signal in value['signals'])]
    exclusions = tuple(profile.get('excluded_title_terms', []))
    from scanners.jobspy_registry import SITES
    queries, seen, limitations = [], set(), []
    for language in locales:
        if language not in ('en','de','ar'):
            limitations.append(f'Unsupported query language: {language}'); continue
        terms = [term for f in families for term in ROLES[f][language]]
        # Explicit preferences remain useful for unknown occupations; blank intent gets a declared broad query.
        terms += roles or ([] if terms else skills[:2]) or ([] if terms else ['Jobs'])
        for term in terms:
            if any(x.casefold() in term.casefold() for x in exclusions): continue
            for region in places:
                key = (term.casefold(), region.casefold(), language)
                if key in seen: continue
                seen.add(key)
                for site in SITES:
                    queries.append(QuerySpec(profile_id, version, term, region, language, site, evidence,
                                             exclusions, region.casefold() == 'remote'))
    return queries[:max_queries], {'intent_version': version, 'limitations': limitations,
        'planned_variants': len(seen), 'query_budget_deferred': max(0, len(queries)-max_queries),
        'broad_default': not bool(evidence), 'families': families}
