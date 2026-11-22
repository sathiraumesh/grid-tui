"""Cluster: what a cluster knows about itself."""

from grid_tui.models import Cluster


def test_wattmeter() -> None:
    assert Cluster("gros", metrics=("bmc_node_power_watt", "wattmetre_power_watt")).wattmeter
    assert not Cluster("grat", metrics=("bmc_node_power_watt",)).wattmeter
    assert not Cluster("bare").wattmeter
