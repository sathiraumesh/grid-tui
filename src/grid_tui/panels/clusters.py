"""Clusters: the clusters of the site chosen in Sites. enter (or a click)
opens a cluster's nodes; g its reservations.

    ╭─ site: nancy · clusters: 2 ─────────────────────────────────────╮
    │ CLUSTER    MODEL                 QUEUES              WATTMETER   │
    │ graffiti   Dell PowerEdge T640   production, admin   no          │
    │ gros       Dell PowerEdge R640   default, admin      yes         │
    ╰─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters ─────╯
"""

from __future__ import annotations

from typing import Any

from textual import on
from textual.binding import Binding
from textual.widgets import DataTable

from grid_tui.models import Cluster, Site
from grid_tui.panels.messages import ClusterChosen
from grid_tui.widgets.list_panel import ListPanel


class ClustersPanel(ListPanel[Cluster]):
    COLUMNS = ("CLUSTER", "MODEL", "QUEUES", "WATTMETER")

    BINDINGS = [Binding("g", "reservations", "Reservations"), *ListPanel.BINDINGS]

    def __init__(self, api, **kwargs) -> None:
        super().__init__(api, **kwargs)
        self.site: Site | None = None

    def on_mount(self) -> None:
        # Textual runs ListPanel.on_mount too (every class's, in turn): only what's added here.
        self.set_status("choose a site in Sites (1)")

    def show_site(self, site: Site) -> None:
        """Show the clusters of site (loaded again only for another site)."""
        if self.site == site and self.items:
            return
        self.site = site
        self.show([])
        self.load()

    def action_reload(self) -> None:
        if self.site is not None:
            self.load()

    async def fetch(self) -> list[Cluster]:
        assert self.site is not None
        return await self.api.clusters(self.site.uid)

    def row(self, c: Cluster) -> tuple[Any, ...]:
        return (c.uid, c.model or "-", ", ".join(c.queues) or "-", "yes" if c.wattmeter else "no")

    def key(self, c: Cluster) -> str:
        return c.uid

    def heading(self) -> str:
        return f"site: {self.site.uid} · clusters: {len(self.items)}" if self.site else "clusters"

    def path(self) -> str:
        return f"/sites/{self.site.uid}/clusters" if self.site else ""

    @on(DataTable.RowSelected)
    def chosen(self) -> None:
        if self.site is not None and self.selected is not None:
            self.post_message(ClusterChosen(self.site, self.selected))

    def action_reservations(self) -> None:
        if self.site is not None and self.selected is not None:
            self.post_message(ClusterChosen(self.site, self.selected, reservations=True))
