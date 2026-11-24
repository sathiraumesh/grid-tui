from textual.app import App
from textual.widgets import Footer

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

    def on_mount(self):
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'

    def compose(self):
        yield MainTabs()
        yield Footer()

    def action_reload(self) -> None:
        self.notify('Reloading…')

    def action_show_tab(self, tab: str) -> None:
        self.query_one(MainTabs).show(tab)


def main() -> None:
    Grid5KApp().run()
