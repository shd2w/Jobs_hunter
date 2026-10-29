"""Bounded, inert file intake. No pickle, executable plugins or automatic URLs."""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024


def parse_jobs(content: bytes, format: str) -> list[dict]:
    if len(content) > MAX_BYTES:
        raise ValueError('Import exceeds 10 MiB')
    if format == 'xlsx':
        from .spreadsheets import read_xlsx
        return read_xlsx(content)
    text = content.decode('utf-8-sig')
    if format == 'json':
        rows = strict_json(text)
    elif format == 'jsonl':
        rows = [strict_json(line) for line in text.splitlines() if line.strip()]
    elif format == 'csv':
        reader = csv.DictReader(io.StringIO(text), strict=True)
        try:
            headers = reader.fieldnames or []
        except csv.Error as exc:
            raise ValueError('CSV parser rejected malformed headers') from exc
        if not headers or len(headers) != len(set(headers)) or any(not x for x in headers):
            raise ValueError('CSV requires unique nonempty headers')
        try:
            rows = list(reader)
        except csv.Error as exc:
            raise ValueError('CSV parser rejected malformed or oversized fields') from exc
        if any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError('CSV row width does not match headers')
    else:
        raise ValueError('Supported formats: JSON, JSONL, CSV, XLSX (optional Excel dependency)')
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Expected at most 10,000 job objects')
    return rows


def read_jobs(path: Path) -> list[dict]:
    with path.open('rb') as f:
        content = f.read(MAX_BYTES + 1)
    return parse_jobs(content, path.suffix.lstrip('.').lower())


def export_jobs(store, format='json', profile_id='default') -> bytes:
    # Paginate instead of silently limiting export to the dashboard's first page.
    rows = []
    offset = 0
    while True:
        page = store.jobs(profile_id=profile_id, limit=1000, offset=offset)
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    from .posts import origins
    for row in rows:
        row['post_origins'] = origins(store, row['id'])
    if format == 'json':
        return json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    if format == 'xlsx':
        from .spreadsheets import write_xlsx
        return write_xlsx(rows)
    if format != 'csv':
        raise ValueError('Export must be JSON, CSV or XLSX')
    out = io.StringIO(newline='')
    fields = ['id', 'url', 'title', 'company', 'location', 'description', 'status', 'notes', 'deadline', 'first_seen', 'last_seen', 'attribution', 'source_notice', 'post_origins']
    writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        row = {**row, 'post_origins': json.dumps(row.get('post_origins', []), ensure_ascii=False)}
        # Spreadsheet formula injection protection without changing stored facts.
        safe = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v) for k, v in row.items()}
        writer.writerow(safe)
    return out.getvalue().encode('utf-8-sig')


def strict_json(text):
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in '[{':
            depth += 1
            if depth > 64:
                raise ValueError('JSON nesting exceeds 64 levels')
        elif character in ']}':
            depth -= 1
    def reject(value):
        raise ValueError('Non-finite JSON number rejected')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError('Duplicate JSON key rejected')
            out[key] = value
        return out
    def finite_float(value):
        import math
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('Non-finite JSON number rejected')
        return number
    try:
        return json.loads(text, parse_constant=reject, parse_float=finite_float, object_pairs_hook=unique)
    except RecursionError as exc:
        raise ValueError('JSON nesting exceeds safe parser depth') from exc
