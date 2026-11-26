"""Tests for StatusClient: how busy every site's nodes are now."""

import pytest

from grid_tui.grid5000 import ApiError, Cache, StatusClient
from grid_tui.models import Usage
from tests.grid5000.fakes import SITES, STATUS, fake_grid5000


async def test_one_site() -> None:
    """site_usage counts one site's nodes."""
    client = StatusClient(transport=fake_grid5000(SITES, statuses=STATUS))
    assert await client.site_usage('nancy') == Usage(busy=3, up=4)


async def test_asks_for_the_light_answer() -> None:
    """It leaves out each node's jobs and the disks."""
    seen = []
    client = StatusClient(transport=fake_grid5000(SITES, statuses=STATUS, seen=seen))
    await client.site_usage('nancy')
    assert seen[0].url.params['job_details'] == 'no'
    assert seen[0].url.params['disks'] == 'no'


async def test_every_site_together() -> None:
    """usage() adds up every site."""
    client = StatusClient(transport=fake_grid5000(SITES, statuses=STATUS))
    assert await client.usage() == Usage(busy=4, up=6)


async def test_a_site_that_fails_is_left_out() -> None:
    """A site whose status can't be read is skipped."""
    client = StatusClient(
        transport=fake_grid5000(SITES, statuses={'nancy': STATUS['nancy']})
    )
    assert await client.usage() == Usage(busy=3, up=4)


async def test_every_site_failing_raises() -> None:
    """If no site can be read, the error is raised."""
    client = StatusClient(transport=fake_grid5000(SITES))
    with pytest.raises(ApiError):
        await client.usage()


async def test_status_is_never_cached() -> None:
    """Each call asks the API again: it changes every minute."""
    seen = []
    client = StatusClient(
        transport=fake_grid5000(SITES, statuses=STATUS, seen=seen),
        cache=Cache(':memory:'),
    )
    await client.site_usage('nancy')
    await client.site_usage('nancy')
    assert len(seen) == 2


async def test_usage_of_one_site_asks_only_that_site() -> None:
    """usage('lyon') counts lyon only, and asks for nothing else."""
    seen = []
    client = StatusClient(transport=fake_grid5000(SITES, statuses=STATUS, seen=seen))
    assert await client.usage('lyon') == Usage(busy=1, up=2)
    assert [r.url.path for r in seen] == ['/stable/sites/lyon/status']


async def test_usage_by_site() -> None:
    """usage_by_site gives each site's counts, from one round of requests."""
    client = StatusClient(transport=fake_grid5000(SITES, statuses=STATUS))
    assert await client.usage_by_site() == {
        'nancy': Usage(busy=3, up=4),
        'lyon': Usage(busy=1, up=2),
    }
