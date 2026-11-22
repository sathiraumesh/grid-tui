"""The app's data, one model per file. It knows nothing about the API or
the screens.

    site.py      Site
    cluster.py   Cluster
    hardware.py  Hardware, and its Disk, NIC and GPU
"""

from grid_tui.models.cluster import Cluster
from grid_tui.models.hardware import GPU, NIC, Disk, Hardware
from grid_tui.models.site import Site

__all__ = ["Cluster", "Disk", "GPU", "Hardware", "NIC", "Site"]
