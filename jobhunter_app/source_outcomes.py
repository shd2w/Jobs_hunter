"""Backend source response outcomes, independent of pagination and evaluation."""
def outcome(metrics):
    if metrics.get('error'):
        return {'code': 'failed', 'message': metrics['error']}
    received = metrics.get('raw_received', metrics.get('received'))
    new = metrics.get('new_unique_jobs')
    existing = metrics.get('existing_job_observations')
    invalid = metrics.get('invalid', 0)
    rejected = metrics.get('rejected_title', 0) + metrics.get('rejected_location', 0)
    if received is None or new is None or existing is None:
        return {'code': 'unknown', 'message': 'Historical response counts unavailable; no empty-result conclusion can be drawn.'}
    if received == 0:
        code, message = 'empty_response', 'Source returned no records for this request; this does not prove no vacancies exist.'
    elif new:
        code, message = 'new_records', f'{new} canonical inserts; {existing} existing observations.'
    elif existing:
        code, message = 'existing_only', f'No new inserts; {existing} existing job observations refreshed.'
    elif rejected:
        code, message = 'filtered', f'No inserts; {rejected} received records excluded by configured filters.'
    elif invalid:
        code, message = 'invalid_records', f'No inserts; {invalid} invalid records. Review source diagnostics.'
    else:
        code, message = 'processed', 'Response processed with no canonical inserts; review detailed counts.'
    return {'code': code, 'message': message, 'received': received, 'new': new,
            'existing': existing, 'invalid': invalid, 'filtered': rejected}
