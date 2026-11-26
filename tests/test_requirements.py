"""Tests for requirements: which nodes and clusters meet some hardware needs."""

from grid_tui.models import Cluster, Node
from grid_tui.requirements import (
    ANY_GPU,
    Match,
    Requirements,
    gpu_models,
    has_disk,
    has_gpu,
    has_wattmeter,
    meets,
    search,
)

GIB = 1024**3

SMALL = Node.model_validate(
    {
        'uid': 'small-1',
        'architecture': {'nb_cores': 8},
        'main_memory': {'ram_size': 32 * GIB},
    }
)
BIG_GPU = Node.model_validate(
    {
        'uid': 'big-1',
        'architecture': {'nb_cores': 64},
        'main_memory': {'ram_size': 512 * GIB},
        'gpu_devices': [{'model': 'A100'}],
        'storage_devices': [{'storage': 'SSD', 'interface': 'NVMe', 'size': GIB}],
        'monitoring': {'wattmeter': True},
    }
)
HDD_ONLY = Node.model_validate(
    {'uid': 'hdd-1', 'storage_devices': [{'storage': 'HDD', 'size': GIB}]}
)


def test_no_needs_meets_every_node() -> None:
    """With nothing asked for, every node meets it."""
    assert all(meets(node, Requirements()) for node in (SMALL, BIG_GPU, HDD_ONLY))


def test_min_cores() -> None:
    """A node needs at least min_cores cores."""
    needs = Requirements(min_cores=16)
    assert not meets(SMALL, needs)
    assert meets(BIG_GPU, needs)
    assert meets(SMALL, Requirements(min_cores=8))  # exactly enough is enough


def test_min_ram() -> None:
    """A node needs at least min_ram_gib GiB of RAM."""
    assert not meets(SMALL, Requirements(min_ram_gib=64))
    assert meets(BIG_GPU, Requirements(min_ram_gib=64))


def test_any_gpu() -> None:
    """With ANY_GPU, a node needs at least one GPU, of any model."""
    assert not meets(SMALL, Requirements(gpu=ANY_GPU))
    assert meets(BIG_GPU, Requirements(gpu=ANY_GPU))


def test_a_gpu_model() -> None:
    """With a model, a node needs a GPU of that model."""
    assert meets(BIG_GPU, Requirements(gpu='A100'))
    assert not meets(BIG_GPU, Requirements(gpu='Tesla V100'))
    assert not has_gpu(SMALL, 'A100')


def test_disk_types() -> None:
    """With a disk type, a node needs a disk of that type."""
    assert meets(BIG_GPU, Requirements(disk='SSD'))
    assert not meets(HDD_ONLY, Requirements(disk='SSD'))
    assert meets(HDD_ONLY, Requirements(disk='HDD'))
    assert not meets(BIG_GPU, Requirements(disk='HDD'))


def test_nvme_is_the_disks_interface() -> None:
    """NVMe is found by a disk's interface, not its storage."""
    assert meets(BIG_GPU, Requirements(disk='NVMe'))
    assert not meets(HDD_ONLY, Requirements(disk='NVMe'))


def test_disk_type_case_does_not_matter() -> None:
    """'ssd' finds an 'SSD', 'nvme' an 'NVMe'."""
    assert has_disk(BIG_GPU, 'ssd')
    assert has_disk(BIG_GPU, 'nvme')


def test_every_need_at_once() -> None:
    """A node must meet every need, not just one."""
    needs = Requirements(min_cores=16, gpu=ANY_GPU, disk='SSD')
    assert meets(BIG_GPU, needs)
    assert not meets(SMALL, needs)


# The wattmeter


def test_wattmeter_from_the_nodes_monitoring() -> None:
    """A node whose monitoring says wattmeter has one."""
    assert has_wattmeter(BIG_GPU)
    assert not has_wattmeter(SMALL)


def test_wattmeter_from_the_clusters_metrics() -> None:
    """A wattmetre metric recorded for the node counts as a wattmeter."""
    cluster = Cluster.model_validate(
        {
            'uid': 'c',
            'metrics': [{'name': 'wattmetre_power_watt', 'only_for': ['small-1']}],
        }
    )
    assert has_wattmeter(SMALL, cluster)
    assert not has_wattmeter(HDD_ONLY, cluster)  # not in only_for


def test_other_power_metrics_are_not_a_wattmeter() -> None:
    """A BMC power metric isn't a wattmeter."""
    cluster = Cluster.model_validate(
        {'uid': 'c', 'metrics': [{'name': 'bmc_node_power_watt'}]}
    )
    assert not has_wattmeter(SMALL, cluster)


def test_wattmeter_need() -> None:
    """With wattmeter, a node needs a wattmeter, from either place."""
    needs = Requirements(wattmeter=True)
    assert meets(BIG_GPU, needs)
    assert not meets(SMALL, needs)


# Searching clusters


FOUND = {
    ('nancy', 'a'): (Cluster(uid='a'), [SMALL, BIG_GPU]),
    ('lyon', 'b'): (Cluster(uid='b'), [SMALL]),
    ('lille', 'c'): (Cluster(uid='c'), []),
}


def test_search_lists_clusters_with_a_good_node_by_site() -> None:
    """Each cluster with a good node is a match, in site then cluster order."""
    matches = search(FOUND, Requirements())
    assert [(m.site, m.cluster.uid) for m in matches] == [('lyon', 'b'), ('nancy', 'a')]


def test_search_keeps_only_the_good_nodes_and_the_total() -> None:
    """A match has the nodes that meet the needs, and how many the cluster has."""
    [match] = search(FOUND, Requirements(gpu=ANY_GPU))
    assert match == Match('nancy', Cluster(uid='a'), (BIG_GPU,), 2)


def test_search_by_site() -> None:
    """With a site, only that site's clusters are searched."""
    matches = search(FOUND, Requirements(site='lyon'))
    assert [m.cluster.uid for m in matches] == ['b']


def test_search_with_no_match() -> None:
    """When no node meets the needs, there are no matches."""
    assert search(FOUND, Requirements(min_cores=1000)) == []


def test_gpu_models_lists_each_model_once_sorted() -> None:
    """gpu_models gives every model in the nodes, once each, sorted."""
    v100 = Node.model_validate({'uid': 'v', 'gpu_devices': [{'model': 'V100'}] * 2})
    found = {
        ('a', 'x'): (Cluster(uid='x'), [BIG_GPU, v100]),
        ('b', 'y'): (Cluster(uid='y'), [v100, SMALL]),
    }
    assert gpu_models(found) == ['A100', 'V100']
    assert gpu_models({}) == []
