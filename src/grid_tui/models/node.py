"""A node (a machine) of a cluster, and the OAR jobs holding it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Reservation:
    """An OAR job holding, or scheduled to hold, a node."""

    job_id: int
    start: datetime
    end: datetime
    user: str = ""
    queue: str = ""  # "default", "production", "besteffort"…
    state: str = ""  # "Running", "Waiting"…

    @property
    def besteffort(self) -> bool:
        """Besteffort jobs are killed when a regular job needs the node: they
        don't really keep it busy."""
        return self.queue == "besteffort"

    def holds(self, at: datetime) -> bool:
        """Whether the job holds the node at that moment."""
        return self.start <= at < self.end


@dataclass(frozen=True)
class Node:
    """One node of a cluster: its OAR states and its jobs (sorted by start)."""

    name: str  # short name, e.g. "gros-12"
    hard: str = ""  # alive, absent, suspected, dead
    soft: str = ""  # free, busy, busy_besteffort, unknown
    reservations: tuple[Reservation, ...] = ()

    @property
    def usable(self) -> bool:
        """Whether it can take jobs: its hard state is alive."""
        return self.hard == "alive"

    def now(self, at: datetime) -> str:
        """What it does at that moment: "down", "busy", "besteffort" (only a
        besteffort job) or "free"."""
        if not self.usable:
            return "down"
        held = [r for r in self.reservations if r.holds(at)]
        if any(not r.besteffort for r in held):
            return "busy"
        return "besteffort" if held else "free"

    def slot(self, start: datetime, end: datetime) -> str:
        """What it does during [start, end): "down", "busy" (a regular job
        overlaps), "besteffort" (only besteffort ones) or "free"."""
        if not self.usable:
            return "down"
        held = [r for r in self.reservations if r.start < end and r.end > start]
        if any(not r.besteffort for r in held):
            return "busy"
        return "besteffort" if held else "free"

    def job(self, at: datetime) -> Reservation | None:
        """The job it runs at that moment (a regular one before a besteffort
        one), or else its next one; None if it has none left."""
        held = sorted((r for r in self.reservations if r.holds(at)), key=lambda r: r.besteffort)
        if held:
            return held[0]
        upcoming = [r for r in self.reservations if r.start > at]
        return min(upcoming, key=lambda r: r.start, default=None)


def node_order(node: Node) -> tuple[str, int, str]:
    """Sorts names with their numbers as numbers: gros-2 before gros-10."""
    m = re.fullmatch(r"(.*?)-?(\d+)", node.name)
    if m:
        return (m.group(1), int(m.group(2)), node.name)
    return (node.name, 0, node.name)
