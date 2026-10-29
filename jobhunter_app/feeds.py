"""Inert RSS/Atom parsing; entries are posts for review, never auto-approved jobs."""
from __future__ import annotations
from html.parser import HTMLParser
from urllib.parse import urljoin
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from .validation import public_url


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
        if tag in ('p','div','br','li','h1','h2','h3'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden = max(0, self.hidden - 1)
        if tag in ('p','div','li'): self.parts.append('\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def text(value):
    parser = Text(); parser.feed(value or '')
    return ''.join(parser.parts).strip()


def local(tag): return tag.rsplit('}', 1)[-1]


def parse(content, source_label='Supplied feed', base_url=''):
    if isinstance(content, str): content = content.encode('utf-8')
    if not isinstance(content, bytes) or not 0 < len(content) <= 5 * 1024 * 1024:
        raise ValueError('Feed must contain at most 5 MiB')
    if base_url: public_url(base_url)
    try: root = ET.fromstring(content, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException) as exc: raise ValueError('Invalid or unsafe RSS/Atom XML') from exc
    kind = local(root.tag)
    if kind not in ('rss','feed','RDF'): raise ValueError('Expected RSS or Atom, not a web page')
    entries = [e for e in root.iter() if local(e.tag) in ('item','entry')]
    rows, errors = [], []
    for index, entry in enumerate(entries[:300]):
        try:
            values = {}
            for child in entry:
                name = local(child.tag)
                values.setdefault(name, []).append(child)
            def value(*names):
                for name in names:
                    nodes = values.get(name, [])
                    if nodes:
                        node = nodes[0]
                        if list(node):
                            return ''.join(ET.tostring(c, encoding='unicode') for c in node)
                        return node.text or ''
                return ''
            title = text(value('title'))[:500]
            description = text(value('encoded','content','description','summary'))
            body = title + ('\n' + description if description else '')
            link = ''
            for node in values.get('link', []):
                if local(entry.tag) == 'entry':
                    if node.get('rel', 'alternate') != 'alternate': continue
                    link = node.get('href', '')
                else: link = node.text or ''
                if link: break
            if link:
                link = urljoin(base_url, link.strip())
                public_url(link)
            rows.append({'body': body, 'title_hint': title, 'origin_url': link, 'source_label': source_label,
                         'published': value('published','pubDate','updated')[:200]})
        except (ValueError, TypeError) as exc:
            errors.append({'entry': index + 1, 'error': str(exc)})
    return {'posts': rows, 'total_entries': len(entries), 'truncated': len(entries) > 300, 'errors': errors}


def ingest(store, content, rights_attested=False, source_label='Supplied feed', base_url='', dry_run=False, _db=None, auto_add=False, profile_id='default'):
    from .posts import stage, process
    parsed = parse(content, source_label, base_url)
    result = (process(store, parsed['posts'], rights_attested, dry_run,_db=_db,profile_id=profile_id) if auto_add else stage(store, parsed['posts'], rights_attested, dry_run,_db=_db)) if parsed['posts'] else {'received': 0, 'staged': 0, 'duplicates': 0, 'invalid': 0, 'skipped': 0, 'items': [], 'errors': [], 'dry_run': dry_run}
    return {**result, 'feed_entries': parsed['total_entries'], 'feed_truncated': parsed['truncated'], 'feed_errors': parsed['errors']}
