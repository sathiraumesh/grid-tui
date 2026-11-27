"""Tests for MainTabs: the tab bar and switching tabs."""

from textual.app import App, ComposeResult
from textual.widgets import TabbedContent

from grid_tui.widgets.main_tabs import MainTabs
from tests.grid5000.fakes import fake_client


class TabsApp(App):
    """A tiny app that shows only MainTabs, to test it on its own."""

    def compose(self) -> ComposeResult:
        """The only widget: the tabs, with a fake client."""
        yield MainTabs(fake_client())


async def test_starts_on_sites() -> None:
    """The Sites tab shows first."""
    app = TabsApp()
    async with app.run_test():
        assert app.query_one(MainTabs).active == 'sites'


async def test_has_a_tab_per_panel() -> None:
    """There are Sites, Clusters, Nodes, Reservations, Search and Jobs tabs."""
    app = TabsApp()
    async with app.run_test():
        panes = app.query_one(TabbedContent).query('TabPane')
        assert [pane.id for pane in panes] == [
            'sites',
            'clusters',
            'nodes',
            'reservations',
            'search',
            'jobs',
        ]


async def test_show_switches_tab() -> None:
    """show() switches to the tab with that id."""
    app = TabsApp()
    async with app.run_test():
        tabs = app.query_one(MainTabs)
        tabs.show('clusters')
        assert tabs.active == 'clusters'
        assert app.query_one(TabbedContent).active == 'clusters'


async def test_stylesheet_is_loaded() -> None:
    """main_tabs.tcss is loaded: the tabs fill the screen."""
    app = TabsApp()
    async with app.run_test(size=(60, 12)):
        tabs = app.query_one(MainTabs)
        assert tabs.size.height == 12  # height: 1fr fills the screen
        panel = app.query_one('#sites SitesPanel')
        assert panel.size.height > 0  # the panel is not squashed to 0 rows
