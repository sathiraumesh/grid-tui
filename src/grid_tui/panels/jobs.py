"""Reservations › My reservations: your jobs on every site, waiting,
launching or running. x cancels one (after a yes); enter opens its
cluster's current reservations.

    ╭─ my reservations: 2 · bob ────────────────────────────────────────────────────╮
    │ SITE    JOB    NAME      STATE     START          END     LENGTH  NODES        │
    │ nancy   4710   grid-tui  Waiting   Sun 22 18:00   20:00   2h      2 × gros     │
    │ lyon    1234   grid-tui  Running   13:00          17:00   4h      1 × nova     │
    ╰─ $ curl https://api.grid5000.fr/stable/sites/{site}/jobs?user=bob&state=… ─────╯

They load the first time the tab is opened, every site at the same time;
r loads them again. A site that fails is said; the others still show.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime
from typing import Any

from textual import on, work
from textual.binding import Binding
from textual.widgets import DataTable

from grid_tui.format import clock, duration
from grid_tui.models import Cluster, Job, Site
from grid_tui.models.reservable import cluster_of
from grid_tui.panels.messages import ClusterChosen
from grid_tui.screens.reserve import ConfirmDialog
from grid_tui.widgets.list_panel import ListPanel


class JobsPanel(ListPanel[Job]):
    COLUMNS = ("SITE", "JOB", "NAME", "STATE", "START", "END", "LENGTH", "NODES", "QUEUE")

    BINDINGS = [
        Binding("x", "cancel_job", "Cancel job"),
        Binding("g", "reservations", "Its reservations"),
        *ListPanel.BINDINGS,
    ]

    def __init__(self, api, **kwargs) -> None:
        super().__init__(api, **kwargs)
        self.started = False

    def activate(self) -> None:
        """The tab is shown: load the jobs, the first time."""
        if not self.started:
            self.started = True
            self.load()

    def heading(self) -> str:
        return f"my reservations: {len(self.items)} · {self.api.login() or '?'}"

    def path(self) -> str:
        return f"/sites/{{site}}/jobs?user={self.api.login()}&state=waiting,launching,running"

    def row(self, j: Job) -> tuple[Any, ...]:
        now = datetime.now().astimezone()
        per_cluster = Counter(cluster_of(n) for n in j.nodes)
        nodes = ", ".join(f"{n} × {c}" for c, n in per_cluster.items()) or "-"
        return (
            j.site, str(j.job_id), j.name or "-", j.state or "-",
            clock(j.start, now) if j.start else "not yet",
            clock(j.end, now) if j.end else "-",
            duration(j.walltime) if j.walltime else "-",
            nodes, j.queue or "-",
        )

    def key(self, j: Job) -> str:
        return f"{j.site}/{j.job_id}"

    @work(exclusive=True)
    async def load(self) -> None:
        """Every site's jobs at the same time; a site that fails is said."""
        user = self.api.login()
        if not user:
            self.set_status("who are you? set G5K_USER (or run on a frontend)", error=True)
            return
        self.set_status("loading…")
        self.table.loading = True
        try:
            sites = await self.api.sites()
            answers = await asyncio.gather(*(self.api.my_jobs(s.uid, user) for s in sites), return_exceptions=True)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            return
        finally:
            self.table.loading = False
        jobs = [j for a in answers if not isinstance(a, BaseException) for j in a]
        failed = [f"{s.uid}: {a}" for s, a in zip(sites, answers) if isinstance(a, BaseException)]
        self.show(sorted(jobs, key=lambda j: (j.start is None, j.start or datetime.max.astimezone(), j.site)))
        if failed:
            self.set_status("not every site answered: " + "; ".join(failed), error=True)
        elif not jobs:
            self.set_status("no reservations: make one in Reserve (5) or with b in Current (4)")
        else:
            self.set_status("")

    # Cancelling, and looking at a job's cluster.

    def action_cancel_job(self) -> None:
        j = self.selected
        if j is None:
            return
        now = datetime.now().astimezone()
        when = f"{clock(j.start, now)}→{clock(j.end, now)}" if j.start and j.end else "not scheduled yet"
        question = f"Cancel job #{j.job_id} at {j.site} ({j.name or '-'}, {when}, {len(j.nodes)} node(s))?"
        self.app.push_screen(ConfirmDialog(question), lambda yes: self.cancel(j) if yes else None)

    @work(exclusive=True, group="jobs")
    async def cancel(self, j: Job) -> None:
        self.set_status(f"cancelling job #{j.job_id}…")
        try:
            await self.api.cancel_job(j.site, j.job_id)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            self.notify(str(e), title="Not cancelled", severity="error", timeout=10)
            return
        self.notify(f"job #{j.job_id} at {j.site}", title="Cancelled")
        self.load()

    @on(DataTable.RowSelected)
    def action_reservations(self) -> None:
        """The current reservations of the job's (first) cluster."""
        j = self.selected
        if j is None:
            return
        if not j.clusters:
            self.notify(f"job #{j.job_id} has no nodes yet: OAR hasn't placed it", severity="warning")
            return
        self.post_message(ClusterChosen(Site(j.site), Cluster(j.clusters[0]), reservations=True))

