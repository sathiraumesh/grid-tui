"""Tests for the new reservation pop-up: the form, what it costs, its answer."""

from datetime import datetime

import pytest
from textual.app import App
from textual.widgets import Input, Static

from grid_tui.policy import PARIS
from grid_tui.widgets.popups.new_reservation import NewReservation, ReservationRequest
from grid_tui.widgets.popups.new_reservation.new_reservation import (
    read_start,
    start_text,
)

THURSDAY_9 = datetime(2026, 11, 26, 9, 0, tzinfo=PARIS).timestamp()


def at(hour: int) -> float:
    """Thursday at an hour, in seconds since 1970."""
    return THURSDAY_9 + (hour - 9) * 3600


def test_read_start() -> None:
    """'now' or nothing is None; a time is read in Paris; the past is now."""
    assert read_start('now', THURSDAY_9) is None
    assert read_start('', THURSDAY_9) is None
    assert read_start('2026-11-26 14:00', THURSDAY_9) == at(14)
    assert read_start('2026-11-25 14:00', THURSDAY_9) is None  # gone: now
    with pytest.raises(ValueError):
        read_start('tomorrow', THURSDAY_9)


def test_start_text() -> None:
    """How a start shows in its box."""
    assert start_text(None) == 'now'
    assert start_text(at(14)) == '2026-11-26 14:00'


class FormApp(App):
    """An app that opens the form at once and keeps its answer."""

    def __init__(self, **form: object) -> None:
        super().__init__()
        self.form = form
        self.answers: list[ReservationRequest | None] = []

    def on_mount(self) -> None:
        settings = {'node_cores': 18, 'cluster_cores': 36, 'free_nodes': 2}
        settings.update(self.form)
        self.push_screen(
            NewReservation('nancy', 'gros', now=lambda: THURSDAY_9, **settings),
            self.answers.append,
        )


def cost(app: App) -> str:
    """What the form says the reservation costs."""
    return str(app.screen.query_one('#new-cost', Static).render())


async def test_filled_in_and_says_the_quota_it_uses() -> None:
    """1 node × 2 h at 10:00: half of gros's daytime quota."""
    app = FormApp(nodes=1, seconds=2 * 3600, start=at(10))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.screen.query_one('#new-nodes', Input).value == '1'
        assert app.screen.query_one('#new-hours', Input).value == '2'
        assert app.screen.query_one('#new-start', Input).value == '2026-11-26 10:00'
        assert 'day: 2 h quota' in cost(app)
        assert 'About 50% of the day’s quota' in cost(app)


async def test_too_many_nodes_and_over_the_quota_are_said() -> None:
    """3 nodes when 2 can run, all day: over the quota, and too many."""
    app = FormApp(nodes=3, seconds=8 * 3600, start=at(10))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert 'Over the quota' in cost(app)
        assert 'Only 2 nodes can run jobs' in cost(app)


async def test_a_wrong_box_says_what_to_fix() -> None:
    """No nodes: the cost line says so, and Reserve doesn't close the form."""
    app = FormApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.screen.query_one('#new-nodes', Input).value = '0'
        await pilot.pause()
        assert 'Ask for 1 node or more.' in cost(app)
        await pilot.click('#reserve')
        await pilot.pause()
        assert app.answers == []
        assert isinstance(app.screen, NewReservation)


async def test_reserve_answers_with_the_request() -> None:
    """Reserve closes the form with what it says."""
    app = FormApp(nodes=2, seconds=3600, start=at(20))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.screen.query_one('#new-name', Input).value = 'exp'
        await pilot.click('#new-deploy')
        await pilot.click('#reserve')
        await pilot.pause()
        assert app.answers == [
            ReservationRequest(
                nodes=2, seconds=3600, start=at(20), name='exp', deploy=True
            )
        ]


async def test_escape_cancels() -> None:
    """Esc closes the form with nothing."""
    app = FormApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.answers == [None]
