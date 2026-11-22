"""What the panels tell the main screen, which moves between the tabs.

    SiteChosen      a site was picked: its clusters
    ClusterChosen   a cluster was picked: its nodes (or straight to its reservations)
    NodeChosen      a node was picked: the cluster's reservations, on that node
    SitesLoaded     the sites' first load is over (or failed): the splash can go
"""

from __future__ import annotations

from textual.message import Message

from grid_tui.models import Cluster, Node, Site


class SiteChosen(Message):
    def __init__(self, site: Site) -> None:
        super().__init__()
        self.site = site


class ClusterChosen(Message):
    def __init__(self, site: Site, cluster: Cluster, *, reservations: bool = False) -> None:
        super().__init__()
        self.site, self.cluster, self.reservations = site, cluster, reservations


class NodeChosen(Message):
    def __init__(self, site: Site, cluster: Cluster, nodes: list[Node], node: int) -> None:
        super().__init__()
        self.site, self.cluster, self.nodes, self.node = site, cluster, nodes, node


class SitesLoaded(Message):
    pass
