"""Sites: loading, errors, reloading, moving, and opening a site."""

from __future__ import annotations

import asyncio

from textual.widgets import DataTable

from grid_tui.app import GridTUI
from tests.fakes import TWO_SITES, FakeClient, settle, status

SIZE = (140, 40)


async def test_shows_loading_until_the_sites_arrive() -> None:
    client = FakeClient(TWO_SITES)
    client.gate = asyncio.Event()
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert status(app) == "loading…"
        client.gate.set()
        await settle(pilot)
        assert app.screen.sites.table.row_count == 2
        assert app.screen.sites.table.border_title == "sites: 2"
        assert app.screen.sites.table.border_subtitle == "$ curl https://api.test/sites"


async def test_moves_and_selects() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("down")
        assert app.screen.sites.selected == TWO_SITES[1]
        await pilot.press("up")
        assert app.screen.sites.selected == TWO_SITES[0]


async def test_error_is_shown_and_r_retries() -> None:
    client = FakeClient(error=RuntimeError("GET /sites: 401 Unauthorized"))
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        assert status(app) == "error: GET /sites: 401 Unauthorized"
        assert app.screen.sites.query_one(".status").has_class("error")
        client.error, client.result = None, TWO_SITES  # now it works
        await pilot.press("r")
        await settle(pilot)
        assert app.screen.sites.table.row_count == 2
        assert status(app) == ""
        assert not app.screen.sites.query_one(".status").has_class("error")


async def test_a_failed_reload_keeps_the_sites() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        client.error = RuntimeError("timeout")
        await pilot.press("r")
        await settle(pilot)
        assert app.screen.sites.table.row_count == 2
        assert status(app) == "error: timeout"


async def test_enter_opens_the_clusters_tab() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("down", "enter")  # rennes
        await settle(pilot)
        assert app.screen.active == "clusters" and app.screen.clusters.site == TWO_SITES[1]
        assert isinstance(app.focused, DataTable)
