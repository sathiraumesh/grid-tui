"""The app: it opens on the sites, and q quits."""

from __future__ import annotations

from textual.widgets import DataTable

from grid_tui.app import GridTUI
from grid_tui.screens import SitesScreen
from tests.fakes import TWO_SITES, FakeClient, status


async def test_opens_on_the_sites() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, SitesScreen)
        table = screen.query_one(DataTable)
        assert table.row_count == 2
        assert [str(c) for c in table.get_row_at(0)] == ["nancy", "Nancy", "Grid5000 Nancy site"]
        assert table.border_title == "sites: 2"
        assert table.border_subtitle == "$ curl https://api.test/sites"
        assert status(app) == ""

async def test_q_quits() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.press("q")
    assert app.return_code == 0
