"""The clusters of a site: what they show, errors, and esc."""

from __future__ import annotations

from textual.widgets import DataTable

from grid_tui.app import GridTUI
from grid_tui.screens import ClustersScreen, SitesScreen
from tests.fakes import TWO_SITES, FakeClient, cells, status


async def test_enter_opens_the_clusters_of_the_selected_site() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")  # nancy
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ClustersScreen) and screen.site.uid == "nancy"
        table = screen.query_one(DataTable)
        assert table.row_count == 2
        assert cells(app, 0) == ["graffiti", "Dell PowerEdge T640", "production, admin", "no"]
        assert cells(app, 1) == ["gros", "Dell PowerEdge R640", "default, admin", "yes"]
        assert table.border_title == "site: nancy · clusters: 2"
        assert table.border_subtitle == "$ curl https://api.test/sites/nancy/clusters"

async def test_esc_goes_back_to_the_same_site() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down", "enter")  # rennes
        await pilot.pause()
        assert app.screen.site.uid == "rennes"
        assert cells(app, 0)[0] == "paravance"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SitesScreen)
        assert app.screen.selected == TWO_SITES[1]

async def test_clusters_error_and_reload() -> None:
    client = FakeClient(TWO_SITES)
    client.clusters_error = RuntimeError("GET /sites/nancy/clusters: 500 Internal Server Error")
    app = GridTUI(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert status(app) == "error: GET /sites/nancy/clusters: 500 Internal Server Error"
        client.clusters_error = None
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.query_one(DataTable).row_count == 2
        assert status(app) == ""
