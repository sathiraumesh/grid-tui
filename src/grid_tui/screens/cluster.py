"""One cluster in detail: what its nodes are made of, then every node (a
machine) with what it does now. esc goes back to the clusters.

    ╭─ site: nancy · cluster: gros ──────────────────────────────────────╮
    │  MODEL      Dell PowerEdge R640                                     │
    │  CPU        1 × Intel Xeon Gold 5220 · 18 cores · 36 threads · 2.2 GHz
    │  …                                                                  │
    ╰─ $ curl …/sites/nancy/clusters/gros/nodes ─────────────────────────╯
    ╭─ nodes: 3 · free 1 · busy 1 · down 1 ──────────────────────────────╮
    │ NODE      STATE          NOW    JOB                                 │
    │ gros-1    alive/free     free   next #4600 eve 18:00→19:00 (1h)     │
    │ gros-2    alive/busy     busy   #4521 bob 13:30→16:30 (3h) Running  │
    │ gros-10   dead/unknown   down                                       │
    ╰─ $ curl …/sites/nancy/clusters/gros/status ────────────────────────╯

The hardware and the nodes load at the same time, in the background; a
part that fails shows its error, and the other part still shows.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timedelta

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware, Node, Reservation, Site
from grid_tui.screens.base import Api


class ClusterDetailScreen(Screen):
    """The detail of one cluster of a site."""

    BINDINGS = [
        Binding("escape,backspace", "app.pop_screen", "Clusters"),
        Binding("r", "reload", "Reload"),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    ClusterDetailScreen #detail, ClusterDetailScreen #nodes {
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
    }
    ClusterDetailScreen #detail { height: auto; padding: 0 1; }
    ClusterDetailScreen #nodes { height: 1fr; }
    ClusterDetailScreen #status { height: 1; padding: 0 1; color: $text-muted; }
    ClusterDetailScreen #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, site: Site, cluster: Cluster) -> None:
        super().__init__()
        self.api, self.site, self.cluster = api, site, cluster
        self.hardware: Hardware | None = None  # None while loading
        self.nodes: list[Node] = []
        self.loaded_at: datetime | None = None  # when the nodes were loaded: what "now" means

    def compose(self) -> ComposeResult:
        yield Header()
        detail = Static(self.text(), id="detail")
        detail.border_title = f"site: {self.site.uid} · cluster: {self.cluster.uid}"
        detail.border_subtitle = "$ " + self.api.command(
            f"/sites/{self.site.uid}/clusters/{self.cluster.uid}/nodes"
        )
        yield detail
        nodes: DataTable = DataTable(id="nodes", cursor_type="row", zebra_stripes=True)
        nodes.border_title = "nodes: loading"
        nodes.border_subtitle = "$ " + self.api.command(
            f"/sites/{self.site.uid}/clusters/{self.cluster.uid}/status"
        )
        yield nodes
        yield Static("", id="status", markup=False)  # an error's [ ] aren't styling
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#nodes", DataTable).add_columns("NODE", "STATE", "NOW", "JOB")
        self.load()

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load the hardware and the nodes at the same time, in the
        background, then show what came back."""
        self.set_status("loading…")
        hardware, nodes = await asyncio.gather(
            self.api.hardware(self.site.uid, self.cluster.uid),
            self.api.nodes(self.site.uid, self.cluster.uid),
            return_exceptions=True,  # one failing doesn't lose the other
        )
        errors = [e for e in (hardware, nodes) if isinstance(e, BaseException)]
        if not isinstance(hardware, BaseException):
            self.hardware = hardware
            self.query_one("#detail", Static).update(self.text())
        if not isinstance(nodes, BaseException):
            self.show_nodes(nodes, datetime.now().astimezone())
        if errors:
            self.set_status("error: " + "; ".join(str(e) for e in errors), error=True)
        else:
            self.set_status("")

    def show_nodes(self, nodes: list[Node], at: datetime) -> None:
        """Fill the nodes' table as they are at that moment, keeping the
        cursor's row where it can."""
        table = self.query_one("#nodes", DataTable)
        row = table.cursor_row
        self.nodes, self.loaded_at = nodes, at
        table.clear()
        for n in nodes:
            table.add_row(n.name, f"{n.hard}/{n.soft}", n.now(at), job_text(n.job(at), at), key=n.name)
        now = Counter(n.now(at) for n in nodes)
        table.border_title = (
            f"nodes: {len(nodes)} · free {now['free'] + now['besteffort']} · busy {now['busy']} · down {now['down']}"
        )
        if nodes:
            table.move_cursor(row=min(row, len(nodes) - 1))

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")

    def lines(self) -> list[tuple[str, str]]:
        """The detail as (label, value) pairs; the hardware's say "loading"
        until it is there."""
        c, hw = self.cluster, self.hardware
        known = [
            ("MODEL", c.model or "-"),
            ("QUEUES", ", ".join(c.queues) or "-"),
        ]
        if hw is None:
            hardware = [(label, "loading") for label in ("NODES", "CPU", "MEMORY", "STORAGE", "NETWORK", "GPU")]
        else:
            hardware = [
                ("NODES", str(hw.nodes) if hw.nodes else "-"),
                ("CPU", cpu(hw)),
                ("MEMORY", gib(hw.memory)),
                ("STORAGE", joined(disk(d) for d in hw.disks)),
                ("NETWORK", joined(nic(n) for n in hw.nics)),
                ("GPU", gpus(hw.gpus)),
            ]
        return known + hardware + [
            ("WATTMETER", "yes" if c.wattmeter else "no"),
            ("METRICS", ", ".join(c.metrics) or "-"),
        ]

    def text(self) -> str:
        """The detail as text: a bold label, then its value."""
        width = max(len(label) for label, _ in self.lines())
        return "\n".join(f"[b]{label:<{width}}[/b]  {escape(value)}" for label, value in self.lines())


# How a node's job reads.


def job_text(r: Reservation | None, now: datetime) -> str:
    """The job a node runs, or "next …" for one to come, e.g.
    "#4521 bob 13:30→16:30 (3h) Running"; "" for none."""
    if r is None:
        return ""
    text = f"#{r.job_id} {r.user or '-'} {clock(r.start, now)}→{clock(r.end, now)} ({duration(r.end - r.start)})"
    if r.besteffort:
        text += " besteffort"
    if r.start > now:
        return "next " + text
    return f"{text} {r.state}".rstrip()


def clock(t: datetime, now: datetime) -> str:
    """t as "15:04", with the day when it isn't now's day: "Mon 23 09:00"."""
    if t.date() == now.date():
        return t.strftime("%H:%M")
    return t.strftime("%a %d %H:%M")


def duration(d: timedelta) -> str:
    """d as "3h", "1h30m" or "45m"."""
    minutes = round(d.total_seconds() / 60)
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m}m"
    return f"{h}h" if h else f"{m}m"


# How the hardware reads.


def cpu(hw: Hardware) -> str:
    """e.g. "2 × Intel Xeon Gold 5220 · 36 cores · 72 threads · 2.2 GHz"."""
    name = hw.cpu
    if name and hw.sockets > 0:
        name = f"{hw.sockets} × {name}"
    parts = [
        name,
        f"{hw.cores} cores" if hw.cores else "",
        f"{hw.threads} threads" if hw.threads else "",
        f"{hw.clock_ghz:g} GHz" if hw.clock_ghz else "",
    ]
    return joined(parts)


def disk(d: Disk) -> str:
    """e.g. "480 GB SSD SATA"."""
    return " ".join(p for p in (gb(d.size), d.kind, d.interface) if p)


def nic(n: NIC) -> str:
    """e.g. "25 Gbps Ethernet"."""
    rate = f"{n.rate / 1e9:g} Gbps" if n.rate else ""
    return " ".join(p for p in (rate, n.interface) if p)


def gpus(gs: tuple[GPU, ...]) -> str:
    """e.g. "4 × Nvidia A100 40 GiB": the same cards counted together."""
    names = Counter(" ".join(p for p in (g.vendor, g.model, gib(g.memory)) if p) for g in gs)
    return joined(f"{n} × {name}" if n > 1 else name for name, n in names.items())


def gib(b: int) -> str:
    """A memory size in powers of 1024: "96 GiB", "1.5 TiB"; "" for none."""
    return _scaled(b, 1024, ("B", "KiB", "MiB", "GiB", "TiB"))


def gb(b: int) -> str:
    """A disk size in powers of 1000, as disks are sold: "480 GB"; "" for none."""
    return _scaled(b, 1000, ("B", "kB", "MB", "GB", "TB"))


def _scaled(v: float, step: int, units: tuple[str, ...]) -> str:
    if v <= 0:
        return ""
    i = 0
    while v >= step and i < len(units) - 1:
        v /= step
        i += 1
    return f"{round(v, 1):g} {units[i]}"


def joined(parts) -> str:
    """The non-empty parts joined by " · ", or "-" if there are none."""
    return " · ".join(p for p in parts if p) or "-"
