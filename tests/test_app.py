import asyncio

from textual.widgets import DataTable, Static

from grid_tui.app import GridTUI
from grid_tui.models import Cluster, Site
from grid_tui.screens import ClustersScreen, SitesScreen

TWO_SITES = [Site("nancy", "Nancy", "Grid5000 Nancy site"), Site("rennes", "Rennes", "Grid5000 Rennes site")]

CLUSTERS = {
    "nancy": [
        Cluster("graffiti", "Dell PowerEdge T640", ("production", "admin")),
        Cluster("gros", "Dell PowerEdge R640", ("default", "admin"), ("wattmetre_power_watt",)),
    ],
    "rennes": [Cluster("paravance", "Dell PowerEdge R630", ("default",))],
}


class FakeClient:
    """Answers with sites, or raises error; calls counts the loads."""

    def __init__(self, sites: list[Site] | None = None, error: Exception | None = None) -> None:
        self.result, self.error, self.calls = sites or [], error, 0
        self.gate: asyncio.Event | None = None  # set: loads wait for it
        self.clusters_error: Exception | None = None

    async def sites(self) -> list[Site]:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.result

    async def clusters(self, site: str) -> list[Cluster]:
        self.calls += 1
        if self.clusters_error is not None:
            raise self.clusters_error
        return CLUSTERS.get(site, [])

    def command(self, path: str) -> str:
        return "curl https://api.test" + path


def status(app: GridTUI) -> str:
    return str(app.screen.query_one("#status", Static).render())


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


async def test_q_quits() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test() as pilot:
        await pilot.press("q")
    assert app.return_code == 0


def cells(app: GridTUI, row: int) -> list[str]:
    return [str(c) for c in app.screen.query_one(DataTable).get_row_at(row)]


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
