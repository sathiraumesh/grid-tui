"""The app's data, one model per file. It knows nothing about the API or
the screens.

    site.py      Site
    cluster.py   Cluster
"""

from grid_tui.models.cluster import Cluster
from grid_tui.models.site import Site

__all__ = ["Cluster", "Site"]
