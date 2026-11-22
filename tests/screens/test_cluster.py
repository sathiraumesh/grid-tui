"""One cluster in detail: its hardware, loading, errors, and esc."""

from __future__ import annotations

import asyncio

from grid_tui.app import GridTUI
from datetime import datetime, timedelta

from textual.widgets import DataTable

from grid_tui.models import GPU, NIC, Disk, Hardware, Reservation
from grid_tui.screens import ClusterDetailScreen, ClustersScreen, SitesScreen
from grid_tui.screens.cluster import cpu, disk, gb, gib, gpus, job_text, joined, nic
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



# The nodes: the machines of the cluster.


def node_rows(app: GridTUI) -> list[list[str]]:
    table = app.screen.query_one("#nodes", DataTable)
    return [[str(c) for c in table.get_row_at(i)] for i in range(table.row_count)]


async def test_detail_shows_the_nodes() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(140, 40)) as pilot:
        await open_gros(pilot)
        rows = node_rows(app)
        assert [r[:3] for r in rows] == [
            ["gros-1", "alive/free", "free"],
            ["gros-2", "alive/busy", "busy"],
            ["gros-10", "dead/unknown", "down"],
        ]
        assert rows[0][3].startswith("next #4600 eve ") and rows[0][3].endswith("(1h)")
        assert rows[1][3].startswith("#4521 bob ") and rows[1][3].endswith("(3h) Running")
        assert rows[2][3] == ""
        table = app.screen.query_one("#nodes", DataTable)
        assert table.border_title == "nodes: 3 · free 1 · busy 1 · down 1"
        assert table.border_subtitle == "$ curl https://api.test/sites/nancy/clusters/gros/status"


async def test_the_nodes_table_takes_the_keys() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(140, 40)) as pilot:
        await open_gros(pilot)
        await pilot.press("down", "down")
        assert app.screen.query_one("#nodes", DataTable).cursor_row == 2
        assert app.screen.nodes[2].name == "gros-10"


async def test_one_part_failing_keeps_the_other() -> None:
    client = FakeClient(TWO_SITES)
    client.nodes_error = RuntimeError("GET /sites/nancy/clusters/gros/status: 500")
    app = GridTUI(client)
    async with app.run_test(size=(140, 40)) as pilot:
        await open_gros(pilot)
        assert "Intel Xeon Gold 5220" in detail(app)  # the hardware still shows
        assert node_rows(app) == []
        assert status(app) == "error: GET /sites/nancy/clusters/gros/status: 500"
        client.nodes_error = None
        await pilot.press("r")
        await pilot.pause()
        assert len(node_rows(app)) == 3
        assert status(app) == ""


def test_job_text() -> None:
    now = datetime(2026, 11, 22, 14, 30).astimezone()
    h = timedelta(hours=1)
    assert job_text(Reservation(1, now - h, now + h, "a", "default", "Running"), now) == "#1 a 13:30→15:30 (2h) Running"
    assert job_text(Reservation(2, now + h, now + 2.5 * h, "b"), now) == "next #2 b 15:30→17:00 (1h30m)"
    assert job_text(Reservation(3, now + 20 * h, now + 21 * h, "c"), now) == "next #3 c Mon 23 10:30→Mon 23 11:30 (1h)"
    assert job_text(Reservation(4, now - h, now + 0.75 * h, "d", "besteffort", "Running"), now) == (
        "#4 d 13:30→15:15 (1h45m) besteffort Running"
    )
    assert job_text(None, now) == ""
