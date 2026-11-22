"""The app's data, one model per file. It knows nothing about the API or
the screens.

    site.py      Site
    cluster.py   Cluster
    hardware.py  Hardware, and its Disk, NIC and GPU
    node.py      Node (a machine) and the Reservations (OAR jobs) holding it
    search.py    SearchEntry, Requirements: which clusters meet a search
    gantt.py     Gantt: a cluster's reservations on a time line, a week, a month
    job.py       JobRequest: a reservation to ask OAR for; Job: one of yours
    reservable.py  Availability: which clusters can take a reservation for a window
"""

from grid_tui.models.cluster import Cluster
from grid_tui.models.gantt import Gantt, Mode
from grid_tui.models.hardware import GPU, NIC, Disk, Hardware
from grid_tui.models.job import Job, JobRequest
from grid_tui.models.node import Node, Reservation, node_order
from grid_tui.models.reservable import Availability
from grid_tui.models.search import Requirements, SearchEntry
from grid_tui.models.site import Site

__all__ = ["Availability", "Cluster", "Disk", "GPU", "Gantt", "Mode", "Hardware", "Job", "JobRequest", "NIC", "Node", "Requirements", "Reservation", "SearchEntry", "Site", "node_order"]
