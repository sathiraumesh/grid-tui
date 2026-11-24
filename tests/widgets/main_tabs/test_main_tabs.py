from textual.app import App
from textual.widgets import Label, TabbedContent

from grid_tui.widgets.main_tabs import MainTabs


class TabsApp(App):
    """A tiny app that shows only MainTabs, to test it on its own."""

    def compose(self):
        yield MainTabs()


async def test_starts_on_sites():
    app = TabsApp()
    async with app.run_test():
        assert app.query_one(MainTabs).active == 'sites'


async def test_has_a_tab_per_panel():
    app = TabsApp()
    async with app.run_test():
        panes = app.query_one(TabbedContent).query('TabPane')
        assert [pane.id for pane in panes] == ['sites', 'clusters', 'nodes']


async def test_show_switches_tab():
    app = TabsApp()
    async with app.run_test():
        tabs = app.query_one(MainTabs)
        tabs.show('clusters')
        assert tabs.active == 'clusters'
        assert app.query_one(TabbedContent).active == 'clusters'


async def test_stylesheet_is_loaded():
    app = TabsApp()
    async with app.run_test(size=(60, 12)):
        tabs = app.query_one(MainTabs)
        assert tabs.size.height == 12  # height: 1fr fills the screen
        label = app.query_one('#sites Label', Label)
        assert label.size.height > 0  # the panel is not squashed to 0 rows
