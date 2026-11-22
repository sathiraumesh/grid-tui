"""The app's screens, one per file.

    sites.py      the list of sites; a click (or enter) opens its clusters
    clusters.py   the clusters of a site; esc goes back
    base.py       what they share: a table loaded in the background
"""

from grid_tui.screens.base import Api, ListScreen
from grid_tui.screens.clusters import ClustersScreen
from grid_tui.screens.sites import SitesScreen

__all__ = ["Api", "ClustersScreen", "ListScreen", "SitesScreen"]
