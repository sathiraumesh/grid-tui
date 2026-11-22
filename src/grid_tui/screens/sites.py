"""The list of Grid'5000 sites.

    ╭─ sites: 2 ───────────────────────────────────────╮
    │ SITE     NAME     DESCRIPTION                     │
    │ nancy    Nancy    Grid5000 Nancy site             │  ← selected
    │ rennes   Rennes   Grid5000 Rennes site            │
    ╰─ $ curl https://api.grid5000.fr/stable/sites ─────╯
     loading… / error: … / r reload

The sites load in the background when the screen opens (and with r); the
table fills in when they arrive. A failed load shows its error and keeps
the sites already there.
"""

from __future__ import annotations

from typing import Protocol

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from grid_tui.models import Site


class SitesClient(Protocol):
    """What loads the sites: grid5000.Client in the app, a fake in tests."""

    async def sites(self) -> list[Site]: ...

    def command(self, path: str) -> str: ...


class SitesScreen(Screen):
    """The list of sites, loaded from the API."""

    BINDINGS = [
        Binding("r", "reload", "Reload"),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    SitesScreen #sites {
        height: 1fr;
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
    }
    SitesScreen #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    SitesScreen #status.error {
        color: $error;
        text-style: bold;
    }
    """

    def __init__(self, client: SitesClient) -> None:
        super().__init__()
        self.client = client
        self.sites: list[Site] = []

    def compose(self) -> ComposeResult:
        yield Header()
        table = DataTable(id="sites", cursor_type="row", zebra_stripes=True)
        table.border_title = "sites"
        table.border_subtitle = "$ " + self.client.command("/sites")
        yield table
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(DataTable).add_columns("SITE", "NAME", "DESCRIPTION")
        self.load()

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load the sites in the background, then show them."""
        self.set_status("loading…")
        try:
            sites = await self.client.sites()
        except Exception as e:  # the API's error, or no network
            self.set_status(f"error: {e}", error=True)
            return
        self.show(sites)
        self.set_status("")

    def show(self, sites: list[Site]) -> None:
        """Fill the table, keeping the selected row where it can."""
        table = self.query_one(DataTable)
        row = table.cursor_row
        self.sites = sites
        table.clear()
        for s in sites:
            table.add_row(s.uid, s.name, s.description, key=s.uid)
        table.border_title = f"sites: {len(sites)}"
        if sites:
            table.move_cursor(row=min(row, len(sites) - 1))

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")

    @property
    def selected(self) -> Site | None:
        """The site under the cursor, if any."""
        table = self.query_one(DataTable)
        if not self.sites:
            return None
        return self.sites[table.cursor_row]
