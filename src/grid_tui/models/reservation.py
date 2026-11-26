"""A cluster's reservations, from GET /sites/{site}/clusters/{cluster}/status.

The status answer lists, for each node, the jobs on it now or later. A job on
many nodes is listed once per node; Schedule puts each job back together with
all its nodes.

    schedule = Schedule.from_status(answer)
    schedule.nodes          # {'gros-1': 'alive', 'gros-2': 'dead', ...}
    schedule.reservations   # [Reservation(uid=..., nodes={'gros-1', ...}), ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

UP = {'alive', 'standby'}  # a node that can run jobs (standby: off until needed)


def short_name(host: str) -> str:
    """'gros-12.nancy.grid5000.fr' → 'gros-12'."""
    return host.split('.', 1)[0]


def node_number(name: str) -> tuple[str, int]:
    """A key that sorts gros-2 before gros-10: ('gros', 2)."""
    match = re.match(r'^(.*?)-?(\d+)$', name)
    if not match:
        return (name, 0)
    return (match.group(1), int(match.group(2)))


@dataclass(frozen=True)
class Reservation:
    """One job on a cluster: who, what, when, on which nodes."""

    uid: int
    user: str = ''
    name: str = ''  # the job's name, if it was given one
    queue: str = ''  # e.g. 'default', 'admin', 'besteffort', 'production'
    state: str = ''  # e.g. 'running', 'waiting'
    start: int = 0  # when it starts (or started), in seconds since 1970
    end: int = 0  # when it ends at the latest (start + walltime)
    types: tuple[str, ...] = ()  # e.g. ('deploy', 'night')
    nodes: frozenset[str] = field(default_factory=frozenset)  # short names

    @property
    def is_running(self) -> bool:
        """Running now (not waiting for its start)."""
        return self.state in ('running', 'launching')

    @property
    def is_besteffort(self) -> bool:
        """A best-effort job: it is killed when someone needs its nodes."""
        return self.queue == 'besteffort' or 'besteffort' in self.types

    @property
    def is_maintenance(self) -> bool:
        """A job of the Grid'5000 staff (the admin queue)."""
        return self.queue == 'admin'

    def covers(self, moment: float) -> bool:
        """Does it hold its nodes at this moment."""
        return self.start <= moment < self.end


@dataclass(frozen=True)
class Schedule:
    """A cluster's nodes (with their state) and the reservations on them."""

    nodes: dict[str, str] = field(default_factory=dict)  # name → hard state
    reservations: tuple[Reservation, ...] = ()

    @property
    def node_names(self) -> list[str]:
        """The nodes, in number order: gros-1, gros-2, ..., gros-10."""
        return sorted(self.nodes, key=node_number)

    @property
    def up(self) -> int:
        """How many nodes can run jobs."""
        return sum(state in UP for state in self.nodes.values())

    def on(self, node: str) -> list[Reservation]:
        """The reservations on one node, earliest first."""
        found = [r for r in self.reservations if node in r.nodes]
        return sorted(found, key=lambda r: (r.start, r.uid))

    def free_at(self, moment: float) -> int:
        """How many up nodes no reservation holds at a moment."""
        held = set()
        for reservation in self.reservations:
            if reservation.covers(moment):
                held |= reservation.nodes
        return sum(
            1 for node, state in self.nodes.items() if state in UP and node not in held
        )

    def free_between(self, start: float, end: float) -> list[str]:
        """The up nodes that no reservation holds at any time from start to end."""
        held = set()
        for reservation in self.reservations:
            if reservation.start < end and start < reservation.end:
                held |= reservation.nodes
        return [
            node
            for node in self.node_names
            if self.nodes[node] in UP and node not in held
        ]

    def find_slot(
        self, nodes: int, seconds: float, after: float
    ) -> tuple[float, list[str]] | None:
        """The first time from `after` when enough nodes are free for long enough.

        A slot can only open now or when a reservation ends, so those are the
        times tried, earliest first.

        Args:
            nodes: How many nodes are needed.
            seconds: For how long.
            after: The earliest start, e.g. now.

        Returns:
            (start, free nodes) for the first slot; None if none is known (the
            schedule only reaches as far as the reservations do, so after the
            last one ends every up node is free: None means too few are up).
        """
        if nodes <= 0 or seconds <= 0:
            return None
        starts = sorted({after, *(r.end for r in self.reservations if r.end > after)})
        for start in starts:
            free = self.free_between(start, start + seconds)
            if len(free) >= nodes:
                return start, free
        return None

    @classmethod
    def from_status(cls, answer: Any) -> Schedule:
        """Read a cluster's status answer.

        A reservation with no start yet (waiting, not scheduled) is left out:
        there's no time to draw it at.

        Args:
            answer: The JSON of GET /sites/{site}/clusters/{cluster}/status.
        """
        hosts = answer.get('nodes') if isinstance(answer, dict) else None
        if not isinstance(hosts, dict):
            return cls()
        nodes: dict[str, str] = {}
        jobs: dict[int, dict] = {}
        on_nodes: dict[int, set[str]] = {}
        for host, status in hosts.items():
            if not isinstance(status, dict):
                continue
            name = short_name(host)
            nodes[name] = str(status.get('hard') or 'unknown')
            for job in status.get('reservations') or []:
                if not isinstance(job, dict) or 'uid' not in job:
                    continue
                jobs.setdefault(job['uid'], job)
                on_nodes.setdefault(job['uid'], set()).add(name)
        reservations = []
        for uid, job in jobs.items():
            start = job.get('started_at') or job.get('scheduled_at') or 0
            if not start:
                continue
            reservations.append(
                Reservation(
                    uid=uid,
                    user=str(job.get('user') or ''),
                    name=str(job.get('name') or ''),
                    queue=str(job.get('queue') or ''),
                    state=str(job.get('state') or ''),
                    start=int(start),
                    end=int(start) + int(job.get('walltime') or 0),
                    types=tuple(job.get('types') or ()),
                    nodes=frozenset(on_nodes[uid]),
                )
            )
        reservations.sort(key=lambda r: (r.start, r.uid))
        return cls(nodes, tuple(reservations))
