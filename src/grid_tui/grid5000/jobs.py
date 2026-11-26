"""Your jobs: GET /sites/{site}/jobs?user=you, and one job's details.

Not cached while a job can still change; a finished job's details are.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models.job import Job
from grid_tui.models.site import Site

# the states worth reading: what runs or will, and what ran (for today's quota)
STATES = 'running,launching,waiting,terminated,error'
FRESH_FOR = 240  # seconds your jobs list (and a running job) is remembered


class JobsClient(BaseClient):
    """The calls about your jobs."""

    async def mine(self, site: str, *, refresh: bool = False) -> list[Job]:
        """Your recent jobs on a site (without their nodes or cores)."""
        user = quote(self.user, safe='')
        path = f'/sites/{quote(site, safe="")}/jobs?user={user}&state={STATES}&limit=50'
        answer = await self._get(path, fresh_for=FRESH_FOR, refresh=refresh)
        return [Job.from_api(item, site) for item in answer.get('items', [])]

    async def get(self, site: str, uid: int) -> Job:
        """One job, with its nodes and cores."""
        path = f'/sites/{quote(site, safe="")}/jobs/{uid}'
        answer = await self._get(path, fresh_for=FRESH_FOR)
        job = Job.from_api(answer, site)
        if not job.is_active and self.cache is not None:
            self.cache.put(self.base_url + path, answer)  # finished: won't change
        return job

    async def _details(self, job: Job) -> Job:
        """The job with its nodes and cores; from the cache if it's finished."""
        path = f'/sites/{quote(job.site, safe="")}/jobs/{job.uid}'
        if not job.is_active and self.cache is not None:
            saved = self.cache.get(self.base_url + path)
            if saved is not None:
                return Job.from_api(saved, job.site)
        return await self.get(job.site, job.uid)

    async def mine_today(
        self, since: datetime, site: str | None = None, *, refresh: bool = False
    ) -> list[Job]:
        """Your jobs that run now, will run, or ran since a time.

        Args:
            since: Keep finished jobs that started at or after this, e.g.
                midnight today.
            site: Only this site's jobs, e.g. 'nancy'; None for every site.
            refresh: Ask the API even for lists asked within FRESH_FOR.

        Returns:
            The jobs with their nodes and cores. A site that can't be read is
            left out; if none can be, the first error is raised.
        """
        if not self.user:
            return []  # on a frontend there's no login to ask with
        if site is not None:
            uids = [site]
        else:
            data = await self._get('/sites', cached=True)
            uids = [Site.model_validate(item).uid for item in data.get('items', [])]
        listed = await asyncio.gather(
            *(self.mine(uid, refresh=refresh) for uid in uids),
            return_exceptions=True,
        )
        lists = [jobs for jobs in listed if isinstance(jobs, list)]
        errors = [error for error in listed if isinstance(error, BaseException)]
        if errors and not lists:
            raise errors[0]
        start = since.timestamp()
        wanted = [
            job
            for jobs in lists
            for job in jobs
            if job.is_active or (job.started_at or 0) >= start
        ]
        details = await asyncio.gather(
            *(self._details(job) for job in wanted), return_exceptions=True
        )
        return [job for job in details if isinstance(job, Job)]
