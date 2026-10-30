"""Legacy BaseScanner bridge to the primary Scrapling collection engine."""
import asyncio
import json
from pathlib import Path
from .base import BaseScanner, JobPosting

class ScraplingScanner(BaseScanner):
    def __init__(self,config,data_dir='data',dry_run=False):
        super().__init__(config,name='scrapling')
        self.data_dir=Path(data_dir);self.dry_run=dry_run

    async def scan(self):
        result=self._make_result()
        if self.dry_run:
            self.logger.info('Scrapling crawl skipped in dry-run: no network, quota changes or vacancy writes')
            return self._finish_result(result)
        return await asyncio.to_thread(self._collect,result)

    def _collect(self,result):
        from jobhunter_app.store import Store,now
        from jobhunter_app.sources import Source,scan
        from jobhunter_app.scrapling_engine import SOURCES
        store=Store(self.data_dir/'jobhunter.sqlite3')
        kinds=self.config.get('scrapling_sources',list(SOURCES))
        if not isinstance(kinds,list) or any(k not in SOURCES for k in kinds):
            raise ValueError('Use supported Scrapling source kinds')
        for kind in dict.fromkeys(kinds):
            source=Source(kind,SOURCES[kind]['identifier'])
            with store.connect() as db:
                # Never reapprove a source that the user or access handler paused.
                db.execute('INSERT OR IGNORE INTO sources(id,kind,identifier,approved) VALUES(?,?,?,1)',(source.id,kind,source.identifier))
            stamp=now()
            try:
                scan(store,source.id,mirror_legacy=False)
                with store.connect() as db:
                    rows=db.execute('SELECT j.data FROM jobs j JOIN sightings s ON s.job_id=j.id WHERE s.source=? AND s.last_seen>=?',(source.id,stamp)).fetchall()
                for row in rows:
                    item=json.loads(row[0]);keys=('title','url','company','location','date_posted','description','salary','employment_type')
                    result.jobs.append(JobPosting(**{k:item.get(k,'') for k in keys},source=source.id))
            except ValueError as exc:
                result.errors.append(f'{source.id}: {exc}')
        return self._finish_result(result)
