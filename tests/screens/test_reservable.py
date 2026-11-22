"""Reservable: which clusters can take a reservation for a date, a time and a duration."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from textual.widgets import Checkbox, DataTable, Input, Select, Static

from grid_tui.app import GridTUI
from grid_tui.screens import ReservableScreen
from grid_tui.screens.reserve import ReserveDialog
from tests.fakes import TWO_SITES, FakeClient

SIZE = (140, 40)

# The fake API's nodes, for the default window (the next half hour, for 1h):
# nancy/graffiti 2 free of 2; nancy/gros 1 free of 2 (gros-2 runs a job,
# gros-10 is dead); rennes/paravance 1 free of 1.


async def open_reservable(pilot) -> ReservableScreen:
    await pilot.pause()
    await pilot.press("a")
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, ReservableScreen)
    return screen


def rows(screen: ReservableScreen) -> list[list[str]]:
    table = screen.query_one("#results", DataTable)
    return [[str(c) for c in table.get_row_at(i)] for i in range(table.row_count)]


async def set_value(pilot, widget, value) -> None:
    widget.value = value
    await pilot.pause()


async def test_a_opens_it_and_shows_the_reservable_clusters() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        assert rows(screen) == [
            ["nancy", "graffiti", "2 of 2", "yes"],
            ["nancy", "gros", "1 of 2", "yes"],
            ["rennes", "paravance", "1 of 1", "yes"],
        ]
        assert screen.query_one("#results", DataTable).border_title.startswith("reservable: 3 of 3 · ")


async def test_more_nodes_and_showing_the_rest() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        assert [r[1] for r in rows(screen)] == ["graffiti"]
        await set_value(pilot, screen.query_one("#only", Checkbox), False)
        assert rows(screen) == [
            ["nancy", "graffiti", "2 of 2", "yes"],
            ["nancy", "gros", "1 of 2", "no: only 1 free"],
            ["rennes", "paravance", "1 of 1", "no: it has 1 usable node(s)"],
        ]


async def test_a_site_and_a_later_window() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#site", Select), "rennes")
        assert [r[1] for r in rows(screen)] == ["paravance"]
        screen.query_one("#site", Select).clear()
        # tomorrow: gros' jobs are over, both its alive nodes are free
        tomorrow = datetime.now().astimezone().date() + timedelta(days=1)
        await set_value(pilot, screen.query_one("#date", Select), tomorrow)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        assert [r[1] for r in rows(screen)] == ["graffiti", "gros"]


async def test_a_passed_time_is_said() -> None:
    if datetime.now().hour < 1:
        pytest.skip("00:00 hasn't passed by half an hour yet")
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#time", Select), time(0, 0))
        assert "that time has passed" in str(screen.query_one("#status", Static).render())
        await set_value(pilot, screen.query_one("#time", Select), time(23, 30))
        assert "passed" not in str(screen.query_one("#status", Static).render())


async def test_enter_reserves_with_the_window_filled_in() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        await set_value(pilot, screen.query_one("#duration", Select), timedelta(hours=2))
        start, end, _ = screen.window()
        screen.query_one("#results", DataTable).focus()
        await pilot.press("enter")  # graffiti
        await pilot.pause()
        dialog = app.screen
        assert isinstance(dialog, ReserveDialog)
        r = dialog.request()
        assert (r.site, r.cluster, r.nodes, r.start, r.walltime) == ("nancy", "graffiti", 2, start, end - start)

        await pilot.click("#reserve")
        await pilot.pause()
        await pilot.click("#send")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.screen is screen
        [sent] = client.submitted
        assert (sent.cluster, sent.nodes, sent.walltime) == ("graffiti", 2, timedelta(hours=2))


async def test_enter_on_a_cluster_that_cant_take_it_says_why() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        await set_value(pilot, screen.query_one("#only", Checkbox), False)
        table = screen.query_one("#results", DataTable)
        table.focus()
        await pilot.press("down", "enter")  # gros: only 1 free
        await pilot.pause()
        assert app.screen is screen and client.submitted == []
