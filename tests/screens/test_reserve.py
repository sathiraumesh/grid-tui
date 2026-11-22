"""Reserving by choosing, and cancelling, from the reservations screen."""

from __future__ import annotations

from datetime import timedelta

from textual.widgets import Checkbox, Input, Select, Static

from grid_tui.app import GridTUI
from grid_tui.screens import ReservationsScreen
from grid_tui.screens.reserve import ConfirmDialog, ReserveDialog
from tests.fakes import TWO_SITES, FakeClient, open_gros

SIZE = (140, 45)


async def reservations(pilot) -> ReservationsScreen:
    await open_gros(pilot)
    await pilot.press("down", "enter")  # gros-2's reservations
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, ReservationsScreen)
    return screen


async def open_dialog(pilot) -> ReserveDialog:
    await pilot.press("b")
    await pilot.pause()
    dialog = pilot.app.screen
    assert isinstance(dialog, ReserveDialog)
    return dialog


async def test_b_opens_the_dialog_filled_from_the_cursor() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)
        await pilot.press("right", "right", "right", "right")  # 4 cells later
        cursor = screen.gantt.cursor_time
        dialog = await open_dialog(pilot)
        r = dialog.request()
        assert (r.site, r.cluster, r.nodes, r.start, r.walltime, r.queue) == (
            "nancy", "gros", 1, cursor, timedelta(hours=1), "default")
        assert not dialog.query_one("#asap", Checkbox).value
        assert "free all through" in str(dialog.query_one("#fit", Static).render())


async def test_reserve_asks_then_sends_only_on_yes() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)
        await pilot.press("right", "right", "right", "right")
        dialog = await open_dialog(pilot)
        dialog.query_one("#nodes", Select).value = 2
        dialog.query_one("#duration", Select).value = timedelta(hours=2)
        dialog.query_one("#project", Input).value = "my-lab"
        dialog.query_one("#deploy", Checkbox).value = True
        await pilot.pause()

        await pilot.click("#reserve")
        await pilot.pause()
        assert dialog.has_class("confirming") and client.submitted == []  # it asks first
        assert "2 node(s) of gros at nancy" in str(dialog.query_one("#confirm", Static).render())

        await pilot.click("#back")
        await pilot.pause()
        assert not dialog.has_class("confirming") and client.submitted == []

        await pilot.click("#reserve")
        await pilot.pause()
        await pilot.click("#send")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.screen is screen
        [sent] = client.submitted
        assert (sent.nodes, sent.walltime, sent.project, sent.types) == (2, timedelta(hours=2), "my-lab", ("deploy",))


async def test_esc_and_cancel_send_nothing() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)
        await open_dialog(pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is screen
        await open_dialog(pilot)
        await pilot.click("#cancel")
        await pilot.pause()
        assert app.screen is screen and client.submitted == []


async def test_as_soon_as_possible_from_now() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await reservations(pilot)  # the cursor on now
        dialog = await open_dialog(pilot)
        assert dialog.query_one("#asap", Checkbox).value
        assert dialog.request().start is None


async def test_a_refused_reservation_is_said() -> None:
    client = FakeClient(TWO_SITES)
    client.jobs_error = RuntimeError("POST /sites/nancy/jobs: 400 Bad Request: not enough resources")
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)
        await open_dialog(pilot)
        await pilot.click("#reserve")
        await pilot.pause()
        await pilot.click("#send")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "not enough resources" in str(screen.query_one("#status", Static).render())


async def test_x_cancels_your_job_after_yes() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)  # gros-2: bob's job 4521 now; the login is bob
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog) and "Cancel job #4521" in app.screen.question

        await pilot.press("n")  # no
        await pilot.pause()
        assert app.screen is screen and client.cancelled == []

        await pilot.press("x")
        await pilot.pause()
        await pilot.click("#yes")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert client.cancelled == [4521]


async def test_x_refuses_another_s_job() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await reservations(pilot)
        await pilot.press("up")  # gros-1: free now
        await pilot.press("right_square_bracket")  # its next job: eve's 4600
        await pilot.press("x")
        await pilot.pause()
        assert app.screen is screen and client.cancelled == []  # no question: it isn't bob's


async def test_the_dialog_scrolls_on_a_small_terminal() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await reservations(pilot)
        await pilot.resize_terminal(50, 14)  # narrower and shorter than the dialog
        await pilot.pause()
        dialog = await open_dialog(pilot)
        box = dialog.query_one("#dialog")
        assert box.max_scroll_y > 0, "it should scroll up and down"
        assert box.max_scroll_x > 0, "it should scroll sideways"

        # tab to the Reserve button: the dialog scrolls it into view
        reserve = dialog.query_one("#reserve")
        while app.focused is not reserve:
            await pilot.press("tab")
        await pilot.pause()
        assert box.scroll_y > 0
        await pilot.press("enter")
        await pilot.pause()
        assert dialog.has_class("confirming") and app.focused is dialog.query_one("#send")
        await pilot.press("enter")  # Yes, send
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert len(client.submitted) == 1
