"""Tests for Connection: one kept-open connection, shared and remembered answers."""

import asyncio

import httpx
import pytest

from grid_tui.grid5000 import ApiError, Client
from grid_tui.grid5000.base import Connection
from tests.grid5000.fakes import SITES, STATUS, fake_grid5000


def connection(seen: list, delay: float = 0) -> Connection:
    """A connection to the fake API; each answer waits `delay` seconds."""
    fake = fake_grid5000(SITES, statuses=STATUS, seen=seen)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(delay)
        return await fake.handle_async_request(request)

    return Connection(
        'https://api.example/stable', '', '', httpx.MockTransport(slow), 5.0
    )


async def test_the_same_request_at_once_is_sent_once() -> None:
    """Three identical GETs at the same time: one request, three answers."""
    seen: list = []
    api = connection(seen, delay=0.05)
    answers = await asyncio.gather(*(api.get('/sites') for _ in range(3)))
    assert len(seen) == 1
    assert answers[0] == answers[1] == answers[2] == {'items': SITES}


async def test_remembered_for_fresh_for() -> None:
    """With fresh_for, a repeat is answered from memory; refresh asks again."""
    seen: list = []
    api = connection(seen)
    await api.get('/sites', fresh_for=60)
    await api.get('/sites', fresh_for=60)
    assert len(seen) == 1
    await api.get('/sites', fresh_for=60, refresh=True)
    assert len(seen) == 2


async def test_not_remembered_without_fresh_for() -> None:
    """Without fresh_for, each GET (one after the other) is sent."""
    seen: list = []
    api = connection(seen)
    await api.get('/sites')
    await api.get('/sites')
    assert len(seen) == 2


async def test_old_answers_are_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once fresh_for has passed, the next GET is sent."""
    seen: list = []
    api = connection(seen)
    now = [1000.0]
    monkeypatch.setattr('grid_tui.grid5000.base.time.monotonic', lambda: now[0])
    await api.get('/sites', fresh_for=60)
    now[0] += 61
    await api.get('/sites', fresh_for=60)
    assert len(seen) == 2


async def test_an_error_reaches_everyone_waiting_and_isnt_remembered() -> None:
    """A failed request raises for every caller, and the next one is sent."""
    seen: list = []
    api = connection(seen, delay=0.05)
    results = await asyncio.gather(
        api.get('/nope', fresh_for=60),
        api.get('/nope', fresh_for=60),
        return_exceptions=True,
    )
    assert all(isinstance(result, ApiError) for result in results)
    assert len(seen) == 1
    with pytest.raises(ApiError):
        await api.get('/nope', fresh_for=60)
    assert len(seen) == 2


async def test_one_connection_kept_open_for_every_part() -> None:
    """A Client's parts share one connection, which stays open between requests."""
    client = Client(transport=fake_grid5000(SITES, statuses=STATUS))
    assert client.sites.connection is client.status.connection is client.connection
    await client.sites.list()
    first = client.connection._http
    await client.status.site_usage('nancy')
    assert client.connection._http is first  # the same, kept open
    await client.aclose()
    assert client.connection._http is None
