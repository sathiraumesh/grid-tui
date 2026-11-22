"""Search: every site loads the first time the tab opens, the form filters,
a result opens in Nodes."""

from __future__ import annotations

from textual.widgets import Checkbox, DataTable, Input, Select

from grid_tui.app import GridTUI
from grid_tui.panels import SearchPanel
from tests.fakes import TWO_SITES, FakeClient, settle, status

# The fake API's clusters: nancy/graffiti (4 GPUs, 64 cores), nancy/gros
# (Intel, 18 cores, a wattmeter), rennes/paravance (no hardware known).


async def open_search(pilot) -> SearchPanel:
    """Tab 7, every site loaded."""
    await settle(pilot)
    await pilot.press("7")
    await settle(pilot)
    assert pilot.app.screen.active == "search"
    return pilot.app.screen.search


def found(screen: SearchPanel) -> list[str]:
    table = screen.query_one("#results", DataTable)
    return [f"{table.get_row_at(i)[0]}/{table.get_row_at(i)[1]}" for i in range(table.row_count)]


async def test_the_search_tab_loads_every_site_the_first_time() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)
        assert found(screen) == ["nancy/graffiti", "nancy/gros", "rennes/paravance"]
        table = screen.query_one("#results", DataTable)
        assert table.border_title == "matches: 3 of 3"
        gros = [str(c) for c in table.get_row_at(1)]
        assert gros == ["nancy", "gros", "124", "1 × Intel Xeon Gold 5220", "18", "96 GiB", "-", "25 Gbps Ethernet", "yes"]
        assert status(app) == ""


async def test_the_form_filters_the_results() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)

        screen.query_one("#has_gpu", Checkbox).value = True
        await pilot.pause()
        assert found(screen) == ["nancy/graffiti"]
        screen.query_one("#has_gpu", Checkbox).value = False

        screen.query_one("#wattmeter", Checkbox).value = True
        await pilot.pause()
        assert found(screen) == ["nancy/gros"]
        screen.query_one("#wattmeter", Checkbox).value = False

        screen.query_one("#site", Select).value = "rennes"
        await pilot.pause()
        assert found(screen) == ["rennes/paravance"]
        screen.query_one("#site", Select).clear()

        screen.query_one("#min_cores", Input).value = "20"
        await pilot.pause()
        assert found(screen) == ["nancy/graffiti"]

        screen.query_one("#min_cores", Input).value = ""
        await pilot.pause()
        assert len(found(screen)) == 3


async def test_the_choices_are_what_was_found() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)
        assert screen.choices == {"site": ["nancy", "rennes"], "cpu": ["AMD", "Intel"], "gpu": ["Nvidia A100"]}
        screen.query_one("#cpu", Select).value = "AMD"
        await pilot.pause()
        assert found(screen) == ["nancy/graffiti"]


async def test_enter_on_a_result_opens_it_in_nodes_and_7_comes_back() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)
        screen.query_one("#min_cores", Input).value = "10"
        await pilot.pause()
        table = screen.query_one("#results", DataTable)
        table.focus()
        await pilot.press("down", "enter")  # gros
        await settle(pilot)
        nodes = app.screen.nodes
        assert app.screen.active == "nodes" and (nodes.site.uid, nodes.cluster.uid) == ("nancy", "gros")

        calls = client.calls
        app.screen.set_focus(nodes.query_one("#nodes", DataTable))
        await pilot.press("7")  # back: the same requirements, nothing loaded again
        await settle(pilot)
        assert app.screen.active == "search"
        assert screen.query_one("#min_cores", Input).value == "10" and client.calls == calls


async def test_a_failed_hardware_shows_and_is_left_out_of_hardware_filters() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    client.hardware_error = RuntimeError("500")
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)
        table = screen.query_one("#results", DataTable)
        assert [str(c) for c in table.get_row_at(0)][2:4] == ["?", "?"]
        screen.query_one("#min_nodes", Input).value = "1"
        await pilot.pause()
        assert found(screen) == []


async def test_a_failed_site_is_said() -> None:
    client = FakeClient(TWO_SITES)
    client.clusters_error = RuntimeError("GET /sites/x/clusters: 500")
    app = GridTUI(client)
    async with app.run_test(size=(160, 45)) as pilot:
        await open_search(pilot)
        assert status(app).startswith("2 site(s) failed: ")
