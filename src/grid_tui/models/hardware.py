"""What one node of a cluster is made of."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Disk:
    kind: str = ""        # "SSD", "HDD"
    interface: str = ""   # "SATA", "NVME"
    size: int = 0         # bytes


@dataclass(frozen=True)
class NIC:
    interface: str = ""   # "Ethernet", "InfiniBand"
    rate: int = 0         # bits per second


@dataclass(frozen=True)
class GPU:
    vendor: str = ""
    model: str = ""
    memory: int = 0       # bytes


@dataclass(frozen=True)
class Hardware:
    """One node's hardware. A cluster's nodes are normally all the same."""

    nodes: int = 0             # how many nodes the cluster has
    cpu: str = ""              # "Intel Xeon Gold 5220"
    sockets: int = 0
    cores: int = 0             # per node
    threads: int = 0
    clock_ghz: float = 0.0
    memory: int = 0            # bytes
    disks: tuple[Disk, ...] = ()
    nics: tuple[NIC, ...] = ()
    gpus: tuple[GPU, ...] = ()