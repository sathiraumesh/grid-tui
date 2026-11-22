"""A reservation to ask OAR for."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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
