"""What the screen tests share: a fake API, sample data, and helpers that
read what is on screen."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from textual.widgets import DataTable, Static

from grid_tui.app import GridTUI
from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware, JobRequest, Node, Reservation, Site

TWO_SITES = [Site("nancy", "Nancy", "Grid5000 Nancy site"), Site("rennes", "Rennes", "Grid5000 Rennes site")]

CLUSTERS = {
    "nancy": [
        Cluster("graffiti", "Dell PowerEdge T640", ("production", "admin")),
        Cluster("gros", "Dell PowerEdge R640", ("default", "admin"), ("wattmetre_power_watt",)),
    ],
    "rennes": [Cluster("paravance", "Dell PowerEdge R630", ("default",))],
}

GROS = Hardware(
    nodes=124,
    cpu="Intel Xeon Gold 5220",
    sockets=1,
    cores=18,
    threads=36,
    clock_ghz=2.2,
    memory=96 * 2**30,
    disks=(Disk("SSD", "SATA", 480 * 10**9), Disk("SSD", "SATA", 960 * 10**9)),
    nics=(NIC("Ethernet", 25 * 10**9),),
)

GPU_NODE = Hardware(nodes=2, cpu="AMD EPYC 7452", sockets=2, cores=64, memory=512 * 2**30,
                    gpus=(GPU("Nvidia", "A100", 40 * 2**30),) * 4)


def gros_nodes(now: datetime) -> list[Node]:
    """gros-1 free with eve's job later; gros-2 running bob's job; gros-10 dead."""
    hour = timedelta(hours=1)
    return [
        Node("gros-1", "alive", "free", (Reservation(4600, now + 3 * hour, now + 4 * hour, "eve", "default", "Waiting"),)),
        Node("gros-2", "alive", "busy", (Reservation(4521, now - hour, now + 2 * hour, "bob", "default", "Running"),)),
        Node("gros-10", "dead", "unknown"),
    ]


class FakeClient:
    """Answers with sites, or raises error; calls counts the loads."""

    def __init__(self, sites: list[Site] | None = None, error: Exception | None = None) -> None:
        self.result, self.error, self.calls = sites or [], error, 0
        self.gate: asyncio.Event | None = None  # set: loads wait for it
        self.clusters_error: Exception | None = None
        self.hardware_error: Exception | None = None
        self.hardware_gate: asyncio.Event | None = None
        self.nodes_error: Exception | None = None
        self.submitted: list[JobRequest] = []
        self.cancelled: list[int] = []
        self.jobs_error: Exception | None = None

    async def sites(self) -> list[Site]:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.result

    async def clusters(self, site: str) -> list[Cluster]:
        self.calls += 1
        if self.clusters_error is not None:
            raise self.clusters_error
        return CLUSTERS.get(site, [])

    async def hardware(self, site: str, cluster: str) -> Hardware:
        self.calls += 1
        if self.hardware_gate is not None:
            await self.hardware_gate.wait()
        if self.hardware_error is not None:
            raise self.hardware_error
        return {"gros": GROS, "graffiti": GPU_NODE}.get(cluster, Hardware())

    async def nodes(self, site: str, cluster: str) -> list[Node]:
        self.calls += 1
        if self.nodes_error is not None:
            raise self.nodes_error
        return gros_nodes(datetime.now().astimezone()) if cluster == "gros" else []

    async def submit_job(self, r: JobRequest) -> int:
        self.calls += 1
        if self.jobs_error is not None:
            raise self.jobs_error
        self.submitted.append(r)
        return 4710

    async def cancel_job(self, site: str, job_id: int) -> None:
        self.calls += 1
        if self.jobs_error is not None:
            raise self.jobs_error
        self.cancelled.append(job_id)

    async def site_nodes(self, site: str) -> list[Node]:
        """nancy: gros' nodes and two free graffiti; rennes: one free paravance."""
        self.calls += 1
        if self.nodes_error is not None:
            raise self.nodes_error
        free = lambda name: Node(name, "alive", "free")  # noqa: E731
        return {
            "nancy": gros_nodes(datetime.now().astimezone()) + [free("graffiti-1"), free("graffiti-2")],
            "rennes": [free("paravance-1")],
        }.get(site, [])

    def submit_command(self, r: JobRequest) -> str:
        return f"curl -X POST https://api.test/sites/{r.site}/jobs"

    def login(self) -> str:
        return "bob"  # gros-2's job 4521 is bob's

    def command(self, path: str) -> str:
        return "curl https://api.test" + path


def status(app: GridTUI) -> str:
    return str(app.screen.query_one("#status", Static).render())

def cells(app: GridTUI, row: int) -> list[str]:
    return [str(c) for c in app.screen.query_one(DataTable).get_row_at(row)]

def detail(app: GridTUI) -> str:
    """The detail screen's text, without its styling."""
    return app.screen.query_one("#detail", Static).render().plain


async def open_gros(pilot) -> None:
    await pilot.pause()
    await pilot.press("enter")  # nancy's clusters
    await pilot.pause()
    await pilot.press("down", "enter")  # gros
    await pilot.pause()
