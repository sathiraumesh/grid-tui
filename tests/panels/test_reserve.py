"""Reservations › Reserve: which clusters can take a reservation for a date,
a time and a duration, and reserving on one, in the same panel."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from textual.widgets import Checkbox, DataTable, Input, Select, Static

from grid_tui.app import GridTUI
from grid_tui.panels import ReservePanel
from tests.fakes import TWO_SITES, FakeClient, settle

SIZE = (140, 40)

# The fake API's nodes, for the default window (the next half hour, for 1h):
# nancy/graffiti 2 free of 2; nancy/gros 1 free of 2 (gros-2 runs a job,
# gros-10 is dead); rennes/paravance 1 free of 1.


async def open_reservable(pilot) -> ReservePanel:
    """Tab 5, every site loaded."""
    await settle(pilot)
    await pilot.press("5")
    await settle(pilot)
    assert pilot.app.screen.active == "reserving"
    return pilot.app.screen.reserve


def rows(screen: ReservePanel) -> list[list[str]]:
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


async def press_button(pilot, selector: str) -> None:
    """Scroll a button into view, as one would, then click it."""
    button = pilot.app.screen.reserve.query_one(selector)
    button.scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click(selector)
    await pilot.pause()


async def reserve_flow(pilot, screen: ReservePanel) -> None:
    """Reserve on the picked cluster, then Yes."""
    await press_button(pilot, "#reserve")
    assert screen.has_class("confirming")
    await press_button(pilot, "#send")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def test_reserving_is_in_the_same_panel() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        await set_value(pilot, screen.query_one("#duration", Select), timedelta(hours=2))
        start, end, _ = screen.window()
        assert "nancy/graffiti: it fits" in str(screen.query_one("#picked", Static).render())
        assert screen.queue_choices == ["production"]  # graffiti's queues, without admin

        await press_button(pilot, "#reserve")
        assert screen.has_class("confirming") and client.submitted == []  # it asks first
        assert "2 node(s) of graffiti at nancy" in str(screen.query_one("#confirm", Static).render())

        await press_button(pilot, "#send")
        await app.workers.wait_for_complete()
        await pilot.pause()
        [sent] = client.submitted
        assert (sent.site, sent.cluster, sent.nodes, sent.start, sent.walltime, sent.queue) == (
            "nancy", "graffiti", 2, start, end - start, "production")
        assert not screen.has_class("confirming")


async def test_enter_on_a_cluster_asks_too() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        table = screen.query_one("#results", DataTable)
        table.focus()
        await pilot.press("down")  # gros
        assert "nancy/gros: it fits" in str(screen.query_one("#picked", Static).render())
        assert screen.queue_choices == ["default"]
        await pilot.press("enter")
        await pilot.pause()
        assert screen.has_class("confirming")
        await pilot.press("escape")  # out of the question, not out of the screen
        await pilot.pause()
        assert app.screen.active == "reserving" and not screen.has_class("confirming") and client.submitted == []


async def test_back_and_changes_cancel_the_question() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await press_button(pilot, "#reserve")
        await press_button(pilot, "#back")
        assert not screen.has_class("confirming")

        await press_button(pilot, "#reserve")
        await set_value(pilot, screen.query_one("#deploy", Checkbox), True)  # a change: ask again
        assert not screen.has_class("confirming") and client.submitted == []

        await reserve_flow(pilot, screen)
        assert client.submitted[0].types == ("deploy",)


async def test_a_cluster_that_cant_take_it_isnt_reserved() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        await set_value(pilot, screen.query_one("#nodes", Input), "2")
        await set_value(pilot, screen.query_one("#only", Checkbox), False)
        table = screen.query_one("#results", DataTable)
        table.focus()
        await pilot.press("down")  # gros: only 1 free
        assert "no: only 1 free" in str(screen.query_one("#picked", Static).render())
        await pilot.press("enter")
        await pilot.pause()
        assert not screen.has_class("confirming") and client.submitted == []


async def test_a_site_whose_status_fails_is_loaded_cluster_by_cluster() -> None:
    client = FakeClient(TWO_SITES)
    client.broken_sites = {"nancy"}  # as bordeaux's did: the site-wide status crashes
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        assert [r[:2] for r in rows(screen)] == [["nancy", "graffiti"], ["nancy", "gros"], ["rennes", "paravance"]]
        assert str(screen.query_one("#status", Static).render()) == ""  # every cluster answered


async def test_when_every_cluster_fails_too_it_says_what_each_said() -> None:
    client = FakeClient(TWO_SITES)
    client.broken_sites = {"nancy"}
    client.nodes_error = None
    app = GridTUI(client)

    async def failing_nodes(site: str, cluster: str):
        raise RuntimeError(f"GET /sites/{site}/clusters/{cluster}/status: 500")

    client.nodes = failing_nodes  # every cluster's status fails as well
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        status = str(screen.query_one("#status", Static).render())
        assert "nancy: its status failed (GET /sites/nancy/status: 500" in status
        assert "graffiti: GET /sites/nancy/clusters/graffiti/status: 500" in status
        assert [r[0] for r in rows(screen)] == ["rennes"]  # the other sites still show


async def test_ctrl_g_shows_the_picked_clusters_current_reservations() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_reservable(pilot)
        screen.query_one("#results", DataTable).focus()
        await pilot.press("down", "ctrl+g")  # gros
        await settle(pilot)
        assert app.screen.active == "current" and app.screen.current.cluster.uid == "gros"
