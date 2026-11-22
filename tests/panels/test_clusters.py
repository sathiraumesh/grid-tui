"""Clusters: what they show, errors, esc, and g for the reservations."""

from __future__ import annotations

from grid_tui.app import GridTUI
from tests.fakes import TWO_SITES, FakeClient, cells, settle, status

SIZE = (140, 40)


async def test_before_a_site_is_chosen() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("2")
        await settle(pilot)
        assert status(app) == "choose a site in Sites (1)"


async def test_enter_on_a_site_shows_its_clusters() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("enter")  # nancy
        await settle(pilot)
        panel = app.screen.clusters
        assert app.screen.active == "clusters" and panel.site.uid == "nancy"
        assert panel.table.row_count == 2
        assert cells(app, 0) == ["graffiti", "Dell PowerEdge T640", "production, admin", "no"]
        assert cells(app, 1) == ["gros", "Dell PowerEdge R640", "default, admin", "yes"]
        assert panel.table.border_title == "site: nancy · clusters: 2"
        assert panel.table.border_subtitle == "$ curl https://api.test/sites/nancy/clusters"


async def test_esc_goes_back_to_the_same_site() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("down", "enter")  # rennes
        await settle(pilot)
        assert cells(app, 0)[0] == "paravance"
        await pilot.press("escape")
        await settle(pilot)
        assert app.screen.active == "sites" and app.screen.sites.selected == TWO_SITES[1]


async def test_clusters_error_and_reload() -> None:
    client = FakeClient(TWO_SITES)
    client.clusters_error = RuntimeError("GET /sites/nancy/clusters: 500 Internal Server Error")
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        assert status(app) == "error: GET /sites/nancy/clusters: 500 Internal Server Error"
        client.clusters_error = None
        await pilot.press("r")
        await settle(pilot)
        assert app.screen.clusters.table.row_count == 2 and status(app) == ""


async def test_g_opens_a_clusters_reservations() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot)
        await pilot.press("down", "g")  # gros
        await settle(pilot)
        current = app.screen.current
        assert app.screen.active == "current" and current.cluster.uid == "gros"
        assert [n.name for n in current.gantt.nodes] == ["gros-1", "gros-2", "gros-10"]
        await pilot.press("escape")  # straight from Clusters: back there
        await settle(pilot)
        assert app.screen.active == "clusters"
