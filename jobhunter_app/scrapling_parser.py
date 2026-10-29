"""Optional Scrapling extraction worker over already-authorized public HTML.

No Scrapling network, browser, proxy, credential or challenge-solving features
are invoked. Existing bounded transports and board URL rules remain in charge.
"""
import os
from types import SimpleNamespace


def parser_mode():
    value = os.environ.get('JOBHUNTER_AUTHORIZED_BOARD_PARSER', 'stdlib')
    if value not in ('stdlib', 'scrapling'):
        raise ValueError('JOBHUNTER_AUTHORIZED_BOARD_PARSER must be stdlib or scrapling')
    return value


def parse_page(body):
    if len(body) > 5 * 1024 * 1024: raise ValueError('Source response exceeds byte limit')
    try:
        from scrapling import Selector
    except ImportError:
        raise ImportError('Optional Scrapling parser missing; install requirements-scrapling.txt') from None
    page = Selector(body.decode('utf-8-sig'), adaptive=False)
    documents = page.css('script[type="application/ld+json"]::text').getall()[:100]
    links = []
    for node in page.css('a[href], link[rel]')[:1000]:
        attrs = node.attrib
        links.append({'url': attrs.get('href', ''),
                      'next': 'next' in attrs.get('rel', '').split(),
                      'label': node.get_all_text()[:100]})
    return SimpleNamespace(documents=documents, links=links)
