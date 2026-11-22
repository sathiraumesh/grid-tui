"""A reservation to ask OAR for."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from grid_tui.models.reservable import cluster_of

JOB_NAME = "grid-tui"  # the name the reservations made here get


@dataclass(frozen=True)
class JobRequest:
    """nodes nodes of a cluster for walltime, from start (None: as soon as
    possible)."""

    site: str
    cluster: str
    nodes: int
    walltime: timedelta
    start: datetime | None = None
    queue: str = "default"
    project: str = ""  # the Grid'5000 project it counts for; "" for none
    types: tuple[str, ...] = ()  # "deploy", "exotic"
    name: str = JOB_NAME

    def summary(self) -> str:
        """The request in words."""
        when = "as soon as possible" if self.start is None else f"from {self.start:%a %d %b %H:%M}"
        hours, rest = divmod(int(self.walltime.total_seconds()) // 60, 60)
        length = f"{hours}h{rest:02d}" if rest else f"{hours}h"
        text = f"{self.nodes} node(s) of {self.cluster} at {self.site}, {when}, for {length} · queue {self.queue}"
        if self.project:
            text += f" · project {self.project}"
        if self.types:
            text += " · " + ", ".join(self.types)
        return text


@dataclass(frozen=True)
class Job:
    """One of your OAR jobs, as GET /sites/{site}/jobs lists it."""

    site: str
    job_id: int
    state: str = ""  # "Waiting", "Launching", "Running"…
    user: str = ""
    name: str = ""
    queue: str = ""
    project: str = ""
    start: datetime | None = None  # started, or scheduled; None: not scheduled yet
    walltime: timedelta = timedelta(0)
    nodes: tuple[str, ...] = ()  # short names, e.g. ("gros-12", "gros-13")
    types: tuple[str, ...] = ()

    @property
    def end(self) -> datetime | None:
        return self.start + self.walltime if self.start is not None else None

    @property
    def clusters(self) -> tuple[str, ...]:
        """The clusters its nodes are in, e.g. ("gros",)."""
        return tuple(dict.fromkeys(cluster_of(n) for n in self.nodes))
