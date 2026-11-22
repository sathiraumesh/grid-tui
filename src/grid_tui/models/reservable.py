"""Which clusters can be reserved for a given window: nodes nodes free all
through [start, start + walltime).

A node is free all through when it is usable and no regular job overlaps
the window (a besteffort job doesn't count: OAR evicts it). This is what the
status said when it was loaded: OAR decides, and may still refuse.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from grid_tui.models.node import Node, node_order


def cluster_of(node_name: str) -> str:
    """The cluster of a node, from its name: "gros-12" → "gros"."""
    m = re.fullmatch(r"(.+?)-\d+", node_name)
    return m.group(1) if m else node_name


def by_cluster(nodes: Iterable[Node]) -> dict[str, list[Node]]:
    """A site's nodes, by cluster, each list in name order."""
    out: dict[str, list[Node]] = {}
    for n in nodes:
        out.setdefault(cluster_of(n.name), []).append(n)
    return {c: sorted(ns, key=node_order) for c, ns in sorted(out.items())}


@dataclass(frozen=True)
class Availability:
    """One cluster for one window."""

    site: str
    cluster: str
    free: int  # nodes free all through the window
    usable: int  # nodes that can take jobs at all
    wanted: int  # nodes asked for

    @property
    def reservable(self) -> bool:
        return self.free >= self.wanted

    def reason(self) -> str:
        """Why it is, or isn't, reservable."""
        if self.reservable:
            return "yes"
        if self.usable < self.wanted:
            return f"no: it has {self.usable} usable node(s)"
        return f"no: only {self.free} free"


def availability(site: str, cluster: str, nodes: Iterable[Node], start: datetime, end: datetime,
                 wanted: int) -> Availability:
    free = usable = 0
    for n in nodes:
        slot = n.slot(start, end)
        if slot == "down":
            continue
        usable += 1
        if slot != "busy":
            free += 1
    return Availability(site, cluster, free, usable, wanted)


def rank(found: Iterable[Availability]) -> list[Availability]:
    """Reservable first, then the most free nodes, then by site and cluster."""
    return sorted(found, key=lambda a: (not a.reservable, -a.free, a.site, a.cluster))
