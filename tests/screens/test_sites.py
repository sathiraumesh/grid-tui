"""The sites: loading, errors, reloading, moving, and opening a site."""

from __future__ import annotations

import asyncio

from textual.widgets import DataTable

from grid_tui.app import GridTUI
from grid_tui.screens import ClustersScreen
from tests.fakes import TWO_SITES, FakeClient, status


async def test_shows_loading_until_the_sites_arrive() -> None:
    client = FakeClient(TWO_SITES)
    client.gate = asyncio.Event()
    app = GridTUI(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert status(app) == "loading…"
        client.gate.set()
        await pilot.pause()
        assert app.screen.query_one(DataTable).row_count == 2

async def test_moves_and_selects() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        assert app.screen.selected == TWO_SITES[1]
        await pilot.press("up")
        assert app.screen.selected == TWO_SITES[0]

async def test_error_is_shown_and_r_retries() -> None:
    client = FakeClient(error=RuntimeError("GET /sites: 401 Unauthorized"))
    app = GridTUI(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert status(app) == "error: GET /sites: 401 Unauthorized"
        assert app.screen.query_one("#status").has_class("error")

        client.error, client.result = None, TWO_SITES  # now it works
        await pilot.press("r")
        await pilot.pause()
        assert client.calls == 2
        assert app.screen.query_one(DataTable).row_count == 2
        assert status(app) == ""
        assert not app.screen.query_one("#status").has_class("error")

async def test_a_failed_reload_keeps_the_sites() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        client.error = RuntimeError("timeout")
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.query_one(DataTable).row_count == 2
        assert status(app) == "error: timeout"

async def test_a_click_on_a_site_opens_its_clusters() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = app.screen.query_one(DataTable)
        await pilot.click(DataTable, offset=(5, 3))  # the border, the titles, nancy: rennes is the 2nd row
        await pilot.pause()
        if not isinstance(app.screen, ClustersScreen):  # the first click may only move the cursor
            await pilot.click(DataTable, offset=(5, 3))
            await pilot.pause()
        assert isinstance(app.screen, ClustersScreen)
        assert app.screen.site == TWO_SITES[table.cursor_row]
