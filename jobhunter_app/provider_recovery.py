"""Conservative JobSpy failure policy shared by bounded and legacy execution.

A denial is not an empty search. Never retries immediately or changes transport.
Backoff does not revoke approval, delete progress, or prove future access.
"""
import re


def http_status(value):
    match = re.search(r"(?:status(?: code)?|HTTP)\s*[:=]?\s*(401|403|429)\b", str(value), re.I)
    return int(match[1]) if match else None


def policy(kind, status=None, consecutive=1):
    if kind == 'jobspy_google':
        category, base, message = 'upstream_unavailable', 86400, 'Google Jobs is unavailable in the installed upstream integration. No successful empty scan was recorded.'
    elif status in (401, 403):
        category, base, message = 'access_denied', 21600, 'Provider denied access (HTTP %s). Other sources continue. No proxy, login or challenge bypass was attempted.' % status
    elif status == 429:
        category, base, message = 'rate_limited', 3600, 'Provider rate limit reached (HTTP 429). Requests are deferred; no alternate transport was attempted.'
    else:
        category, base, message = 'provider_failure', 3600, 'JobSpy provider request failed. Other sources continue; inspect local scanner diagnostics.'
    delay = min(86400, base * 2 ** min(4, max(0, consecutive - 1)))
    return {'recovery_category': category, 'retry_delay_seconds': delay,
            'recovery_action': 'Wait for the provider gate, then recheck using the same adapter. Persistent denial requires provider/upstream resolution.',
            'error': message}
