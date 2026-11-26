"""Tests for Cache: API answers saved in a SQLite file."""

from pathlib import Path

import pytest

from grid_tui.grid5000 import ApiError, Cache, Client, SitesClient
from grid_tui.grid5000.cache import default_cache_path
from grid_tui.models import Site
from tests.grid5000.fakes import fake_api

SITES_ANSWER = {'items': [{'uid': 'nancy'}]}


def test_nothing_saved_is_none() -> None:
    """A path never saved gives None."""
    assert Cache(':memory:').get('/sites') is None


def test_put_then_get() -> None:
    """An answer saved can be read back."""
    cache = Cache(':memory:')
    cache.put('/sites', SITES_ANSWER)
    assert cache.get('/sites') == SITES_ANSWER


def test_put_replaces() -> None:
    """Saving a path again replaces the old answer."""
    cache = Cache(':memory:')
    cache.put('/sites', {'items': []})
    cache.put('/sites', SITES_ANSWER)
    assert cache.get('/sites') == SITES_ANSWER


def test_clear_forgets_everything() -> None:
    """clear() forgets every answer."""
    cache = Cache(':memory:')
    cache.put('/sites', SITES_ANSWER)
    cache.clear()
    assert cache.get('/sites') is None


def test_answers_stay_in_the_file(tmp_path: Path) -> None:
    """The answers are still there when the file is opened again."""
    path = tmp_path / 'sub' / 'cache.db'
    first = Cache(path)
    first.put('/sites', SITES_ANSWER)
    first.close()
    assert Cache(path).get('/sites') == SITES_ANSWER


def test_default_path_is_under_xdg_cache_home(tmp_path: Path) -> None:
    """The default file is in $XDG_CACHE_HOME/grid-tui (set by conftest)."""
    assert default_cache_path() == tmp_path / 'cache' / 'grid-tui' / 'cache.db'


async def test_sites_are_asked_for_once() -> None:
    """With a cache, the second list() is read from it, not the API."""
    seen = []
    client = SitesClient(
        transport=fake_api(json=SITES_ANSWER, seen=seen), cache=Cache(':memory:')
    )
    assert await client.list() == [Site(uid='nancy')]
    assert await client.list() == [Site(uid='nancy')]
    assert len(seen) == 1


async def test_refresh_asks_the_api_again_and_saves_it() -> None:
    """refresh=True skips the saved answer and saves the new one."""
    cache = Cache(':memory:')
    cache.put('https://api.grid5000.fr/stable/sites', {'items': [{'uid': 'old'}]})
    seen = []
    client = SitesClient(transport=fake_api(json=SITES_ANSWER, seen=seen), cache=cache)
    assert await client.list() == [Site(uid='old')]
    assert await client.list(refresh=True) == [Site(uid='nancy')]
    assert await client.list() == [Site(uid='nancy')]
    assert len(seen) == 1


async def test_without_a_cache_every_call_asks_the_api() -> None:
    """With no cache (as in tests), nothing is saved."""
    seen = []
    client = SitesClient(transport=fake_api(json=SITES_ANSWER, seen=seen))
    await client.list()
    await client.list()
    assert len(seen) == 2


async def test_an_error_is_not_saved() -> None:
    """A failed answer isn't saved: the next call asks the API again."""
    cache = Cache(':memory:')
    client = SitesClient(transport=fake_api(status=500), cache=cache)
    with pytest.raises(ApiError):
        await client.list()
    assert cache.get('https://api.grid5000.fr/stable/sites') is None


def test_each_api_root_has_its_own_answers() -> None:
    """The same path under another API root isn't mixed up with this one's."""
    cache = Cache(':memory:')
    cache.put('https://api.grid5000.fr/stable/sites', SITES_ANSWER)
    client = SitesClient('https://api.example/stable', cache=cache)
    assert cache.get(client.base_url + '/sites') is None


def test_client_shares_one_cache_with_its_parts() -> None:
    """A Client gives its cache to every part."""
    cache = Cache(':memory:')
    client = Client(cache=cache)
    assert client.sites.cache is cache
    assert client.nodes.cache is cache


def test_from_env_has_a_cache() -> None:
    """The app's client (from_env) caches, in the default file."""
    client = Client.from_env()
    assert client.cache is not None
    assert client.cache.path == default_cache_path()
