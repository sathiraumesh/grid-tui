"""A table of items loaded from the API in the background, with a status
line under it, and r to reload.

    ╭─ heading ────────────────────────────╮
    │ COLUMN   COLUMN   …                   │
    │ row      row                          │  ← the cursor
    ╰─ $ curl … ───────────────────────────╯
     loading… / error: …                       ← the status line

A panel says what it loads (fetch), its columns and heading, and how a row
looks (row). The base runs fetch in the background (load), fills the table,
and shows "loading…" or the error. A failed load keeps the rows already
there.
"""

from __future__ import annotations

from typing import Any, ClassVar, Generic, TypeVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from grid_tui.api import Api

Item = TypeVar("Item")


class ListPanel(Vertical, Generic[Item]):
    COLUMNS: ClassVar[tuple[str, ...]] = ()

    BINDINGS = [Binding("r", "reload", "Reload")]

    DEFAULT_CSS = """
    ListPanel DataTable {
        height: 1fr;
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
    }
    ListPanel .status { height: 1; padding: 0 1; color: $text-muted; }
    ListPanel .status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self.items: list[Item] = []

    # What each panel says.

    async def fetch(self) -> list[Item]:
        raise NotImplementedError

    def row(self, item: Item) -> tuple[Any, ...]:
        raise NotImplementedError

    def key(self, item: Item) -> str:
        raise NotImplementedError

    def heading(self) -> str:
        return ""

    def path(self) -> str:
        """The API path behind the panel, shown as a curl command."""
        return ""

    # What they share.

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Static("", classes="status", markup=False)

    @property
    def table(self) -> DataTable:
        return self.query_one(DataTable)

    def on_mount(self) -> None:
        self.table.add_columns(*self.COLUMNS)
        self.refresh_titles()

    def refresh_titles(self) -> None:
        self.table.border_title = self.heading()
        path = self.path()
        self.table.border_subtitle = "$ " + self.api.command(path) if path else ""

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load the items in the background, a loading animation over the
        table meanwhile, then show them."""
        self.set_status("loading…")
        self.table.loading = True
        try:
            items = await self.fetch()
        except Exception as e:  # the API's error, or no network
            self.set_status(f"error: {e}", error=True)
            self.loaded()
            return
        finally:
            self.table.loading = False
        self.show(items)
        self.set_status("")
        self.loaded()

    def loaded(self) -> None:
        """Called after every load, whether it worked or not."""

    def show(self, items: list[Item]) -> None:
        """Fill the table, keeping the cursor's row where it can."""
        row = self.table.cursor_row
        self.items = items
        self.table.clear()
        for item in items:
            self.table.add_row(*self.row(item), key=self.key(item))
        self.refresh_titles()
        if items:
            self.table.move_cursor(row=min(row, len(items) - 1))

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one(".status", Static)
        status.update(text)
        status.set_class(error, "error")

    @property
    def selected(self) -> Item | None:
        """The item under the cursor, if any."""
        if not self.items or not 0 <= self.table.cursor_row < len(self.items):
            return None
        return self.items[self.table.cursor_row]
