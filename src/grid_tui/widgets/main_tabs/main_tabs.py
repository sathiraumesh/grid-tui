"""The tab bar at the top of the app."""

from pathlib import Path

from textual.widget import Widget
from textual.widgets import Label, TabbedContent, TabPane

from grid_tui.grid5000 import Client
from grid_tui.panels.sites import SitesPanel


class MainTabs(Widget):
    """The tab bar at the top of the app, with one panel per tab."""

    # styles live in main_tabs.tcss next to this file
    DEFAULT_CSS = (Path(__file__).parent / 'main_tabs.tcss').read_text()

    def __init__(self, client: Client, **kwargs) -> None:
        """Make the tabs.

        Args:
            client: How to reach the API; passed on to the panels.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client

    def compose(self):
        """The tabs and their panels: Sites, Clusters and Nodes."""
        with TabbedContent(initial='sites'):
            with TabPane('Sites', id='sites'):
                yield SitesPanel(self.client)
            with TabPane('Clusters', id='clusters'):
                yield Label('Clusters will go here')
            with TabPane('Nodes', id='nodes'):
                yield Label('Nodes will go here')

    @property
    def active(self) -> str:
        """The id of the tab that is showing."""
        return self.query_one(TabbedContent).active

    def show(self, tab: str) -> None:
        """Switch to the tab with this id."""
        self.query_one(TabbedContent).active = tab
