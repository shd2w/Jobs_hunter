"""Additive public feeds and a bounded adapter over the original JobSpy scanner.

No account scraping, proxies, credential guessing or anti-bot bypass is added.
The full original run_scan.py remains available alongside these resumable units.
"""
import json
from pathlib import Path
from .collection import Collection, text

JOBSPY = ('jobspy_linkedin', 'jobspy_indeed', 'jobspy_google', 'jobspy_bayt')
PUBLIC = ('remoteok', 'weworkremotely')
CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'portals.yml'


def config():
    import yaml
    value = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    if not isinstance(value, dict): raise ValueError('Invalid original scanner registry; no reset attempted')
    return value


def collect(source, checkpoint=None, cancel_event=None):
    state = checkpoint or {}
    if cancel_event and cancel_event.is_set(): raise InterruptedError('Collection cancelled')
    if source.kind in JOBSPY:
        from scanners.jobspy_scanner import JobSpyScanner
        registry = config()
        scanner = JobSpyScanner(registry)
        site = source.kind.removeprefix('jobspy_')
        searches = [s for s in scanner.searches if site in s.get('sites', [])]
        if not searches: raise ValueError('No searches configured for this provider in config/portals.yml')
        index = int(state.get('search_index', 0)) % len(searches)
        search = dict(searches[index])
        page = int(state.get('page', 0))
        size = min(50, max(1, int(search.get('results_wanted', 30))))
        search.update(sites=[site], results_wanted=size, offset=page * size)
        jobs = scanner._run_search(search)
        rows = [j.to_dict() for j in jobs]
        # Two pages per query by default; each pass is bounded, not exhaustive.
        more = len(rows) >= size and page + 1 < min(5, max(1, int(search.get('pages', 2))))
        from utils.filters import TitleFilter, LocationFilter, filter_jobs
        filtered = filter_jobs(rows, TitleFilter(registry), LocationFilter(registry))
        raw_count = len(rows)
        rows = filtered['passed']
        next_state = {'search_index': index if more else (index + 1) % len(searches),
                      'page': page + 1 if more else 0, 'complete': False}
        return Collection(rows, next_state, {'raw_received': raw_count,
            'rejected_title': len(filtered['rejected_title']), 'rejected_location': len(filtered['rejected_location']), 'query': search['term'], 'location_query': search.get('location', ''),
            'page': page + 1, 'configured_queries': len(searches), 'bounded_selection': True,
            'coverage_complete': False, 'provider_errors': scanner.last_errors,
            'provider_warnings': scanner.last_warnings,
            'request_unit': 'One provider search page plus provider-managed description requests; not one HTTP request'})
    from .network import get
    if source.kind == 'remoteok':
        body, typ = get('https://remoteok.com/api')
        if 'json' not in typ: raise ValueError('Remote OK expected JSON')
        data = json.loads(body)
        if not isinstance(data, list) or len(data) > 10000: raise ValueError('Invalid Remote OK payload')
        rows = []
        for item in data:
            if not isinstance(item, dict): raise ValueError('Invalid Remote OK record')
            if 'legal' in item and 'id' not in item: continue  # Feed metadata, not a vacancy.
            salary = ''
            values = [item.get('salary_min'), item.get('salary_max')]
            import math
            if any(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values):
                salary = '-'.join(str(v) for v in values if type(v) in (int, float) and math.isfinite(v) and v > 0)
                if item.get('salary_currency'): salary = str(item['salary_currency']) + ' ' + salary
            rows.append({'title': item.get('position'), 'company': item.get('company'), 'url': item.get('url'),
                'description': text(item.get('description', '')), 'location': item.get('location', ''),
                'date_posted': item.get('date', ''), 'salary': salary,
                'employment_type': item.get('employment_type', ''), 'external_job_id': str(item.get('id', '')),
                'attribution': 'Remote OK', 'source_notice': 'Source: Remote OK. Preserve original Remote OK backlink and attribution; review the original listing.'})
        return Collection(rows, {'complete': True}, {'requests': 1, 'coverage_complete': True,
            'bounded_selection': False, 'coverage_scope': 'Current public API response, not all remote vacancies'})
    if source.kind == 'weworkremotely':
        body, typ = get('https://weworkremotely.com/remote-jobs.rss', 'application/rss+xml, application/xml, text/xml')
        if 'xml' not in typ: raise ValueError('We Work Remotely expected RSS XML')
        from defusedxml import ElementTree as ET
        root = ET.fromstring(body)
        items = root.findall('./channel/item')
        if root.tag != 'rss' or len(items) > 10000: raise ValueError('Invalid We Work Remotely RSS')
        rows = []
        for item in items:
            label = item.findtext('title', '')
            company, sep, title = label.partition(': ')
            # Do not invent a company from unstructured text. Malformed rows
            # are reported by common intake instead of silently discarded.
            rows.append({'title': title if sep else label, 'company': company if sep else '',
                'url': item.findtext('link', ''), 'description': text(item.findtext('description', '')),
                'location': item.findtext('region', ''), 'employment_type': item.findtext('type', ''),
                'date_posted': item.findtext('pubDate', ''),
                'attribution': 'We Work Remotely',
                'source_notice': 'Source: We Work Remotely. Preserve attribution and original listing backlink.'})
        return Collection(rows, {'complete': True}, {'requests': 1, 'coverage_complete': True,
            'bounded_selection': False, 'coverage_scope': 'Current public RSS response, not whole-site coverage'})
    raise ValueError('Unsupported expanded collector')
