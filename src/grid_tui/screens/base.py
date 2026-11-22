"""What every list screen shares: a table loaded from the API in the
background, a status line under it, and r to reload.

    ╭─ title ──────────────────────────────╮
    │ COLUMN   COLUMN   …                   │
    │ row      row                          │  ← the cursor
    ╰─ $ curl … ───────────────────────────╯
     loading… / error: …                       ← the status line
     footer: the keys

A screen says what it loads (fetch), its columns and heading, and how a row
looks (row). The base runs fetch in the background when the screen opens
and on r, fills the table, and shows "loading…" or the error. A failed
load keeps the rows already there.
"""

from __future__ import annotations

from typing import Any, ClassVar, Generic, Protocol, TypeVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from grid_tui.models import Cluster, Site

Item = TypeVar("Item")


class Api(Protocol):
    """What the screens load with: grid5000.Client in the app, a fake in tests."""

    async def sites(self) -> list[Site]: ...

    async def clusters(self, site: str) -> list[Cluster]: ...

    def command(self, path: str) -> str: ...


class ListScreen(Screen, Generic[Item]):
    """A table of items loaded from the API."""

    COLUMNS: ClassVar[tuple[str, ...]] = ()

    BINDINGS = [
        Binding("r", "reload", "Reload"),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    ListScreen DataTable {
        height: 1fr;
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
    }
    ListScreen #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    ListScreen #status.error {
        color: $error;
        text-style: bold;
    }
    """

    def __init__(self, api: Api) -> None:
        super().__init__()
        self.api = api
        self.items: list[Item] = []

    # What each screen says.

    async def fetch(self) -> list[Item]:
        """Load the items from the API."""
        raise NotImplementedError

    def row(self, item: Item) -> tuple[Any, ...]:
        """The cells of an item, one per column."""
        raise NotImplementedError

    def key(self, item: Item) -> str:
        """An item's key in the table."""
        raise NotImplementedError

    def heading(self) -> str:
        """The table's title, on its top border."""
        return ""

    def path(self) -> str:
        """The API path behind the screen, shown as a curl command."""
        return ""

    # What they share.

    def compose(self) -> ComposeResult:
        yield Header()
        table: DataTable = DataTable(cursor_type="row", zebra_stripes=True)
        table.border_title = self.heading()
        table.border_subtitle = "$ " + self.api.command(self.path())
        yield table
        yield Static("", id="status")
        yield Footer()

    @property
    def table(self) -> DataTable:
        return self.query_one(DataTable)

    def on_mount(self) -> None:
        self.table.add_columns(*self.COLUMNS)
        self.load()

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load the items in the background, then show them."""
        self.set_status("loading…")
        try:
            items = await self.fetch()
        except Exception as e:  # the API's error, or no network
            self.set_status(f"error: {e}", error=True)
            return
        self.show(items)
        self.set_status("")

    def show(self, items: list[Item]) -> None:
        """Fill the table, keeping the cursor's row where it can."""
        row = self.table.cursor_row
        self.items = items
        self.table.clear()
        for item in items:
            self.table.add_row(*self.row(item), key=self.key(item))
        self.table.border_title = self.heading()
        if items:
            self.table.move_cursor(row=min(row, len(items) - 1))

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")

    @property
    def selected(self) -> Item | None:
        """The item under the cursor, if any."""
        if not self.items:
            return None
        return self.items[self.table.cursor_row]
