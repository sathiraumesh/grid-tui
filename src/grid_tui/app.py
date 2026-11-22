"""The Textual app: an empty screen to build on."""

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class GridTUI(App):
    """grid-tui's app. For now: a header, an empty panel and a footer."""

    TITLE = "grid-tui"
    SUB_TITLE = "Grid'5000"

    CSS = """
    #main {
        height: 1fr;
        border: round $accent;
        padding: 1 2;
        color: $text-muted;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("nothing to show yet", id="main")
        yield Footer()


def main() -> None:
    GridTUI().run()


if __name__ == "__main__":
    main()
