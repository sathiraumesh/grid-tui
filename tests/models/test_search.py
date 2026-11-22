"""The search's requirements: which clusters meet them."""

from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware
from grid_tui.models.search import (
    Requirements,
    SearchEntry,
    cpu_choices,
    gpu_choices,
    results,
    site_choices,
)

A100 = GPU("Nvidia", "A100", 40 * 2**30)

# lyon/gemini: GPUs and a wattmeter; nancy/gros: Intel; nancy/grat: AMD with
# NVMe and 100 Gbps; nancy/grvingt: hardware still unknown.
ENTRIES = [
    SearchEntry("nancy", Cluster("gros"), Hardware(
        nodes=124, cpu="Intel Xeon Gold 5220", cores=18, memory=96 * 2**30,
        disks=(Disk("SSD", "SATA"),), nics=(NIC("Ethernet", 25 * 10**9),))),
    SearchEntry("nancy", Cluster("grat"), Hardware(
        nodes=8, cpu="AMD EPYC 7513", cores=64, memory=512 * 2**30,
        disks=(Disk("SSD", "NVME"),), nics=(NIC("Ethernet", 100 * 10**9),))),
    SearchEntry("nancy", Cluster("grvingt")),
    SearchEntry("lyon", Cluster("gemini", metrics=("wattmetre_power_watt",)), Hardware(
        nodes=2, cpu="Intel Xeon E5-2698", cores=40, memory=512 * 2**30,
        gpus=(A100, A100), disks=(Disk("HDD", "SAS"),))),
]


def found(req: Requirements) -> list[str]:
    return [f"{e.site}/{e.cluster.uid}" for e in results(ENTRIES, req)]


def test_nothing_asked_finds_everything() -> None:
    assert found(Requirements()) == ["lyon/gemini", "nancy/grat", "nancy/gros", "nancy/grvingt"]


def test_each_requirement() -> None:
    cases = {
        Requirements(site="lyon"): ["lyon/gemini"],
        Requirements(wattmeter=True): ["lyon/gemini"],
        Requirements(has_gpu=True): ["lyon/gemini"],
        Requirements(cpu="Intel"): ["lyon/gemini", "nancy/gros"],
        Requirements(gpu="Nvidia A100"): ["lyon/gemini"],
        Requirements(disk="NVME"): ["nancy/grat"],
        Requirements(disk="SSD"): ["nancy/grat", "nancy/gros"],
        Requirements(min_nodes=10): ["nancy/gros"],
        Requirements(min_cores=40): ["lyon/gemini", "nancy/grat"],
        Requirements(min_memory_gib=500): ["lyon/gemini", "nancy/grat"],
        Requirements(min_gpu_memory_gib=40): ["lyon/gemini"],
        Requirements(min_network_gbps=50): ["nancy/grat"],
        Requirements(cpu="Intel", min_cores=20): ["lyon/gemini"],  # all of them together
    }
    for req, want in cases.items():
        assert found(req) == want, req


def test_unknown_hardware_meets_only_what_isnt_hardware() -> None:
    assert "nancy/grvingt" in found(Requirements(site="nancy"))
    assert "nancy/grvingt" not in found(Requirements(min_nodes=1))


def test_choices_come_from_the_data() -> None:
    assert site_choices(ENTRIES) == ["lyon", "nancy"]
    assert cpu_choices(ENTRIES) == ["AMD", "Intel"]
    assert gpu_choices(ENTRIES) == ["Nvidia A100"]
