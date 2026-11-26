"""Tests for JobsClient: your jobs, and their details."""

from datetime import datetime

from grid_tui.grid5000 import Cache, JobsClient
from grid_tui.policy import PARIS
from tests.grid5000.fakes import SITES, fake_grid5000

MIDNIGHT = datetime(2026, 11, 26, tzinfo=PARIS)
NOW = int(MIDNIGHT.timestamp()) + 12 * 3600
RUNNING = {
    'uid': 1,
    'state': 'running',
    'started_at': NOW - 3600,
    'walltime': 7200,
    'assigned_nodes': ['gros-1.nancy.grid5000.fr'],
    'resources_by_type': {'cores': ['1', '2']},
}
FINISHED_TODAY = {**RUNNING, 'uid': 2, 'state': 'terminated', 'stopped_at': NOW - 60}
FINISHED_LAST_WEEK = {
    **FINISHED_TODAY,
    'uid': 3,
    'started_at': NOW - 7 * 86400,
    'stopped_at': NOW - 7 * 86400 + 60,
}


def client(seen: list | None = None) -> JobsClient:
    """A JobsClient logged in as alice, with jobs in nancy and none in lyon."""
    jobs = {'nancy': [RUNNING, FINISHED_TODAY, FINISHED_LAST_WEEK], 'lyon': []}
    return JobsClient(
        user='alice',
        transport=fake_grid5000(SITES, jobs=jobs, seen=seen),
        cache=Cache(':memory:'),
    )


async def test_mine_asks_for_your_jobs() -> None:
    """mine() asks for the user's jobs in the useful states."""
    seen = []
    await client(seen).mine('nancy')
    assert seen[0].url.params['user'] == 'alice'
    assert 'running' in seen[0].url.params['state']


async def test_mine_today_keeps_active_and_todays_jobs() -> None:
    """Running jobs and today's finished ones, with their cores; not last week's."""
    jobs = await client().mine_today(MIDNIGHT)
    assert sorted(job.uid for job in jobs) == [1, 2]
    assert all(job.cores == 2 for job in jobs)


async def test_a_finished_jobs_details_are_cached() -> None:
    """A finished job won't change: its details are read once."""
    seen = []
    jobs = client(seen)
    await jobs.mine_today(MIDNIGHT)
    asked = [r.url.path for r in seen if r.url.path.endswith('/jobs/2')]
    await jobs.mine_today(MIDNIGHT)
    asked_again = [r.url.path for r in seen if r.url.path.endswith('/jobs/2')]
    assert len(asked) == len(asked_again) == 1


async def test_a_running_jobs_details_are_asked_each_time() -> None:
    """A running job can change: asked for every time."""
    seen = []
    jobs = client(seen)
    await jobs.mine_today(MIDNIGHT)
    await jobs.mine_today(MIDNIGHT)
    assert len([r for r in seen if r.url.path.endswith('/jobs/1')]) == 2


async def test_no_login_no_jobs() -> None:
    """Without a login (on a frontend) there are no jobs to ask for."""
    jobs = JobsClient(transport=fake_grid5000(SITES, jobs={'nancy': [RUNNING]}))
    assert await jobs.mine_today(MIDNIGHT) == []


async def test_mine_today_on_one_site() -> None:
    """With a site, only that site's jobs are asked for."""
    seen = []
    jobs = await client(seen).mine_today(MIDNIGHT, 'lyon')
    assert jobs == []
    assert not any('/nancy/' in r.url.path for r in seen)
