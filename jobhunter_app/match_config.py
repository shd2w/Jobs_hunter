"""Explicit profile matching settings; no coercion of uncertain values."""
import math

FIELDS = {'excluded_companies','excluded_location_terms','required_listing_terms','preferred_title_terms','preferred_location_terms','skill_weights','weights'}
DEFAULT_WEIGHTS = {'skills':60,'title':25,'location':15}


def validate(config, skills):
    if not isinstance(config,dict) or set(config)-FIELDS: raise ValueError('Invalid matching settings or unknown fields')
    for key in FIELDS-{'weights','skill_weights'}:
        v=config.get(key,[])
        if not isinstance(v,list) or len(v)>50 or any(not isinstance(x,str) or not x.strip() or len(x)>100 or any(ord(c)<32 for c in x) for x in v):
            raise ValueError('Matching terms must be lists of at most 50 printable nonempty strings')
    for key in ('weights','skill_weights'):
        v=config.get(key,{})
        known=set(DEFAULT_WEIGHTS) if key=='weights' else set(skills)
        if not isinstance(v,dict) or set(v)-known or any(type(x) not in (int,float) or not math.isfinite(x) or not 0 < x <=100 for x in v.values()):
            raise ValueError('Matching weights must be finite positive numbers up to 100 on configured dimensions/skills')
    return config
