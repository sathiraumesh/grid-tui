from textual.app import App
from textual.widgets import Footer

from grid_tui.grid5000 import Client
from grid_tui.panels.sites import SitesPanel
from grid_tui.widgets.main_tabs import MainTabs


class Grid5KApp(App):
    CSS_PATH = 'app.tcss'  # next to this file
    BINDINGS = [
        ('q', 'quit', 'Quit'),  # q runs Textual's built-in quit action
        ('r', 'reload', 'Reload'),
        ('1', "show_tab('sites')", 'Sites'),
        ('2', "show_tab('clusters')", 'Clusters'),
        ('3', "show_tab('nodes')", 'Nodes'),
    ]

    def __init__(self, client: Client | None = None) -> None:
        super().__init__()
        # the real API by default; tests pass a client with a fake API
        self.client = client or Client.from_env()

    def on_mount(self):
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'

    def compose(self):
        yield MainTabs(self.client)
        yield Footer()

    def action_reload(self) -> None:
        self.query_one(SitesPanel).load()

    def action_show_tab(self, tab: str) -> None:
        self.query_one(MainTabs).show(tab)


def main() -> None:
    Grid5KApp().run()
