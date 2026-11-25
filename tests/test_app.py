"""Tests for the whole app: its frame, its keys, and how the tabs work together."""

from textual.widgets import DataTable, Select

from grid_tui.app import Grid5KApp
from grid_tui.panels.clusters import ClusterPanel
from grid_tui.panels.sites import SitesPanel
from grid_tui.widgets.main_tabs import MainTabs
from tests.grid5000.fakes import fake_client, g5k_client
from tests.panels.helpers import rows, settle


async def test_frame_shows_title_and_subtitle():
    """The frame shows Grid'5000 at the top and the credit at the bottom."""
    app = Grid5KApp(fake_client())
    async with app.run_test():  # runs the app headless, no real terminal
        assert app.screen.border_title == "Grid'5000"
        assert app.screen.border_subtitle == 'Powered by IP Paris'


async def test_stylesheet_is_applied():
    """app.tcss is loaded: the dark background and the orange frame."""
    app = Grid5KApp(fake_client())
    async with app.run_test():
        styles = app.screen.styles
        assert styles.background.hex == '#1E1E2E'

        edge_type, edge_color = styles.border_top
        assert edge_type == 'round'
        assert edge_color.hex == '#FAB387'  # orange frame

        assert styles.border_subtitle_color.hex == '#A6ADC8'


async def test_q_quits():
    """q closes the app cleanly."""
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:  # pilot presses keys and clicks
        await pilot.press('q')
    assert app.return_code == 0


async def test_number_keys_switch_tabs():
    """1 and 2 switch to the Sites and Clusters tabs."""
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:
        tabs = app.query_one(MainTabs)
        assert tabs.active == 'sites'
        await pilot.press('2')
        assert tabs.active == 'clusters'
        await pilot.press('1')
        assert tabs.active == 'sites'


# Choosing a site opens its clusters


async def test_choosing_a_site_opens_its_clusters():
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


async def test_r_reloads_sites_and_clusters():
    """r loads both tables again."""
    app = Grid5KApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        sites = app.query_one(SitesPanel).query_one(DataTable)
        clusters = app.query_one(ClusterPanel).query_one(DataTable)
        sites.clear()
        clusters.clear()
        await pilot.press('r')
        await settle(app, pilot)
        assert sites.row_count == 2
        assert clusters.row_count == 3
