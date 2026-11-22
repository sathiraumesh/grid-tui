"""Reservations › Current: the Gantt chart's keys, its views, the clock, the
mouse wheel; and reserving (b) and cancelling (x) from it."""

from __future__ import annotations

from datetime import timedelta

from textual.widgets import Checkbox, Input, Select, Static

from grid_tui.app import GridTUI
from grid_tui.models import Mode
from grid_tui.panels import ReservationsPanel
from grid_tui.screens import ConfirmDialog, MainScreen, ReserveDialog
from tests.fakes import TWO_SITES, FakeClient, open_gros, settle

SIZE = (140, 45)


def text(app: GridTUI) -> str:
    """What the Gantt chart shows, as plain text."""
    return app.screen.current.view.render().plain


async def open_from_the_detail(pilot) -> ReservationsPanel:
    """Nodes of gros → enter on gros-2: Current, on gros-2."""
    await open_gros(pilot)
    await pilot.press("down", "enter")
    await settle(pilot)
    assert pilot.app.screen.active == "current"
    return pilot.app.screen.current


async def test_current_shows_the_cluster_under_the_cursor_when_opened_directly() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        await pilot.press("enter")  # nancy's clusters
        await settle(pilot)
        await pilot.press("down", "4")  # the cursor on gros; then Current
        await settle(pilot)
        current = app.screen.current
        assert current.cluster.uid == "gros" and "FREE" in text(app) and "gros-1" in text(app)


async def test_timeline_keys() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        g = (await open_from_the_detail(pilot)).gantt
        start = g.col
        await pilot.press("right")
        assert g.col == start + 1
        await pilot.press("left", "L")
        assert g.col == start + 24
        await pilot.press("n")
        assert g.col == g.now_col
        await pilot.press("minus")
        assert g.cell == timedelta(hours=2)
        await pilot.press("plus", "plus")
        assert g.cell == timedelta(minutes=30)
        await pilot.press("up")
        assert g.node == 0
        await pilot.press("right_square_bracket")  # gros-1's next job: 4600
        assert g.selected_job().job_id == 4600


async def test_views_keys() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_from_the_detail(pilot)
        g = screen.gantt
        await pilot.press("w")
        assert g.mode is Mode.WEEK and "week of" in text(app)
        assert "reservations: week" in screen.view.border_title
        day = g.day
        await pilot.press("right", "down")
        assert g.day == day + timedelta(days=1, hours=2)
        await pilot.press("enter")  # the time line at that slot, 30 minute cells
        assert g.mode is Mode.TIMELINE and g.cursor_time == day + timedelta(days=1, hours=2)
        assert g.cell == timedelta(minutes=30)
        await pilot.press("m")
        assert g.mode is Mode.MONTH and "nodes free" in text(app)
        await pilot.press("v")
        assert g.mode is Mode.TIMELINE


async def test_the_clock_moves_now_without_loading() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_from_the_detail(pilot)
        calls, before = client.calls, screen.gantt.now
        screen.tick()
        assert screen.gantt.now > before
        assert client.calls == calls


async def test_reload_keeps_the_view_and_cursors() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_from_the_detail(pilot)
        await pilot.press("right", "minus")
        col, zoom, node = screen.gantt.col, screen.gantt.zoom, screen.gantt.node
        await pilot.press("r")
        await settle(pilot)
        g = screen.gantt
        assert (g.col, g.zoom, g.node) == (col, zoom, node)
        assert client.calls > 0


class Wheel:
    """A mouse wheel event, as the screen reads it."""

    def __init__(self, shift: bool = False) -> None:
        self.shift = shift

    def stop(self) -> None:
        pass


async def test_the_mouse_wheel_scrolls_both_ways() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        screen = await open_from_the_detail(pilot)  # gros-2, the cursor on now
        g = screen.gantt
        node, col = g.node, g.col
        screen.on_mouse_scroll_down(Wheel())
        assert g.node == node + 1 and g.col == col  # the wheel: the nodes
        screen.on_mouse_scroll_up(Wheel())
        assert g.node == node
        screen.on_mouse_scroll_down(Wheel(shift=True))
        assert g.col == col + 1  # shift+wheel: time
        screen.on_mouse_scroll_right(Wheel())
        screen.on_mouse_scroll_left(Wheel())
        assert g.col == col + 1

        await pilot.press("w")  # on the week: the wheel moves the slots
        day = g.day
        screen.on_mouse_scroll_down(Wheel())
        assert g.day == day + timedelta(hours=2)


# Reserving (b) and cancelling (x) from Current.


async def reservations(pilot) -> ReservationsPanel:
    return await open_from_the_detail(pilot)


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
        await reservations(pilot)
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
        await settle(pilot)
        assert isinstance(app.screen, MainScreen)
        [sent] = client.submitted
        assert (sent.nodes, sent.walltime, sent.project, sent.types) == (2, timedelta(hours=2), "my-lab", ("deploy",))


async def test_esc_and_cancel_send_nothing() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await reservations(pilot)
        await open_dialog(pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)
        await open_dialog(pilot)
        await pilot.click("#cancel")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen) and client.submitted == []


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
        await settle(pilot)
        assert "not enough resources" in str(screen.query_one(".status", Static).render())


async def test_x_cancels_your_job_after_yes() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await reservations(pilot)  # gros-2: bob's job 4521 now; the login is bob
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog) and "Cancel job #4521" in app.screen.question

        await pilot.press("n")  # no
        await pilot.pause()
        assert isinstance(app.screen, MainScreen) and client.cancelled == []

        await pilot.press("x")
        await pilot.pause()
        await pilot.click("#yes")
        await settle(pilot)
        assert client.cancelled == [4521]


async def test_x_refuses_another_s_job() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await reservations(pilot)
        await pilot.press("up")  # gros-1: free now
        await pilot.press("right_square_bracket")  # its next job: eve's 4600
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen) and client.cancelled == []  # no question: it isn't bob's


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
        await settle(pilot)
        assert len(client.submitted) == 1
