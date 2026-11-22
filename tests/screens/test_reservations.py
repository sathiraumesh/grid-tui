"""The reservations screen: opening it, its keys, the clock, going back."""

from __future__ import annotations

from datetime import timedelta

from grid_tui.app import GridTUI
from grid_tui.models import Mode
from grid_tui.screens import ClusterDetailScreen, ClustersScreen, ReservationsScreen
from tests.fakes import TWO_SITES, FakeClient, open_gros

SIZE = (140, 45)


def text(app: GridTUI) -> str:
    """What the reservations widget shows, as plain text."""
    return app.screen.view.render().plain


async def open_from_the_detail(pilot) -> ReservationsScreen:
    await open_gros(pilot)  # nancy → gros' detail
    await pilot.press("down", "enter")  # enter on gros-2
    await pilot.pause()
    screen = pilot.app.screen
    assert isinstance(screen, ReservationsScreen)
    return screen


async def test_enter_on_a_node_opens_the_reservations_on_it() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await open_gros(pilot)
        calls_before = client.calls
        await pilot.press("down", "enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ReservationsScreen)
        assert screen.gantt.selected.name == "gros-2"
        assert client.calls == calls_before  # the detail's nodes, not loaded again
        shown = text(app)
        assert "FREE" in shown and "gros-1" in shown and "┃" in shown
        assert screen.view.border_title == "site: nancy · cluster: gros · reservations: timeline · zoom 1h"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ClusterDetailScreen)


async def test_g_on_the_clusters_loads_and_opens_the_reservations() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("enter")  # nancy's clusters
        await pilot.pause()
        await pilot.press("down", "g")  # gros
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ReservationsScreen) and screen.cluster.uid == "gros"
        assert [n.name for n in screen.gantt.nodes] == ["gros-1", "gros-2", "gros-10"]
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ClustersScreen)


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
        await app.workers.wait_for_complete()
        await pilot.pause()
        g = screen.gantt
        assert (g.col, g.zoom, g.node) == (col, zoom, node)
        assert client.calls > 0
