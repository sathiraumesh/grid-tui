"""One cluster in detail: what its nodes are made of. esc goes back to the
clusters.

    ╭─ site: nancy · cluster: gros ──────────────────────────────────────╮
    │                                                                     │
    │  MODEL      Dell PowerEdge R640                                     │
    │  QUEUES     default, admin                                          │
    │  NODES      124                                                     │
    │  CPU        1 × Intel Xeon Gold 5220 · 18 cores · 36 threads · 2.2 GHz
    │  MEMORY     96 GiB                                                  │
    │  STORAGE    480 GB SSD SATA · 960 GB SSD SATA                       │
    │  NETWORK    25 Gbps Ethernet                                        │
    │  GPU        -                                                       │
    │  WATTMETER  yes                                                     │
    │  METRICS    wattmetre_power_watt, bmc_node_power_watt               │
    ╰─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters/gros/nodes ╯

The hardware loads in the background; its lines say "loading" until then.
"""

from __future__ import annotations

from collections import Counter

from rich.markup import escape
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware, Site
from grid_tui.screens.base import Api


class ClusterDetailScreen(Screen):
    """The detail of one cluster of a site."""

    BINDINGS = [
        Binding("escape,backspace", "app.pop_screen", "Clusters"),
        Binding("r", "reload", "Reload"),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    ClusterDetailScreen #detail {
        height: 1fr;
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
        padding: 1 2;
    }
    ClusterDetailScreen #status { height: 1; padding: 0 1; color: $text-muted; }
    ClusterDetailScreen #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, site: Site, cluster: Cluster) -> None:
        super().__init__()
        self.api, self.site, self.cluster = api, site, cluster
        self.hardware: Hardware | None = None  # None while loading

    def compose(self) -> ComposeResult:
        yield Header()
        detail = Static(self.text(), id="detail")
        detail.border_title = f"site: {self.site.uid} · cluster: {self.cluster.uid}"
        detail.border_subtitle = "$ " + self.api.command(
            f"/sites/{self.site.uid}/clusters/{self.cluster.uid}/nodes"
        )
        yield detail
        yield Static("", id="status", markup=False)  # an error's [ ] aren't styling
        yield Footer()

    def on_mount(self) -> None:
        self.load()

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)  # a reload replaces a load still on its way
    async def load(self) -> None:
        """Load the hardware in the background, then show it."""
        self.set_status("loading…")
        try:
            hardware = await self.api.hardware(self.site.uid, self.cluster.uid)
        except Exception as e:  # the API's error, or no network
            self.set_status(f"error: {e}", error=True)
            return
        self.hardware = hardware
        self.query_one("#detail", Static).update(self.text())
        self.set_status("")

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
