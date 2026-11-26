"""Finding the clusters whose nodes meet some hardware needs.

Pure functions, no API calls: give them the nodes, and they say which clusters
have nodes that meet every need.
"""

from dataclasses import dataclass

from grid_tui.models import Cluster, Node

ANY_GPU = 'any'  # Requirements.gpu for "any GPU will do"
DISK_TYPES = ('SSD', 'HDD', 'NVMe')  # what Requirements.disk can ask for


@dataclass(frozen=True)
class Requirements:
    """What a node must have. Every need left at its default is no need."""

    min_cores: int = 0  # at least this many cores
    min_ram_gib: float = 0  # at least this much RAM, in GiB
    gpu: str | None = None  # ANY_GPU, or a model like 'Tesla V100'; None: no need
    disk: str | None = None  # a disk of this type: 'SSD', 'HDD' or 'NVMe'; None: any
    wattmeter: bool = False  # a power meter measures it
    site: str | None = None  # only on this site; None for every site


@dataclass(frozen=True)
class Match:
    """A cluster with nodes that meet the needs."""

    site: str  # e.g. 'nancy'
    cluster: Cluster
    nodes: tuple[Node, ...]  # the nodes that meet them
    total: int  # how many nodes the cluster has


def has_wattmeter(node: Node, cluster: Cluster | None = None) -> bool:
    """Is node measured by a wattmeter?

    Yes if its own monitoring says so, or if its cluster has a wattmeter metric
    (a name with 'wattmetre' in it) that is recorded for it.
    """
    if node.monitoring.has_wattmeter:
        return True
    if cluster is None:
        return False
    return any('wattmetre' in metric.name for metric in cluster.metrics_for(node.uid))


def has_gpu(node: Node, model: str) -> bool:
    """Has node a GPU of this model (or any GPU, with ANY_GPU)?"""
    if model == ANY_GPU:
        return bool(node.gpu_devices)
    return any(gpu.model == model for gpu in node.gpu_devices)


def has_disk(node: Node, kind: str) -> bool:
    """Has node a disk of this kind? 'NVMe' is its interface; SSD or HDD its storage.

    The case doesn't matter: 'ssd' finds an 'SSD'.
    """
    kind = kind.lower()
    for disk in node.storage_devices:
        if kind == 'nvme' and disk.interface.lower() == 'nvme':
            return True
        if disk.storage.lower() == kind:
            return True
    return False


def gpu_models(found: dict[tuple[str, str], tuple[Cluster, list[Node]]]) -> list[str]:
    """Every GPU model among the nodes, sorted, each once: for the GPU list."""
    return sorted(
        {
            gpu.model
            for _, nodes in found.values()
            for node in nodes
            for gpu in node.gpu_devices
            if gpu.model
        }
    )


def meets(node: Node, needs: Requirements, cluster: Cluster | None = None) -> bool:
    """Does node meet every need?

    Args:
        node: The node to check.
        needs: What it must have.
        cluster: Its cluster, for the wattmeter check.
    """
    if node.architecture.nb_cores < needs.min_cores:
        return False
    if node.ram_gib < needs.min_ram_gib:
        return False
    if needs.gpu and not has_gpu(node, needs.gpu):
        return False
    if needs.disk and not has_disk(node, needs.disk):
        return False
    if needs.wattmeter and not has_wattmeter(node, cluster):
        return False
    return True


def search(
    found: dict[tuple[str, str], tuple[Cluster, list[Node]]], needs: Requirements
) -> list[Match]:
    """The clusters with at least one node that meets every need.

    Args:
        found: Each cluster and its nodes, by (site, cluster uid).
        needs: What a node must have.

    Returns:
        A Match for each such cluster, by site and then cluster name.
    """
    matches = []
    for (site, _), (cluster, nodes) in sorted(found.items()):
        if needs.site and site != needs.site:
            continue
        good = tuple(node for node in nodes if meets(node, needs, cluster))
        if good:
            matches.append(Match(site, cluster, good, len(nodes)))
    return matches
