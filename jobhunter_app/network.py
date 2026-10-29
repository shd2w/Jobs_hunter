"""Bounded HTTPS fetches with public-address validation and DNS-pinned TLS."""
from __future__ import annotations
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError
from .validation import public_url

MAX_BYTES = 5 * 1024 * 1024
SOCIAL_HOSTS = ('reddit.com', 'redd.it', 'telegram.org', 't.me', 'linkedin.com', 'facebook.com', 'instagram.com', 'x.com', 'twitter.com', 'discord.com', 'discord.gg')


def feed_url(value):
    public_url(value)
    p = urlsplit(value)
    if p.scheme != 'https' or p.port not in (None, 443) or p.fragment:
        raise ValueError('Feeds require HTTPS on port 443 without fragments')
    host = p.hostname.lower()
    if any(host == x or host.endswith('.' + x) for x in SOCIAL_HOSTS):
        raise ValueError('Direct social-platform harvesting is not supported; use content you are authorized to supply')
    # Feed registry is public-only. Never put passwords, tokens or signed private URLs here.
    if p.query:
        from urllib.parse import parse_qsl
        if any(any(s in k.lower() for s in ('token','key','secret','password','signature','auth')) for k, _ in parse_qsl(p.query)):
            raise ValueError('Credential-bearing feed URLs are not supported')
    return value


def public_addresses(host):
    addresses = list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or len(addresses) > 32:
        raise ValueError('Invalid source DNS response')
    for value in addresses:
        ip = ipaddress.ip_address(value)
        if not ip.is_global or (ip.version == 6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global):
            raise ValueError('Source DNS includes a non-public address')
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout=20):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Never resolve the hostname a second time; SNI and certificates still verify it.
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def get(url, accept='application/json', max_bytes=MAX_BYTES, credentials=None, credential_scope=None):
    public_url(url)
    p = urlsplit(url)
    if p.scheme != 'https' or p.port not in (None, 443): raise ValueError('HTTPS sources only')
    host = p.hostname.encode('idna').decode('ascii')
    headers = {'User-Agent': 'JobHunter-Local/0.3', 'Accept': accept, 'Accept-Encoding': 'identity'}
    if credential_scope is not None:
        from .platform_posts import validate_request_scope
        validate_request_scope(credential_scope,url,credentials or {})
        headers.update(credentials or {})
    elif credentials is not None:
        if host != 'data.usajobs.gov' or p.path != '/api/Search' or set(credentials) != {'User-Agent', 'Authorization-Key'}:
            raise ValueError('Credentials are restricted to the documented USAJOBS search endpoint')
        if any(not isinstance(v, str) or not 1 <= len(v) <= 1000 or any(ord(c) < 32 or ord(c) > 126 for c in v) for v in credentials.values()):
            raise ValueError('Invalid USAJOBS credential configuration')
        headers.update(credentials)
    address = public_addresses(host)[0]
    connection = PinnedHTTPS(host, address)
    deadline = time.monotonic() + 20
    try:
        connection.request('GET', (p.path or '/') + ('?' + p.query if p.query else ''), headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            # Do not follow redirects, attach credentials or read/persist remote error bodies.
            raise HTTPError('https://api.telegram.org/[redacted]' if credential_scope=='telegram' else url, response.status, 'Source request rejected', {'Retry-After': response.getheader('Retry-After', '')[:200]}, None)
        content_type = response.getheader('Content-Type', '').lower()
        length = response.getheader('Content-Length')
        if length and int(length) > max_bytes: raise ValueError('Source response exceeds byte limit')
        if response.getheader('Content-Encoding', 'identity') not in ('', 'identity'):
            raise ValueError('Compressed responses are not supported')
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('Source read deadline exceeded')
            if connection.sock: connection.sock.settimeout(remaining)
            chunk = response.read1(min(65536, max_bytes + 1 - size))
            if not chunk: break
            size += len(chunk)
            if size > max_bytes: raise ValueError('Source response exceeds byte limit')
            chunks.append(chunk)
        return b''.join(chunks), content_type
    finally:
        connection.close()
