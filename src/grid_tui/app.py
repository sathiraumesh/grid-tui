"""The Textual app: the main screen, its keys and its frame."""

from textual.app import App
from textual.widgets import Footer

from grid_tui.grid5000 import Client
from grid_tui.panels.clusters import ClusterPanel
from grid_tui.panels.sites import SitesPanel
from grid_tui.widgets.main_tabs import MainTabs


class Grid5KApp(App):
    """The grid-tui app: tabs of Grid'5000 data inside an orange frame."""

    CSS_PATH = 'app.tcss'  # next to this file
    BINDINGS = [
        ('q', 'quit', 'Quit'),  # q runs Textual's built-in quit action
        ('r', 'reload', 'Reload'),
        ('1', "show_tab('sites')", 'Sites'),
        ('2', "show_tab('clusters')", 'Clusters'),
        ('3', "show_tab('nodes')", 'Nodes'),
    ]

    def __init__(self, client: Client | None = None) -> None:
        """Make the app.

        Args:
            client: How to reach the API. Leave it out to use the real API
                with the login from the environment (see Client.from_env).
        """
        super().__init__()
        # the real API by default; tests pass a client with a fake API
        self.client = client or Client.from_env()

    def on_mount(self):
        """Put the app's name and credit in the frame, once the app starts."""
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'

    def compose(self):
        """The app's widgets: the tabs, and the help line at the bottom."""
        yield MainTabs(self.client)
        yield Footer()

    def action_reload(self) -> None:
        """Load the sites and clusters again (the r key)."""
        self.query_one(SitesPanel).load()
        self.query_one(ClusterPanel).load()

    def action_show_tab(self, tab: str) -> None:
        """Switch to the tab with this id (the 1, 2 and 3 keys)."""
        self.query_one(MainTabs).show(tab)


def main() -> None:
    """Start the app: what the grid-tui command runs."""
    Grid5KApp().run()
