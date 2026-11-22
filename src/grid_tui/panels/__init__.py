"""The app's panels: what each tab of the main screen shows.

    sites.py          1 Sites: every site
    clusters.py       2 Clusters: the clusters of the site picked
    nodes.py          3 Nodes: the cluster picked, its hardware and its nodes
    reservations.py   4 Reservations › Current: a cluster's reservations (time line, week, month)
    reserve.py        5 Reservations › Reserve: which clusters can take a window; reserving
    jobs.py           6 Reservations › My reservations: your jobs on every site
    search.py         7 Search: the clusters of every site that meet some requirements
    messages.py       what they tell the main screen, to move between the tabs
"""

from grid_tui.panels.clusters import ClustersPanel
from grid_tui.panels.jobs import JobsPanel
from grid_tui.panels.nodes import NodesPanel
from grid_tui.panels.reservations import ReservationsPanel
from grid_tui.panels.reserve import ReservePanel
from grid_tui.panels.search import SearchPanel
from grid_tui.panels.sites import SitesPanel

__all__ = ["ClustersPanel", "JobsPanel", "NodesPanel", "ReservationsPanel", "ReservePanel", "SearchPanel", "SitesPanel"]
