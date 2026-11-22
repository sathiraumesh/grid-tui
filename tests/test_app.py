"""The app: the main screen's tabs, opening on Sites; 1-7 go to a tab; q quits."""

from __future__ import annotations

from textual.widgets import DataTable, TabbedContent

from grid_tui.app import GridTUI
from grid_tui.screens import MainScreen
from tests.fakes import TWO_SITES, FakeClient, settle, status

SIZE = (140, 40)


async def test_opens_on_the_sites_tab() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        screen = app.screen
        assert isinstance(screen, MainScreen) and screen.active == "sites"
        assert isinstance(app.focused, DataTable) and app.focused.row_count == 2
        assert status(app) == ""


async def test_the_tabs() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        labels = [str(t.label) for t in app.screen.query_one("#tabs", TabbedContent).query("Tab")]
        assert labels[:5] == ["1 Sites", "2 Clusters", "3 Nodes", "4 Reservations", "7 Search"]
        assert labels[5:] == ["4 Current", "5 Reserve", "6 My reservations"]


async def test_digits_go_to_a_tab() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        for key, tab in [("2", "clusters"), ("3", "nodes"), ("4", "current"), ("5", "reserving"),
                         ("6", "mine"), ("7", "search"), ("1", "sites")]:
            app.screen.set_focus(app.screen.query_one(DataTable))  # out of any form field
            await pilot.press(key)
            await settle(pilot)
            assert app.screen.active == tab, key


async def test_q_quits() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("q")
    assert app.return_code == 0


async def test_a_splash_shows_until_the_sites_have_loaded() -> None:
    import asyncio

    from grid_tui.screens import SplashScreen

    client = FakeClient(TWO_SITES)
    client.gate = asyncio.Event()  # the sites wait
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, SplashScreen)
        assert "Grid'5000" in str(app.screen.query_one("#tagline").render())
        client.gate.set()
        await settle(pilot)
        assert isinstance(app.screen, MainScreen) and app.screen.sites.table.row_count == 2


async def test_the_splash_goes_on_an_error_too() -> None:
    client = FakeClient(error=RuntimeError("GET /sites: 401 Unauthorized"))
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        assert isinstance(app.screen, MainScreen)
        assert status(app) == "error: GET /sites: 401 Unauthorized"
