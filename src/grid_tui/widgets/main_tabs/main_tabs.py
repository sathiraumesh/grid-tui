"""The tab bar at the top of the app.

Showing a tab puts the focus in its panel (its table), so the panel's own keys
(e.g. w and m on Reservations, s on Jobs) show in the help line at once and
work without clicking into the panel first.
"""

from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, TabbedContent, TabPane

from grid_tui.grid5000 import Client
from grid_tui.widgets.panels.clusters import ClusterPanel
from grid_tui.widgets.panels.jobs import JobsPanel
from grid_tui.widgets.panels.nodes import NodesPanel
from grid_tui.widgets.panels.reservations import ReservationsPanel
from grid_tui.widgets.panels.search import SearchPanel
from grid_tui.widgets.panels.sites import SitesPanel


class MainTabs(Widget):
    """The tab bar at the top of the app, with one panel per tab."""

    # the tabs' ids, in order: what the 1 to 6 keys show
    TAB_IDS = ('sites', 'clusters', 'nodes', 'reservations', 'search', 'jobs')

    # styles live in main_tabs.tcss next to this file
    DEFAULT_CSS = (Path(__file__).parent / 'main_tabs.tcss').read_text()

    def __init__(self, client: Client, **kwargs: Any) -> None:
        """Make the tabs.

        Args:
            client: How to reach the API; passed on to the panels.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client

    def compose(self) -> ComposeResult:
        """The tabs: Sites, Clusters, Nodes, Reservations, Search and Jobs."""
        with TabbedContent(initial='sites'):
            with TabPane('Sites', id='sites'):
                yield SitesPanel(self.client)
            with TabPane('Clusters', id='clusters'):
                yield ClusterPanel(self.client)
            with TabPane('Nodes', id='nodes'):
                yield NodesPanel(self.client)
            with TabPane('Reservations', id='reservations'):
                yield ReservationsPanel(self.client)
            with TabPane('Search', id='search'):
                yield SearchPanel(self.client)
            with TabPane('Jobs', id='jobs'):
                yield JobsPanel(self.client)

    @property
    def active(self) -> str:
        """The id of the tab that is showing."""
        return self.query_one(TabbedContent).active

    def on_mount(self) -> None:
        """Start with the focus in the first tab's panel."""
        self.call_after_refresh(self._focus_panel)

    @on(TabbedContent.TabActivated)
    def _tab_shown(self) -> None:
        """A tab was shown (a key, a click, or another tab): focus its panel."""
        self.call_after_refresh(self._focus_panel)

    def _focus_panel(self) -> None:
        """Put the focus on the shown panel's table, if it has one.

        Its keys then show in the help line. Left alone if the focus is
        already inside that panel (e.g. in a form box you clicked).
        """
        tabs = self.query_one(TabbedContent)
        pane = tabs.active_pane
        if pane is None:
            return
        focused = self.screen.focused
        if focused is not None and pane in focused.ancestors:
            return
        tables = pane.query(DataTable)
        if tables:
            tables.first().focus()

    def show(self, tab: str) -> None:
        """Switch to the tab with this id."""
        self.query_one(TabbedContent).active = tab
