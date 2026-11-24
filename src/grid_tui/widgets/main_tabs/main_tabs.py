from pathlib import Path

from textual.widget import Widget
from textual.widgets import Label, TabbedContent, TabPane


class MainTabs(Widget):
    """The tab bar at the top of the app, with one panel per tab."""

    # styles live in main_tabs.tcss next to this file
    DEFAULT_CSS = (Path(__file__).parent / 'main_tabs.tcss').read_text()

    def compose(self):
        with TabbedContent(initial='sites'):
            with TabPane('Sites', id='sites'):
                yield Label('Sites will go here')
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
