"""The search: every site loads, the form filters, a result opens."""

from __future__ import annotations

from textual.widgets import Checkbox, DataTable, Input, Select

from grid_tui.app import GridTUI
from grid_tui.screens import ClusterDetailScreen, SearchScreen, SitesScreen
from tests.fakes import TWO_SITES, FakeClient, status

# The fake API's clusters: nancy/graffiti (4 GPUs, 64 cores), nancy/gros
# (Intel, 18 cores, a wattmeter), rennes/paravance (no hardware known).


async def open_search(pilot) -> SearchScreen:
    """Press / and wait until every site has loaded."""
    await pilot.pause()
    await pilot.press("slash")
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()  # the loads run in the background
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, SearchScreen)
    return screen


def found(screen: SearchScreen) -> list[str]:
    table = screen.query_one("#results", DataTable)
    return [f"{table.get_row_at(i)[0]}/{table.get_row_at(i)[1]}" for i in range(table.row_count)]


async def test_slash_opens_the_search_and_loads_every_site() -> None:
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


async def test_enter_on_a_result_opens_its_detail_and_esc_comes_back() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=(160, 45)) as pilot:
        screen = await open_search(pilot)
        screen.query_one("#min_cores", Input).value = "10"
        await pilot.pause()
        table = screen.query_one("#results", DataTable)
        table.focus()
        await pilot.press("down", "enter")  # gros
        await pilot.pause()
        detail = app.screen
        assert isinstance(detail, ClusterDetailScreen)
        assert (detail.site.uid, detail.cluster.uid) == ("nancy", "gros")

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen
        assert screen.query_one("#min_cores", Input).value == "10"  # what was set is kept

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, SitesScreen)

        calls = client.calls
        await pilot.press("slash")  # again: the same screen, nothing loaded again
        await pilot.pause()
        assert app.screen is screen and client.calls == calls


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
