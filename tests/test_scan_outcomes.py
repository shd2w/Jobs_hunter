"""R01: actual orchestration; external scanners replaced, bridge/intake real."""
import asyncio
import pytest
from scanners.base import JobPosting, ScanResult


def test_top_level_jobspy_failure_preserves_independent_results(tmp_path, monkeypatch):
    import run_scan
    class Good:
        def __init__(self, *args): pass
        async def scan(self):
            return ScanResult('scrapling', [JobPosting('Software Engineer', 'https://example.org/jobs/1', 'Example', 'Germany')])
    class Empty(Good):
        async def scan(self): return ScanResult('direct_api')
    class Broken(Good):
        async def scan(self): raise RuntimeError('provider unavailable')
    monkeypatch.setattr(run_scan, 'ScraplingScanner', Good)
    monkeypatch.setattr(run_scan, 'DirectAPIScanner', Empty)
    monkeypatch.setattr(run_scan, 'JobSpyScanner', Broken)
    result = asyncio.run(run_scan.run_scan(config_override={}, data_dir=tmp_path))
    assert result['total_found'] == 1
    assert result['inbox']['inserted'] == 1
    assert any('provider unavailable' in error for error in result['errors'])
    assert result['execution']['status'] == 'partial'
    tasks = result['execution']['tasks']
    assert len(tasks) == 3 and len({task['id'] for task in tasks}) == 3
    assert [task['status'] for task in tasks] == ['succeeded', 'succeeded', 'failed']
    assert tasks[-1]['error_category'] == 'RuntimeError'
    assert all(task['started_at'] and task['finished_at'] for task in tasks)


def test_main_total_failure_is_nonzero(monkeypatch):
    import run_scan
    async def failed(**kwargs): return {'errors': ['failure'], 'total_found': 0}
    monkeypatch.setattr(run_scan, 'run_scan', failed)
    monkeypatch.setattr('sys.argv', ['run_scan.py'])
    with pytest.raises(SystemExit) as exc: run_scan.main()
    assert exc.value.code == 1


def test_query_attempts_reconcile_per_query(monkeypatch):
    from scanners.jobspy_scanner import JobSpyScanner
    async def no_wait(*a): pass
    monkeypatch.setattr('scanners.jobspy_scanner.asyncio.sleep',no_wait)
    def search(self,query):
        if query['term']=='broken': raise RuntimeError('query failed')
        return [JobPosting('Engineer','https://example.org/1','Example')]
    monkeypatch.setattr(JobSpyScanner,'_run_search',search)
    result=asyncio.run(JobSpyScanner({'jobspy_searches':[{'term':'broken'},{'term':'Python Developer'}]}).scan())
    assert [x['status'] for x in result.attempts]==['failed','succeeded']
    assert len({x['id'] for x in result.attempts})==2
    assert result.job_count==1 and result.error_count==1
