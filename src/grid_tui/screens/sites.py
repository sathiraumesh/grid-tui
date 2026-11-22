"""The list of Grid'5000 sites. Clicking one (or enter) opens its clusters;
/ opens the search, a what is reservable for a date and time.

    ╭─ sites: 2 ───────────────────────────────────────╮
    │ SITE     NAME     DESCRIPTION                     │
    │ nancy    Nancy    Grid5000 Nancy site             │  ← the cursor
    │ rennes   Rennes   Grid5000 Rennes site            │
    ╰─ $ curl https://api.grid5000.fr/stable/sites ─────╯
"""

from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.widgets import DataTable

from grid_tui.models import Site
from grid_tui.screens.base import ListScreen
from grid_tui.screens.clusters import ClustersScreen
from grid_tui.screens.reservable import ReservableScreen
from grid_tui.screens.search import SearchScreen


class SitesScreen(ListScreen[Site]):
    """The list of sites. / opens the search."""

    COLUMNS = ("SITE", "NAME", "DESCRIPTION")

    BINDINGS = [
        Binding("slash", "search", "Search"),
        Binding("a", "reservable", "Reservable"),
        *ListScreen.BINDINGS,
    ]

    async def fetch(self) -> list[Site]:
        return await self.api.sites()

    def row(self, site: Site) -> tuple[Any, ...]:
        return (site.uid, site.name, site.description)

    def key(self, site: Site) -> str:
        return site.uid

    def heading(self) -> str:
        return f"sites: {len(self.items)}"

    def path(self) -> str:
        return "/sites"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """A click on a site (or enter) opens its clusters."""
        site = self.selected
        if site is not None:
            self.app.push_screen(ClustersScreen(self.api, site))

    def action_search(self) -> None:
        """Open the search. It is made once and kept, with what it loaded."""
        if not self.app.is_screen_installed("search"):
            self.app.install_screen(SearchScreen(self.api, self.items or None), "search")
        self.app.push_screen("search")

    def action_reservable(self) -> None:
        """Which clusters can take a reservation for a date and time. Made
        once and kept, with what it loaded."""
        if not self.app.is_screen_installed("reservable"):
            self.app.install_screen(ReservableScreen(self.api, self.items or None), "reservable")
        self.app.push_screen("reservable")
