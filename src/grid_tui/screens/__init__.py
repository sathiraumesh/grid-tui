"""The app's screens, one per file.

    sites.py      the list of sites; a click (or enter) opens its clusters
    clusters.py   the clusters of a site; a click opens one; esc goes back
    cluster.py    one cluster in detail: its hardware; esc goes back
    base.py       what the lists share: a table loaded in the background
"""

from grid_tui.screens.base import Api, ListScreen
from grid_tui.screens.cluster import ClusterDetailScreen
from grid_tui.screens.clusters import ClustersScreen
from grid_tui.screens.sites import SitesScreen

__all__ = ["Api", "ClusterDetailScreen", "ClustersScreen", "ListScreen", "SitesScreen"]
