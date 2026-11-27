"""Tests for JobsClient: your jobs, and their details."""

import json
from datetime import datetime

import httpx
import pytest

from grid_tui.grid5000 import ApiError, Cache, JobsClient
from grid_tui.grid5000.jobs import job_request, walltime
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


async def test_a_running_job_is_remembered_for_a_while() -> None:
    """A running job can change: asked again only after FRESH_FOR, or with r."""
    seen = []
    jobs = client(seen)
    await jobs.mine_today(MIDNIGHT)
    await jobs.mine_today(MIDNIGHT)  # within FRESH_FOR: from memory
    assert len([r for r in seen if r.url.path.endswith('/jobs/1')]) == 1
    lists = len([r for r in seen if r.url.path.endswith('/nancy/jobs')])
    await jobs.mine_today(MIDNIGHT, refresh=True)  # r: the lists are asked again
    assert len([r for r in seen if r.url.path.endswith('/nancy/jobs')]) == lists + 1


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


# Reserving: a new job, and cancelling one


def test_walltime() -> None:
    """Seconds as OAR's H:MM:SS; at least a minute."""
    assert walltime(5400) == '1:30:00'
    assert walltime(36 * 3600 + 61) == '36:01:01'
    assert walltime(5) == '0:01:00'


def test_job_request_now() -> None:
    """Nodes of one cluster, for a time, holding them with sleep."""
    assert job_request('gros', 2, 3600) == {
        'resources': 'nodes=2,walltime=1:00:00',
        'properties': "cluster='gros'",
        'command': 'sleep infinity',
    }


def test_job_request_later_named_for_deploy() -> None:
    """A start is an advance reservation, in Paris time; name and deploy go in."""
    start = datetime(2026, 11, 26, 20, 30, tzinfo=PARIS).timestamp()
    request = job_request('gros', 1, 7200, start=start, name='exp', deploy=True)
    assert request['reservation'] == '2026-11-26 20:30:00'
    assert request['name'] == 'exp'
    assert request['types'] == ['deploy']


def posting_client(
    sent: list, status: int = 201, answer: dict | None = None
) -> JobsClient:
    """A JobsClient whose fake API keeps every request, and answers a POST or
    DELETE with status (a GET as fake_grid5000 does)."""
    fake = fake_grid5000(SITES, jobs={'nancy': [], 'lyon': []})

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method in ('POST', 'DELETE'):
            return httpx.Response(status, json=answer or {})
        return fake.handler(request)

    return JobsClient(user='alice', transport=httpx.MockTransport(handle))


async def test_submit_posts_the_job_and_returns_its_uid() -> None:
    """POST /sites/nancy/jobs with the JSON; the answer's uid comes back."""
    sent: list = []
    jobs = posting_client(sent, answer={'uid': 4242})
    uid = await jobs.submit('nancy', job_request('gros', 2, 3600))
    assert uid == 4242
    post = sent[-1]
    assert (post.method, post.url.path) == ('POST', '/stable/sites/nancy/jobs')
    assert json.loads(post.content)['resources'] == 'nodes=2,walltime=1:00:00'


async def test_submit_forgets_what_was_remembered_about_the_site() -> None:
    """After reserving, your jobs list is asked for again, not remembered."""
    sent: list = []
    jobs = posting_client(sent, answer={'uid': 1})
    await jobs.mine('nancy')
    await jobs.mine('nancy')
    assert len(sent) == 1  # remembered
    await jobs.submit('nancy', job_request('gros', 1, 3600))
    await jobs.mine('nancy')
    assert [r.method for r in sent] == ['GET', 'POST', 'GET']


async def test_a_refused_job_says_why() -> None:
    """A 400 with a message: the error carries the API's reason."""
    jobs = posting_client([], status=400, answer={'message': 'walltime too long'})
    with pytest.raises(ApiError) as caught:
        await jobs.submit('nancy', job_request('gros', 1, 3600))
    assert caught.value.detail == 'walltime too long'
    assert str(caught.value).startswith('POST /sites/nancy/jobs: 400')
    assert 'walltime too long' in str(caught.value)


async def test_cancel_deletes_the_job() -> None:
    """DELETE /sites/nancy/jobs/42."""
    sent: list = []
    await posting_client(sent, status=202).cancel('nancy', 42)
    assert (sent[-1].method, sent[-1].url.path) == (
        'DELETE',
        '/stable/sites/nancy/jobs/42',
    )
