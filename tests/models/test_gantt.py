"""Gantt: a cluster's reservations in time."""

from datetime import datetime, timedelta

from grid_tui.models import Gantt, Mode, Node, Reservation
from grid_tui.models.gantt import SPAN, WEEK_SLOT

H = timedelta(hours=1)
LOADED = datetime(2026, 11, 22, 14, 30).astimezone()  # a Sunday


def at(h: int, m: int = 0, day: int = 22) -> datetime:
    return datetime(2026, 11, day, h, m).astimezone()


def sample() -> Gantt:
    """gros-1: job 1 13:30→16:30, then job 2 18:00→20:00 (also on gros-2);
    gros-2: a besteffort job 14:00→15:00; gros-3: dead."""
    return Gantt(
        nodes=[
            Node("gros-1", "alive", reservations=(
                Reservation(1, at(13, 30), at(16, 30), "bob"), Reservation(2, at(18), at(20), "eve"))),
            Node("gros-2", "alive", reservations=(
                Reservation(3, at(14), at(15), queue="besteffort"), Reservation(2, at(18), at(20), "eve"))),
            Node("gros-3", "dead"),
        ],
        loaded_at=LOADED,
    )


def test_cells() -> None:
    g = sample()
    assert g.origin == at(14) and g.cell == H
    assert g.max_col == int(SPAN / H) - 1
    g.zoom_by(-2)  # 15 minutes
    assert g.origin == at(14, 30)


def test_job_in() -> None:
    g = sample()
    g1, g2, _ = g.nodes
    assert g.job_in(g1, 0).job_id == 1  # 14:00
    assert g.job_in(g1, 2).job_id == 1  # 16:00: until 16:30
    assert g.job_in(g1, 3) is None  # 17:00
    assert g.job_in(g1, 4).job_id == 2
    assert g.job_in(g2, 0).job_id == 3  # only the besteffort one


def test_free() -> None:
    g = sample()
    assert g.free_in(0) == (1, 2)  # gros-2's besteffort counts as free
    assert g.free_in(3) == (2, 2)
    assert g.free_in(4) == (0, 2)
    assert g.free_between(at(16), at(18)) == (1, 2)


def test_jump_job_and_zoom() -> None:
    g = sample()
    g.jump_job(1)
    assert g.col == 4  # job 2 at 18:00
    g.jump_job(1)
    assert g.col == 4  # none after
    g.move_time(1)
    g.jump_job(-1)
    assert g.col == 0  # job 1's first cell
    g.move_time(4)
    g.zoom_by(-1)  # 30 minutes: still 18:00
    assert g.cursor_time == at(18)


def test_clock_moves_now_not_the_cells() -> None:
    g = sample()
    assert g.now == LOADED and g.now_col == 0
    g.clock = LOADED + 2 * H + timedelta(minutes=10)  # 16:40
    assert g.now_col == 2 and g.origin == at(14)
    g.to_now()
    assert g.col == 2
    g.clock = LOADED - H
    assert g.now == LOADED  # a clock before the load is ignored


def test_modes_keep_the_time() -> None:
    g = sample()
    g.move_time(4)  # 18:00
    g.set_mode(Mode.WEEK)
    assert g.day == at(18)
    g.move_day(1, 1)  # Mon 23 20:00
    g.set_mode(Mode.MONTH)
    assert g.day == at(0, day=23)
    g.set_mode(Mode.TIMELINE)
    assert g.cursor_time == at(0, day=23)


def test_move_day_stays_in_the_shown_time() -> None:
    g = sample()
    g.set_mode(Mode.WEEK)
    g.move_day(slots=-5)
    assert g.day == at(14)
    g.move_day(days=1000)
    assert g.day <= g.end
    g.set_mode(Mode.MONTH)
    g.move_day(days=-1000)
    assert g.day == at(0)


def test_day_free_and_jobs() -> None:
    g = sample()
    assert g.day_free(at(0)) == (0, 2, 2)
    assert g.day_free(at(0, day=23)) == (2, 2, 2)
    assert g.jobs_starting(at(0), at(0, day=23)) == 2  # 1 and 2; 3 is besteffort
    assert g.jobs_during(at(16), at(19)) == 2
    assert g.job_nodes(2) == 2


def test_free_span() -> None:
    g = sample()
    g.move_time(3)  # 17:00
    assert g.free_span(g.nodes[0]) == (at(16, 30), at(18))


def test_week_slot() -> None:
    assert WEEK_SLOT == 2 * H
