"""The clusters of one site. esc goes back to the sites.

    ╭─ site: nancy · clusters: 2 ─────────────────────────────────────╮
    │ CLUSTER    MODEL                 QUEUES              WATTMETER   │
    │ graffiti   Dell PowerEdge T640   production, admin   no          │
    │ gros       Dell PowerEdge R640   default, admin      yes         │
    ╰─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters ─────╯
"""

from __future__ import annotations

from typing import Any

from textual.binding import Binding

from grid_tui.models import Cluster, Site
from grid_tui.screens.base import Api, ListScreen


class ClustersScreen(ListScreen[Cluster]):
    """The clusters of a site."""

    COLUMNS = ("CLUSTER", "MODEL", "QUEUES", "WATTMETER")

    BINDINGS = [
        Binding("escape,backspace", "app.pop_screen", "Sites"),
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
