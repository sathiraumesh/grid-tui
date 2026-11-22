"""Searching every site for the clusters that meet some requirements.

A SearchEntry is one cluster of one site, with its hardware once loaded.
Requirements are what the search form asks for; matches() says whether a
cluster meets all of them. A requirement on the hardware isn't met while a
cluster's hardware is unknown (loading, or its call failed).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from grid_tui.models.cluster import Cluster
from grid_tui.models.hardware import GPU, Hardware

# The disk choices: a disk is a match if its kind or its interface is one.
DISK_KINDS = ("SSD", "HDD", "NVME")


@dataclass(frozen=True)
class SearchEntry:
    """One cluster of one site, as the search sees it."""

    site: str
    cluster: Cluster
    hardware: Hardware | None = None  # None: loading, or failed
    failed: bool = False  # the hardware's call failed


@dataclass(frozen=True)
class Requirements:
    """What the search form asks for. Empty (None, 0, False): no requirement."""

    has_gpu: bool = False
    wattmeter: bool = False
    site: str | None = None
    cpu: str | None = None  # a CPU maker: the first word of its name, "Intel", "AMD"…
    gpu: str | None = None  # a GPU model, "Nvidia A100"
    disk: str | None = None  # one of DISK_KINDS
    min_nodes: int = 0
    min_cores: int = 0  # per node
    min_memory_gib: int = 0  # per node
    min_gpu_memory_gib: int = 0  # the biggest GPU's
    min_network_gbps: int = 0  # the fastest card's

    def needs_hardware(self) -> bool:
        """Whether any requirement is on the hardware (all but site and wattmeter)."""
        return bool(
            self.has_gpu or self.cpu or self.gpu or self.disk or self.min_nodes or self.min_cores
            or self.min_memory_gib or self.min_gpu_memory_gib or self.min_network_gbps
        )

    def matches(self, e: SearchEntry) -> bool:
        """Whether e meets every requirement."""
        if self.site and e.site != self.site:
            return False
        if self.wattmeter and not e.cluster.wattmeter:
            return False
        if not self.needs_hardware():
            return True
        hw = e.hardware
        if hw is None:
            return False  # unknown: can't say it meets them
        if self.has_gpu and not hw.gpus:
            return False
        if self.cpu and cpu_vendor(hw.cpu) != self.cpu:
            return False
        if self.gpu and not any(gpu_name(g) == self.gpu for g in hw.gpus):
            return False
        if self.disk and not any(self.disk in (d.kind.upper(), d.interface.upper()) for d in hw.disks):
            return False
        return (
            hw.nodes >= self.min_nodes
            and hw.cores >= self.min_cores
            and hw.memory >= self.min_memory_gib * 2**30
            and max((g.memory for g in hw.gpus), default=0) >= self.min_gpu_memory_gib * 2**30
            and max((n.rate for n in hw.nics), default=0) >= self.min_network_gbps * 10**9
        )


def results(entries: Iterable[SearchEntry], req: Requirements) -> list[SearchEntry]:
    """The entries that meet req, by site then cluster."""
    return sorted((e for e in entries if req.matches(e)), key=lambda e: (e.site, e.cluster.uid))


def cpu_vendor(cpu: str) -> str:
    """The first word of a CPU's name: "Intel", "AMD", "Neoverse-V2"."""
    return cpu.split(" ", 1)[0] if cpu else ""


def gpu_name(g: GPU) -> str:
    """e.g. "Nvidia A100"."""
    return " ".join(p for p in (g.vendor, g.model) if p)


# The choices of the form, from what has been loaded: what was found, sorted.


def site_choices(entries: Iterable[SearchEntry]) -> list[str]:
    return sorted({e.site for e in entries})


def cpu_choices(entries: Iterable[SearchEntry]) -> list[str]:
    return sorted({cpu_vendor(e.hardware.cpu) for e in entries if e.hardware and e.hardware.cpu})


def gpu_choices(entries: Iterable[SearchEntry]) -> list[str]:
    return sorted({gpu_name(g) for e in entries if e.hardware for g in e.hardware.gpus if gpu_name(g)})
