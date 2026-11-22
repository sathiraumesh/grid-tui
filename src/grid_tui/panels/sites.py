"""Sites: every Grid'5000 site. enter (or a click) opens its clusters.

    ╭─ sites: 2 ───────────────────────────────────────╮
    │ SITE     NAME     DESCRIPTION                     │
    │ nancy    Nancy    Grid5000 Nancy site             │
    ╰─ $ curl https://api.grid5000.fr/stable/sites ─────╯
"""

from __future__ import annotations

from typing import Any

from textual import on
from textual.widgets import DataTable

from grid_tui.models import Site
from grid_tui.panels.messages import SiteChosen, SitesLoaded
from grid_tui.widgets.list_panel import ListPanel


class SitesPanel(ListPanel[Site]):
    COLUMNS = ("SITE", "NAME", "DESCRIPTION")

    def on_mount(self) -> None:
        # Textual runs ListPanel.on_mount too (every class's, in turn): only what's added here.
        self.load()

    def loaded(self) -> None:
        """After every load: the first one ends the splash."""
        self.post_message(SitesLoaded())

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

    @on(DataTable.RowSelected)
    def chosen(self) -> None:
        if self.selected is not None:
            self.post_message(SiteChosen(self.selected))
