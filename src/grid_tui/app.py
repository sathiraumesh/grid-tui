"""The Textual app: it opens on the list of Grid'5000 sites; a click on one
opens its clusters."""

from __future__ import annotations

from textual.app import App

from grid_tui.grid5000 import Client
from grid_tui.screens import Api, SitesScreen


class GridTUI(App):
    """grid-tui's app."""

    TITLE = "grid-tui"
    SUB_TITLE = "Grid'5000"

    def __init__(self, client: Api | None = None) -> None:
        super().__init__()
        self.client = client if client is not None else Client.from_env()

    def on_mount(self) -> None:
        self.push_screen(SitesScreen(self.client))


def main() -> None:
    GridTUI().run()


if __name__ == "__main__":
    main()
