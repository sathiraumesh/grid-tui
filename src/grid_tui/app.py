"""The Textual app: the main screen, its keys and its frame.

Before the tabs comes your login. The first time, a sign-up screen asks for
your Grid'5000 login and a PIN, and saves the login encrypted with the PIN
(see grid_tui.vault). After that, a login screen asks only for the PIN.
Forgot it? Sign up again from there.

No login screen when G5K_USER is set in the environment (that login is used
as it is), nor when a client is given (tests).
"""

import os
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.scrollbar import ScrollBar
from textual.widgets import Footer

from grid_tui.grid5000 import Cache, Client
from grid_tui.grid5000.base import DEFAULT_BASE_URL
from grid_tui.vault import Credentials, Vault
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.panels.clusters import ClusterPanel
from grid_tui.widgets.panels.jobs import JobsPanel
from grid_tui.widgets.panels.nodes import NodesPanel
from grid_tui.widgets.panels.reservations import ReservationsPanel
from grid_tui.widgets.panels.search import SearchPanel
from grid_tui.widgets.panels.sites import SitesPanel
from grid_tui.widgets.popups.login import LoginScreen, SignUpScreen
from grid_tui.widgets.thin_scrollbar import ThinScrollBarRender
from grid_tui.widgets.usage_bar import UsageBar

# every scrollbar in the app: a thin line, the same thickness both ways
ScrollBar.renderer = ThinScrollBarRender


def connect(credentials: Credentials) -> Client:
    """A client on the real API (or G5K_API's) with this login, and a cache."""
    return Client(
        base_url=os.environ.get('G5K_API') or DEFAULT_BASE_URL,
        user=credentials.user,
        password=credentials.password,
        cache=Cache(),
    )


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
        ('6', "show_tab('jobs')", 'Jobs'),
    ]

    def __init__(
        self,
        client: Client | None = None,
        *,
        vault: Vault | None = None,
        connect: Callable[[Credentials], Client] = connect,
    ) -> None:
        """Make the app.

        Args:
            client: How to reach the API. Leave it out to log in first (or,
                with G5K_USER set, to use the environment's login).
            vault: Where the login is saved encrypted; None for the default
                (~/.grid-secret/credentials.vault).
            connect: Makes a client from a login; tests give a fake API.
        """
        super().__init__()
        if client is None and os.environ.get('G5K_USER'):
            client = Client.from_env()  # a login in the environment: use it
        # None until you log in; tests pass a client with a fake API
        self.client: Client | None = client
        self.vault = vault or Vault()
        self.connect = connect
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
        """Put the app's name and credit in the frame; log in if need be."""
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'
        if self.client is None:
            first = self.vault.exists()
            screen = (LoginScreen if first else SignUpScreen)(self.vault, self.check)
            self.push_screen(screen, self.logged_in)

    def compose(self) -> ComposeResult:
        """The app's widgets: the tabs, how busy it is (top right), the help line.

        Not until you've logged in: they need the client.
        """
        if self.client is not None:
            yield from self.main_widgets(self.client)

    @staticmethod
    def main_widgets(client: Client) -> list:
        """The tabs, how busy it is (top right), and the help line."""
        return [MainTabs(client), UsageBar(client), Footer()]

    async def check(self, credentials: Credentials) -> None:
        """Try a login on the API (signing up): raises ApiError if refused."""
        client = self.connect(credentials)
        try:
            await client.sites.list(refresh=True)
        finally:
            await client.aclose()

    def logged_in(self, credentials: Credentials | None) -> None:
        """You're in: connect with the login, and show the tabs."""
        if credentials is None:
            return
        self.client = self.connect(credentials)
        self.mount_all(self.main_widgets(self.client))

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

    def on_jobs_panel_chosen(self, message: JobsPanel.Chosen) -> None:
        """A job was chosen in the Jobs tab: show its cluster's reservations."""
        # let go of the focus first: else it moves to the next widget of the
        # Jobs tab (its Machines list), and the tabs follow it straight back
        self.set_focus(None)
        self.query_one(MainTabs).show('reservations')
        self.query_one(ReservationsPanel).show_cluster(message.site, message.cluster)
        self.query_one(NodesPanel).show_cluster(message.site, message.cluster)
        self.query_one(UsageBar).show_site(message.site)

    def on_resize(self) -> None:
        """The terminal changed size: keep the usage line in the top-right corner."""
        for usage_bar in self.query(UsageBar):  # none before you log in
            usage_bar.place()

    async def on_unmount(self) -> None:
        """The app is closing: close the connection to the API."""
        if self.client is not None:
            await self.client.aclose()

    def action_reload(self) -> None:
        """Load the tab that is showing again, from the API, not the cache (r)."""
        if self.client is None:
            return  # not logged in yet
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
        elif tab == 'jobs':
            self.query_one(JobsPanel).load(refresh=True)

    def action_show_tab(self, tab: str) -> None:
        """Switch to the tab with this id (the 1 to 6 keys)."""
        if self.client is not None:
            self.query_one(MainTabs).show(tab)


def main() -> None:
    """Start the app: what the grid-tui command runs."""
    Grid5KApp().run()
