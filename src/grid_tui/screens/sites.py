"""The list of Grid'5000 sites. Clicking one (or enter) opens its clusters.

    ╭─ sites: 2 ───────────────────────────────────────╮
    │ SITE     NAME     DESCRIPTION                     │
    │ nancy    Nancy    Grid5000 Nancy site             │  ← the cursor
    │ rennes   Rennes   Grid5000 Rennes site            │
    ╰─ $ curl https://api.grid5000.fr/stable/sites ─────╯
"""

from __future__ import annotations

from typing import Any

from textual.widgets import DataTable

from grid_tui.models import Site
from grid_tui.screens.base import ListScreen
from grid_tui.screens.clusters import ClustersScreen


class SitesScreen(ListScreen[Site]):
    """The list of sites."""

    COLUMNS = ("SITE", "NAME", "DESCRIPTION")

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
