"""Reusable Workday binding over the existing explicit direct scanner."""
import asyncio
from .collection import Collection


def collect(source, checkpoint=None, cancel_event=None):
    if cancel_event and cancel_event.is_set(): raise InterruptedError('Cancelled')
    from scanners.workday import DirectAPIScanner, APIEndpoint
    tenant,node,board=source.identifier.split('__')
    host=f'{tenant}.{node}.myworkdayjobs.com'
    endpoint=APIEndpoint(tenant,f'https://{host}/wday/cxs/{tenant}/{board}/jobs',f'https://{host}/{board}','workday')
    scanner=DirectAPIScanner({})
    jobs=asyncio.run(scanner._scan_workday(endpoint,''))
    if cancel_event and cancel_event.is_set(): raise InterruptedError('Cancelled')
    return Collection([job.to_dict() for job in jobs],{'complete':True},
        {'bounded_selection':True,'coverage_complete':False,'detail_errors':list(scanner.query_errors),'provider_errors':list(scanner.query_errors),
         'request_unit':'up to 5 listing pages plus up to 100 details; existing direct-scanner bounds'})
