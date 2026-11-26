"""The Textual app: the main screen, its keys and its frame."""

from textual.app import App, ComposeResult
from textual.scrollbar import ScrollBar
from textual.widgets import Footer

from grid_tui.grid5000 import Client
from grid_tui.panels.clusters import ClusterPanel
from grid_tui.panels.nodes import NodesPanel
from grid_tui.panels.search import SearchPanel
from grid_tui.panels.sites import SitesPanel
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.thin_scrollbar import ThinScrollBarRender

# every scrollbar in the app: a thin line, the same thickness both ways
ScrollBar.renderer = ThinScrollBarRender


class Grid5KApp(App):
    """The grid-tui app: tabs of Grid'5000 data inside an orange frame."""

    CSS_PATH = 'app.tcss'  # next to this file
    BINDINGS = [
        ('q', 'quit', 'Quit'),  # q runs Textual's built-in quit action
        ('r', 'reload', 'Reload'),
        ('1', "show_tab('sites')", 'Sites'),
        ('2', "show_tab('clusters')", 'Clusters'),
        ('3', "show_tab('nodes')", 'Nodes'),
        ('4', "show_tab('search')", 'Search'),
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

    def on_mount(self) -> None:
        """Put the app's name and credit in the frame, once the app starts."""
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'

    def compose(self) -> ComposeResult:
        """The app's widgets: the tabs, and the help line at the bottom."""
        yield MainTabs(self.client)
        yield Footer()

    def on_sites_panel_chosen(self, message: SitesPanel.Chosen) -> None:
        """A site was chosen in the Sites tab: show its clusters."""
        self.query_one(MainTabs).show('clusters')
        self.query_one(ClusterPanel).show_site(message.site)

    def on_cluster_panel_chosen(self, message: ClusterPanel.Chosen) -> None:
        """A cluster was chosen in the Clusters tab: show its nodes."""
        self.query_one(MainTabs).show('nodes')
        self.query_one(NodesPanel).show_cluster(message.site, message.cluster)

    def on_search_panel_chosen(self, message: SearchPanel.Chosen) -> None:
        """A cluster was chosen in the Search tab: show its nodes."""
        self.query_one(MainTabs).show('nodes')
        self.query_one(NodesPanel).show_cluster(message.site, message.cluster)

    def action_reload(self) -> None:
        """Load every tab again (the r key)."""
        self.query_one(SitesPanel).load()
        self.query_one(ClusterPanel).load()
        self.query_one(NodesPanel).load()
        self.query_one(SearchPanel).load()

    def action_show_tab(self, tab: str) -> None:
        """Switch to the tab with this id (the 1, 2, 3 and 4 keys)."""
        self.query_one(MainTabs).show(tab)


def main() -> None:
    """Start the app: what the grid-tui command runs."""
    Grid5KApp().run()
