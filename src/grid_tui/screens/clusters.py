"""The clusters of one site. A click on one (or enter) opens its detail, g
its reservations; esc goes back to the sites.

    ╭─ site: nancy · clusters: 2 ─────────────────────────────────────╮
    │ CLUSTER    MODEL                 QUEUES              WATTMETER   │
    │ graffiti   Dell PowerEdge T640   production, admin   no          │
    │ gros       Dell PowerEdge R640   default, admin      yes         │
    ╰─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters ─────╯
"""

from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.widgets import DataTable

from grid_tui.models import Cluster, Site
from grid_tui.screens.base import Api, ListScreen
from grid_tui.screens.cluster import ClusterDetailScreen
from grid_tui.screens.reservations import ReservationsScreen


class ClustersScreen(ListScreen[Cluster]):
    """The clusters of a site."""

    COLUMNS = ("CLUSTER", "MODEL", "QUEUES", "WATTMETER")

    BINDINGS = [
        Binding("escape,backspace", "app.pop_screen", "Sites"),
        Binding("g", "reservations", "Reservations"),
        *ListScreen.BINDINGS,
    ]

    def __init__(self, api: Api, site: Site) -> None:
        super().__init__(api)
        self.site = site

    async def fetch(self) -> list[Cluster]:
        return await self.api.clusters(self.site.uid)

    def row(self, cluster: Cluster) -> tuple[Any, ...]:
        return (
            cluster.uid,
            cluster.model or "-",
            ", ".join(cluster.queues) or "-",
            "yes" if cluster.wattmeter else "no",
        )

    def key(self, cluster: Cluster) -> str:
        return cluster.uid

    def heading(self) -> str:
        return f"site: {self.site.uid} · clusters: {len(self.items)}"

    def path(self) -> str:
        return f"/sites/{self.site.uid}/clusters"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """A click on a cluster (or enter) opens its detail."""
        cluster = self.selected
        if cluster is not None:
            self.app.push_screen(ClusterDetailScreen(self.api, self.site, cluster))

    def action_reservations(self) -> None:
        """g: the reservations of the selected cluster (they load there)."""
        cluster = self.selected
        if cluster is not None:
            self.app.push_screen(ReservationsScreen(self.api, self.site, cluster))
