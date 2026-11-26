"""Tests for your usage: what you run, and today's daytime quota."""

from datetime import datetime

from grid_tui.grid5000 import Cache, Client
from grid_tui.models import Job
from grid_tui.my_usage import (
    MyUsage,
    counts_toward_quota,
    daytime_core_seconds,
    my_usage,
)
from grid_tui.policy import PARIS
from tests.grid5000.fakes import NODES, SITES, fake_grid5000

THURSDAY = datetime(2026, 11, 26, 12, 0, tzinfo=PARIS)  # a working day, at noon
SATURDAY = datetime(2026, 11, 28, 12, 0, tzinfo=PARIS)


def at(hour: int, minute: int = 0) -> int:
    """Thursday at a time, in seconds since 1970."""
    return int(THURSDAY.replace(hour=hour, minute=minute).timestamp())


def job(**fields: object) -> Job:
    """A running default-queue job on gros with 9 cores, started at 10:00."""
    answer = {
        'uid': 1,
        'state': 'running',
        'queue': 'default',
        'walltime': 4 * 3600,
        'submitted_at': at(9),
        'started_at': at(10),
        'assigned_nodes': ['gros-1.nancy.grid5000.fr'],
        'resources_by_type': {'cores': list(range(9))},
        **fields,
    }
    return Job.from_api(answer, 'nancy')


# What counts toward the quota


def test_an_ordinary_job_counts() -> None:
    """A default-queue job submitted in the morning counts."""
    assert counts_toward_quota(job(), THURSDAY)


def test_other_queues_dont_count() -> None:
    """The quota is the default queue's rule: production doesn't count."""
    assert not counts_toward_quota(job(queue='production'), THURSDAY)


def test_a_short_last_minute_job_is_free() -> None:
    """1 hour or less, submitted under 10 minutes before it starts: free."""
    short = job(walltime=3600, submitted_at=at(9, 55), started_at=at(10))
    assert not counts_toward_quota(short, THURSDAY)
    planned = job(walltime=3600, submitted_at=at(9, 0), started_at=at(10))
    assert counts_toward_quota(planned, THURSDAY)


def test_a_job_submitted_from_17_is_free() -> None:
    """Submitted at or after 17:00: free."""
    late = job(submitted_at=at(17), started_at=at(17, 5))
    assert not counts_toward_quota(late, THURSDAY)


# How much it used between 09:00 and 19:00


def test_daytime_core_seconds_up_to_now() -> None:
    """Started at 10:00, now noon, 9 cores: 2 h × 9 cores."""
    assert daytime_core_seconds(job(), THURSDAY) == 2 * 3600 * 9


def test_only_the_daytime_part_counts() -> None:
    """A job from 07:00 to 10:00 used only 09:00 to 10:00 of the day."""
    early = job(started_at=at(7), stopped_at=at(10), state='terminated')
    assert daytime_core_seconds(early, THURSDAY) == 3600 * 9


def test_a_job_not_started_used_nothing() -> None:
    """A waiting job used nothing."""
    assert daytime_core_seconds(job(state='waiting', started_at=0), THURSDAY) == 0


# All together, from the API


def client_with(jobs: list[dict]) -> Client:
    """A client logged in as alice, on the fake API with these jobs in nancy."""
    transport = fake_grid5000(SITES, nodes=NODES, jobs={'nancy': jobs, 'lyon': []})
    return Client(user='alice', transport=transport, cache=Cache(':memory:'))


def answer(**fields: object) -> dict:
    """A job as the API gives it (see job())."""
    return {
        'uid': 1,
        'state': 'running',
        'queue': 'default',
        'walltime': 4 * 3600,
        'submitted_at': at(9),
        'started_at': at(10),
        'assigned_nodes': ['gros-1.nancy.grid5000.fr'],
        'resources_by_type': {'cores': list(range(9))},
        **fields,
    }


async def test_my_usage_on_a_working_day() -> None:
    """9 of gros's 18 cores for 2 h: half of its 2 h-on-all-cores quota."""
    usage = await my_usage(client_with([answer()]), THURSDAY)
    assert usage.jobs == 1
    assert usage.cores == 9
    assert usage.quota_percent == 50
    assert usage.quota_cluster == 'nancy/gros'


async def test_waiting_jobs_are_counted_apart() -> None:
    """A waiting job isn't running and uses no quota."""
    waiting = answer(uid=2, state='waiting', started_at=0, assigned_nodes=[])
    usage = await my_usage(client_with([waiting]), THURSDAY)
    assert (usage.jobs, usage.waiting, usage.quota_percent) == (0, 1, 0)


async def test_no_quota_on_a_weekend() -> None:
    """On a weekend there's no quota: quota_percent is None."""
    usage = await my_usage(client_with([]), SATURDAY)
    assert usage == MyUsage(quota_percent=None)


async def test_old_jobs_are_left_out() -> None:
    """A job that finished before today doesn't count."""
    yesterday = answer(
        state='terminated', started_at=at(10) - 86400, stopped_at=at(11) - 86400
    )
    usage = await my_usage(client_with([yesterday]), THURSDAY)
    assert usage.quota_percent == 0


async def test_without_a_login_there_are_no_jobs() -> None:
    """On a frontend (no login) there's no one to ask for: no jobs."""
    transport = fake_grid5000(SITES, jobs={'nancy': [answer()]})
    usage = await my_usage(Client(transport=transport), THURSDAY)
    assert usage.jobs == 0


async def test_my_usage_on_one_site() -> None:
    """On lyon, the nancy job doesn't count; on nancy it does."""
    client = client_with([answer()])
    assert (await my_usage(client, THURSDAY, 'lyon')).jobs == 0
    assert (await my_usage(client, THURSDAY, 'nancy')).quota_percent == 50
