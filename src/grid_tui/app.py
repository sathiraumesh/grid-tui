"""The Textual app: the main screen, its keys and its frame."""

from textual.app import App, ComposeResult
from textual.scrollbar import ScrollBar
from textual.widgets import Footer

from grid_tui.grid5000 import Client
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.panels.clusters import ClusterPanel
from grid_tui.widgets.panels.nodes import NodesPanel
from grid_tui.widgets.panels.reservations import ReservationsPanel
from grid_tui.widgets.panels.search import SearchPanel
from grid_tui.widgets.panels.sites import SitesPanel
from grid_tui.widgets.thin_scrollbar import ThinScrollBarRender
from grid_tui.widgets.usage_bar import UsageBar

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
        ('4', "show_tab('reservations')", 'Reservations'),
        ('5', "show_tab('search')", 'Search'),
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
        self._focused = True  # the terminal is in front (see polling)
        self._away = False  # another program, e.g. ssh, has the terminal

    @property
    def polling(self) -> bool:
        """May the app ask the API on its own (every few minutes)?

        Not while the terminal is in the background, nor during an SSH
        session: nobody is looking. What's old is loaded when you come back.
        """
        return self._focused and not self._away

    def on_app_blur(self) -> None:
        """The terminal went to the background: stop asking on a timer."""
        self._focused = False

    def on_app_focus(self) -> None:
        """The terminal is back in front: the timers catch up on their next tick."""
        self._focused = True

    def away(self, away: bool) -> None:
        """Say an SSH session (or another program) has the terminal, or not."""
        self._away = away

    def on_mount(self) -> None:
        """Put the app's name and credit in the frame, once the app starts."""
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'

    def compose(self) -> ComposeResult:
        """The app's widgets: the tabs, how busy it is (top right), the help line."""
        yield MainTabs(self.client)
        yield UsageBar(self.client)
        yield Footer()

    def on_sites_panel_chosen(self, message: SitesPanel.Chosen) -> None:
        """A site was chosen in the Sites tab: show its clusters."""
        self.query_one(MainTabs).show('clusters')
        self.query_one(ClusterPanel).show_site(message.site)
        self.query_one(UsageBar).show_site(message.site)

    def on_sites_panel_highlighted(self, message: SitesPanel.Highlighted) -> None:
        """You moved onto a site in the Sites tab: show its usage, top right."""
        self.query_one(UsageBar).show_site(message.site)

    def on_cluster_panel_chosen(self, message: ClusterPanel.Chosen) -> None:
        """A cluster was chosen in the Clusters tab: show its nodes."""
        self.query_one(MainTabs).show('nodes')
        self.query_one(NodesPanel).show_cluster(message.site, message.cluster)
        self.query_one(ReservationsPanel).show_cluster(message.site, message.cluster)
        self.query_one(UsageBar).show_site(message.site)

    def on_search_panel_chosen(self, message: SearchPanel.Chosen) -> None:
        """A cluster was chosen in the Search tab: show its nodes."""
        self.query_one(MainTabs).show('nodes')
        self.query_one(NodesPanel).show_cluster(message.site, message.cluster)
        self.query_one(ReservationsPanel).show_cluster(message.site, message.cluster)
        self.query_one(UsageBar).show_site(message.site)

    def on_resize(self) -> None:
        """The terminal changed size: keep the usage line in the top-right corner."""
        self.query_one(UsageBar).place()

    async def on_unmount(self) -> None:
        """The app is closing: close the connection to the API."""
        await self.client.aclose()

    def action_reload(self) -> None:
        """Load the tab that is showing again, from the API, not the cache (r)."""
        tab = self.query_one(MainTabs).active
        if tab == 'sites':
            self.query_one(SitesPanel).load(refresh=True)
        elif tab == 'clusters':
            self.query_one(ClusterPanel).load(refresh=True)
        elif tab == 'nodes':
            self.query_one(NodesPanel).load(refresh=True)
        elif tab == 'reservations':
            self.query_one(ReservationsPanel).load(refresh=True)
        elif tab == 'search':
            self.query_one(SearchPanel).load(refresh=True)

    def action_show_tab(self, tab: str) -> None:
        """Switch to the tab with this id (the 1 to 5 keys)."""
        self.query_one(MainTabs).show(tab)


def main() -> None:
    """Start the app: what the grid-tui command runs."""
    Grid5KApp().run()
