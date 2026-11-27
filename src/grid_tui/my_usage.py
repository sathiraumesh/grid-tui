"""Your own use of Grid'5000: what runs now, and today's daytime quota.

The usage policy allows, on a working day between 09:00 and 19:00, at most
the equivalent of 2 hours on all the cores of a cluster (default queue). Not
counted (the policy's exceptions):

- a job of 1 hour or less, submitted less than 10 minutes before it started;
- a job submitted at or after 17:00 (it may run past 19:00, and its
  17:00-19:00 part is free).

    usage = await my_usage(client, datetime.now(PARIS))
    usage.quota_percent   # e.g. 12: the most used cluster's share of its quota
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from grid_tui.grid5000 import Client
from grid_tui.models.job import Job
from grid_tui.policy import DAY_END, DAY_START, PARIS, is_working_day

QUOTA_SECONDS = 2 * 3600  # 2 h on all the cores of a cluster
SHORT_JOB = 3600  # a job this long or shorter...
LATE_SUBMIT = 600  # ...submitted this soon before it starts, is free
FREE_AFTER = time(17, 0)  # a job submitted from 17:00 is free


@dataclass(frozen=True)
class MyUsage:
    """What you run now, and how much of today's daytime quota you've used."""

    jobs: int = 0  # your jobs running now
    cores: int = 0  # the cores they hold
    waiting: int = 0  # your jobs waiting to start
    # the most used cluster's share of its daily quota, 0-100+; None when there
    # is no quota today (a weekend or a holiday)
    quota_percent: int | None = None
    quota_cluster: str = ''  # that cluster, e.g. 'nancy/gros'
    by_cluster: dict[str, int] = field(default_factory=dict)  # every cluster's %


def counts_toward_quota(job: Job, day: datetime) -> bool:
    """Does the job count toward the daily quota (default queue, no exception)?

    Args:
        job: The job.
        day: Any time on the day in question, in Paris time.
    """
    if job.queue not in ('', 'default'):
        return False  # the quota is the default queue's rule
    submitted, started = job.submitted_at, job.started_at
    if submitted is not None and started is not None:
        if job.walltime <= SHORT_JOB and started - submitted < LATE_SUBMIT:
            return False
    if submitted is not None:
        free_from = datetime.combine(day.date(), FREE_AFTER, tzinfo=PARIS)
        if submitted >= free_from.timestamp():
            return False
    return True


def daytime_core_seconds(job: Job, now: datetime) -> float:
    """How many core-seconds the job used today between 09:00 and 19:00."""
    ran = job.ran(now.timestamp())
    if ran is None:
        return 0.0
    today = now.date()
    window_start = datetime.combine(today, DAY_START, tzinfo=PARIS).timestamp()
    window_end = min(
        datetime.combine(today, DAY_END, tzinfo=PARIS).timestamp(), now.timestamp()
    )
    overlap = min(ran[1], window_end) - max(ran[0], window_start)
    return max(overlap, 0.0) * job.cores


async def my_usage(
    client: Client, now: datetime, site: str | None = None, *, refresh: bool = False
) -> MyUsage:
    """Your use of Grid'5000 at a moment, on one site or all of them.

    Args:
        client: Where to ask (it needs your login).
        now: The moment, e.g. datetime.now(PARIS).
        site: Only this site's jobs and clusters, e.g. 'nancy'; None for all.
        refresh: Ask the API even for answers it remembers.
    """
    now = now.astimezone(PARIS)
    midnight = datetime.combine(now.date(), time(0), tzinfo=PARIS)
    jobs = await client.jobs.mine_today(midnight, site, refresh=refresh)
    running = [job for job in jobs if job.is_running]
    waiting = [job for job in jobs if job.is_active and not job.is_running]
    usage = MyUsage(
        jobs=len(running),
        cores=sum(job.cores for job in running),
        waiting=len(waiting),
    )
    if not is_working_day(now.date()):
        return usage

    used: dict[tuple[str, str], float] = defaultdict(float)
    for job in jobs:
        if job.cluster and counts_toward_quota(job, now):
            used[(job.site, job.cluster)] += daytime_core_seconds(job, now)
    used = {key: seconds for key, seconds in used.items() if seconds > 0}
    if not used:
        return MyUsage(usage.jobs, usage.cores, usage.waiting, quota_percent=0)

    async def cluster_cores(site: str, cluster: str) -> int:
        nodes = await client.nodes.list(site, cluster)  # cached
        return sum(node.architecture.nb_cores for node in nodes)

    keys = list(used)
    totals = await asyncio.gather(*(cluster_cores(*key) for key in keys))
    by_cluster = {
        f'{site}/{cluster}': round(
            100 * used[(site, cluster)] / (QUOTA_SECONDS * total)
        )
        for (site, cluster), total in zip(keys, totals)
        if total
    }
    worst = max(by_cluster, key=by_cluster.get, default='')
    return MyUsage(
        usage.jobs,
        usage.cores,
        usage.waiting,
        quota_percent=by_cluster.get(worst, 0),
        quota_cluster=worst,
        by_cluster=by_cluster,
    )


def planned_quota(
    nodes: int,
    node_cores: int,
    cluster_cores: int,
    start: float,
    seconds: float,
    submitted: float,
) -> int | None:
    """How much of a day's quota a reservation would use, on its worst day.

    The quota is per cluster and per day, so a reservation over several days
    is measured day by day, and the most used day is given.

    Args:
        nodes: How many nodes it reserves.
        node_cores: The cores of each node.
        cluster_cores: All the cluster's cores (the quota is 2 h on them all).
        start: When it starts, in seconds since 1970.
        seconds: How long it lasts.
        submitted: When it is sent (now): a job sent from 17:00, or a short
            one sent just before it starts, doesn't count.

    Returns:
        The percentage of the quota, e.g. 45; 0 if it doesn't touch daytime;
        None if it doesn't count at all (one of the policy's exceptions).
    """
    sent = datetime.fromtimestamp(submitted, PARIS)
    if sent.time() >= FREE_AFTER and is_working_day(sent.date()):
        return None
    if seconds <= SHORT_JOB and start - submitted < LATE_SUBMIT:
        return None
    if cluster_cores <= 0:
        return 0
    end = start + seconds
    day = datetime.fromtimestamp(start, PARIS).date()
    last = datetime.fromtimestamp(end, PARIS).date()
    worst = 0.0
    while day <= last:
        if is_working_day(day):
            opens = datetime.combine(day, DAY_START, tzinfo=PARIS).timestamp()
            closes = datetime.combine(day, DAY_END, tzinfo=PARIS).timestamp()
            worst = max(worst, min(end, closes) - max(start, opens))
        day += timedelta(days=1)
    share = 100 * worst * nodes * node_cores / (QUOTA_SECONDS * cluster_cores)
    return round(share)
