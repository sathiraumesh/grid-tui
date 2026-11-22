"""The start-up screen: the app's name, and a loading animation, until the
sites have loaded (then the main screen shows; on an error too, to show it).

          ┏━╸┏━┓╻╺┳┓   ╺┳╸╻ ╻╻
          ┃╺┓┣┳┛┃ ┃┃╺━╸ ┃ ┃ ┃┃
          ┗━┛╹┗╸╹╺┻┛    ╹ ┗━┛╹
       a terminal UI for Grid'5000

               ● ● ●
          loading the sites…
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import LoadingIndicator, Static

LOGO = """\
┏━╸┏━┓╻╺┳┓   ╺┳╸╻ ╻╻
┃╺┓┣┳┛┃ ┃┃╺━╸ ┃ ┃ ┃┃
┗━┛╹┗╸╹╺┻┛    ╹ ┗━┛╹"""


class SplashScreen(Screen):
    BINDINGS = [Binding("q", "app.quit", "Quit"), Binding("escape", "app.pop_screen", "Skip", show=False)]

    DEFAULT_CSS = """
    SplashScreen { align: center middle; background: $background; }
    SplashScreen #logo { color: $accent; text-style: bold; width: auto; }
    SplashScreen #tagline { color: $text-muted; width: auto; margin-top: 1; }
    SplashScreen LoadingIndicator { height: 3; width: 20; margin-top: 1; }
    SplashScreen #what { color: $text-muted; width: auto; }
    """

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield Static(LOGO, id="logo")
            with Center():
                yield Static("a terminal UI for Grid'5000", id="tagline")
            with Center():
                yield LoadingIndicator()
            with Center():
                yield Static("loading the sites…", id="what", markup=False)

    def say(self, text: str) -> None:
        """What is being loaded."""
        self.query_one("#what", Static).update(text)
