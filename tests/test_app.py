"""Tests for the whole app: its frame, its keys, and how the tabs work together."""

from textual.widgets import DataTable, Select

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Cache, Client
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.panels.clusters import ClusterPanel
from grid_tui.widgets.panels.nodes import NodesPanel
from grid_tui.widgets.panels.search import SearchPanel
from grid_tui.widgets.panels.sites import SitesPanel
from tests.grid5000.fakes import (
    CLUSTERS,
    NODES,
    SITES,
    fake_client,
    fake_grid5000,
    g5k_client,
)
from tests.widgets.panels.helpers import rows, settle


async def test_frame_shows_title_and_subtitle() -> None:
    """The frame shows Grid'5000 at the top and the credit at the bottom."""
    app = Grid5KApp(fake_client())
    async with app.run_test():  # runs the app headless, no real terminal
        assert app.screen.border_title == "Grid'5000"
        assert app.screen.border_subtitle == 'Powered by IP Paris'


async def test_stylesheet_is_applied() -> None:
    """app.tcss is loaded: the dark background and the orange frame."""
    app = Grid5KApp(fake_client())
    async with app.run_test():
        styles = app.screen.styles
        assert styles.background.hex == '#1E1E2E'

        edge_type, edge_color = styles.border_top
        assert edge_type == 'round'
        assert edge_color.hex == '#FAB387'  # orange frame

        assert styles.border_subtitle_color.hex == '#A6ADC8'


async def test_q_quits() -> None:
    """q closes the app cleanly."""
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:  # pilot presses keys and clicks
        await pilot.press('q')
    assert app.return_code == 0


async def test_number_keys_switch_tabs() -> None:
    """1, 2, 3 and 4 switch to the Sites, Clusters, Nodes and Search tabs."""
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:
        tabs = app.query_one(MainTabs)
        assert tabs.active == 'sites'
        await pilot.press('2')
        assert tabs.active == 'clusters'
        await pilot.press('3')
        assert tabs.active == 'nodes'
        await pilot.press('4')
        assert tabs.active == 'search'
        await pilot.press('1')
        assert tabs.active == 'sites'


# Choosing a site opens its clusters


async def test_choosing_a_site_opens_its_clusters() -> None:
    """Enter on a site opens the Clusters tab with only that site."""
    app = Grid5KApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(SitesPanel).query_one(DataTable).focus()
        await pilot.press('down', 'enter')  # the second site: lyon
        await settle(app, pilot)
        assert app.query_one(MainTabs).active == 'clusters'
        panel = app.query_one(ClusterPanel)
        assert panel.site == 'lyon'
        assert [row[0] for row in rows(panel.query_one(DataTable))] == ['lyon']
        assert panel.query_one('#site-select', Select).selection == 'lyon'


async def test_r_reloads_only_the_tab_that_is_showing() -> None:
    """r loads the showing tab again, and leaves the other tabs as they are."""
    app = Grid5KApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        sites = app.query_one(SitesPanel).query_one(DataTable)
        clusters = app.query_one(ClusterPanel).query_one(DataTable)
        sites.clear()
        clusters.clear()
        await pilot.press('r')  # on the Sites tab
        await settle(app, pilot)
        assert sites.row_count == 2
        assert clusters.row_count == 0  # not reloaded

        await pilot.press('2')  # the Clusters tab
        sites.clear()
        await pilot.press('r')
        await settle(app, pilot)
        assert clusters.row_count == 3
        assert sites.row_count == 0  # not reloaded


async def test_r_asks_the_api_again_not_the_cache() -> None:
    """With a cache, sites load from it after the first time, but r asks the API."""
    seen = []
    client = Client(
        transport=fake_grid5000(SITES, CLUSTERS, nodes=NODES, seen=seen),
        cache=Cache(':memory:'),
    )
    app = Grid5KApp(client)

    def asked() -> int:
        """How many times /sites was asked of the API."""
        return sum(request.url.path == '/stable/sites' for request in seen)

    async with app.run_test() as pilot:
        await settle(app, pilot)
        before = asked()
        app.query_one(SitesPanel).load()
        await settle(app, pilot)
        assert asked() == before  # from the cache
        await pilot.press('r')
        await settle(app, pilot)
        assert asked() == before + 1  # from the API


# Choosing a cluster opens its nodes


async def test_choosing_a_cluster_opens_its_nodes() -> None:
    """Enter on a cluster opens the Nodes tab with that cluster's nodes."""
    app = Grid5KApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        await pilot.press('2')
        app.query_one(ClusterPanel).query_one(DataTable).focus()
        await pilot.press('enter')  # the first cluster: nancy / gros
        await settle(app, pilot)
        assert app.query_one(MainTabs).active == 'nodes'
        panel = app.query_one(NodesPanel)
        assert (panel.site, panel.cluster) == ('nancy', 'gros')
        nodes = [row[0] for row in rows(panel.query_one(DataTable))]
        assert nodes == ['gros-1', 'gros-2']


async def test_from_a_site_to_its_nodes() -> None:
    """Site → its clusters → a cluster → its nodes, with the keyboard."""
    app = Grid5KApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(SitesPanel).query_one(DataTable).focus()
        await pilot.press('enter')  # nancy
        await settle(app, pilot)
        app.query_one(ClusterPanel).query_one(DataTable).focus()
        await pilot.press('enter')  # gros
        await settle(app, pilot)
        assert app.query_one(MainTabs).active == 'nodes'
        assert app.query_one(NodesPanel).query_one(DataTable).row_count == 2


# Searching


async def test_a_search_result_opens_its_nodes() -> None:
    """Enter on a search result opens the Nodes tab with that cluster."""
    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press('4')
        app.query_one(SearchPanel).run_search()  # no needs: every cluster with nodes
        await settle(app, pilot)
        app.query_one(SearchPanel).query_one(DataTable).focus()
        await pilot.press('enter')  # the first result: lyon / nova
        await settle(app, pilot)
        assert app.query_one(MainTabs).active == 'nodes'
        panel = app.query_one(NodesPanel)
        assert (panel.site, panel.cluster) == ('lyon', 'nova')


async def test_digits_typed_in_the_search_form_stay_in_the_box() -> None:
    """Typing 32 in Cores doesn't switch to tab 3: the digits go in the box."""
    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press('4')
        app.query_one('#min-cores').focus()
        await pilot.press('3', '2')
        assert app.query_one(MainTabs).active == 'search'
        assert app.query_one('#min-cores').value == '32'


async def test_search_loads_nothing_until_its_tab_is_opened() -> None:
    """Every cluster's nodes load only once the Search tab is opened."""
    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        search = app.query_one(SearchPanel)
        assert search.found is None
        await pilot.press('4')
        await settle(app, pilot)
        assert search.found is not None
