"""One cluster in detail: its hardware, loading, errors, and esc."""

from __future__ import annotations

import asyncio

from grid_tui.app import GridTUI
from grid_tui.models import GPU, NIC, Disk, Hardware
from grid_tui.screens import ClusterDetailScreen, ClustersScreen, SitesScreen
from grid_tui.screens.cluster import cpu, disk, gb, gib, gpus, joined, nic
from tests.fakes import TWO_SITES, FakeClient, detail, open_gros, status


async def test_enter_on_a_cluster_shows_its_detail() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(120, 30)) as pilot:
        await open_gros(pilot)
        screen = app.screen
        assert isinstance(screen, ClusterDetailScreen) and screen.cluster.uid == "gros"
        text = detail(app)
        for line in [
            "MODEL      Dell PowerEdge R640",
            "QUEUES     default, admin",
            "NODES      124",
            "CPU        1 × Intel Xeon Gold 5220 · 18 cores · 36 threads · 2.2 GHz",
            "MEMORY     96 GiB",
            "STORAGE    480 GB SSD SATA · 960 GB SSD SATA",
            "NETWORK    25 Gbps Ethernet",
            "GPU        -",
            "WATTMETER  yes",
            "METRICS    wattmetre_power_watt",
        ]:
            assert line in text, f"{line!r} not in\n{text}"
        widget = screen.query_one("#detail")
        assert widget.border_title == "site: nancy · cluster: gros"
        assert widget.border_subtitle == "$ curl https://api.test/sites/nancy/clusters/gros/nodes"

async def test_the_same_gpus_are_counted_together() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # graffiti: the GPU node here
        await pilot.pause()
        text = detail(app)
        assert "GPU        4 × Nvidia A100 40 GiB" in text
        assert "CPU        2 × AMD EPYC 7452 · 64 cores" in text
        assert "MEMORY     512 GiB" in text

async def test_detail_says_loading_until_the_hardware_arrives() -> None:
    client = FakeClient(TWO_SITES)
    client.hardware_gate = asyncio.Event()
    app = GridTUI(client)
    async with app.run_test(size=(120, 30)) as pilot:
        await open_gros(pilot)
        assert "CPU        loading" in detail(app)
        assert "MODEL      Dell PowerEdge R640" in detail(app)  # known from the list already
        assert status(app) == "loading…"
        client.hardware_gate.set()
        await pilot.pause()
        assert "Intel Xeon Gold 5220" in detail(app)
        assert status(app) == ""

async def test_detail_error_and_reload() -> None:
    client = FakeClient(TWO_SITES)
    client.hardware_error = RuntimeError("GET /sites/nancy/clusters/gros/nodes: 500 [oops]")
    app = GridTUI(client)
    async with app.run_test(size=(120, 30)) as pilot:
        await open_gros(pilot)
        assert status(app) == "error: GET /sites/nancy/clusters/gros/nodes: 500 [oops]"  # [ ] shown as is
        client.hardware_error = None
        await pilot.press("r")
        await pilot.pause()
        assert "Intel Xeon Gold 5220" in detail(app)
        assert status(app) == ""

async def test_esc_from_the_detail_goes_back_to_the_same_cluster() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(120, 30)) as pilot:
        await open_gros(pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ClustersScreen)
        assert app.screen.selected.uid == "gros"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SitesScreen)


# How the hardware reads.


def test_sizes() -> None:
    assert gib(96 * 2**30) == "96 GiB"
    assert gib(1536 * 2**30) == "1.5 TiB"
    assert gb(480_103_981_056) == "480.1 GB"
    assert gb(2 * 10**12) == "2 TB"
    assert gib(0) == "" and gb(0) == ""


def test_hardware_text() -> None:
    a100 = GPU("Nvidia", "A100", 40 * 2**30)
    assert gpus((a100,) * 4) == "4 × Nvidia A100 40 GiB"
    assert gpus((a100, GPU("AMD", "MI50"))) == "Nvidia A100 40 GiB · AMD MI50"
    assert gpus(()) == "-"
    assert cpu(Hardware(cpu="AMD EPYC 7452", sockets=2, cores=64)) == "2 × AMD EPYC 7452 · 64 cores"
    assert cpu(Hardware()) == "-"
    assert disk(Disk("HDD", "", 2 * 10**12)) == "2 TB HDD"
    assert nic(NIC("InfiniBand", 100 * 10**9)) == "100 Gbps InfiniBand"
    assert joined(["", "a", "", "b"]) == "a · b" and joined([]) == "-"
