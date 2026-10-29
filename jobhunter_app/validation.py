"""Input and model-output boundaries. Never coerce unknown facts to truth."""
from __future__ import annotations
import math
from urllib.parse import urlsplit


def public_url(value: str) -> str:
    """Syntactic public web URL check; network adapters additionally pin hosts."""
    import ipaddress
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 for c in value):
        raise ValueError('Invalid job URL')
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid job URL') from exc
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Job URL must be HTTP(S) without credentials')
    host = parsed.hostname.lower()
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
        raise ValueError('Local network URLs are not allowed')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('Private network URLs are not allowed')
    if port not in (None, 80, 443):
        raise ValueError('Nonstandard web ports are not allowed')
    return value


def normalize_job(raw: dict) -> dict:
    from utils.queue_exporter import canonicalize_url
    if not isinstance(raw, dict):
        raise ValueError('Job must be an object')
    out = {}
    limits = {'title': 300, 'company': 300, 'location': 500, 'description': 100000,
              'source': 100, 'date_posted': 100, 'salary': 300, 'employment_type': 1000,
              'language': 100, 'external_job_id': 300, 'attribution': 500,
              'source_notice': 1000}
    for field, limit in limits.items():
        value = raw.get(field, '')
        if value is None:
            value = ''
        if not isinstance(value, str) or len(value) > limit or '\x00' in value:
            raise ValueError(f'Invalid {field}')
        out[field] = value.strip()
    for field in ('title', 'company'):
        if not out[field]:
            raise ValueError(f'Missing {field}')
    out['url'] = canonicalize_url(public_url(raw.get('url', '')))
    return out


def validate_ai_evaluation(data) -> bool:
    if not isinstance(data, dict):
        return False
    score = data.get('global_score')
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 1 <= score <= 5:
        return False
    scores = data.get('scores')
    keys = ('skills_match', 'education_match', 'location', 'language', 'growth')
    if not isinstance(scores, dict):
        return False
    for key in keys:
        x = scores.get(key)
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 1 <= x <= 5:
            return False
    if data.get('recommendation') not in ('apply', 'consider', 'skip'):
        return False
    for field in ('match_highlights', 'gaps'):
        values = data.get(field)
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(x, str) or len(x) > 2000 for x in values):
            return False
    return isinstance(data.get('reasoning'), str) and data.get('german_level_required') in ('none', 'A1-A2', 'B1', 'B2+')
