"""Tests for Schedule and Reservation: a cluster's reservations, put together."""

from grid_tui.models import Reservation, Schedule
from grid_tui.models.reservation import node_number, short_name
from tests.grid5000.fakes import HOUR, SCHEDULE, SCHEDULE_NOW


def schedule() -> Schedule:
    """The fake gros cluster's schedule."""
    return Schedule.from_status(SCHEDULE)


def test_names_and_order() -> None:
    """Hosts become short names, in number order: gros-4 before gros-10."""
    assert short_name('gros-12.nancy.grid5000.fr') == 'gros-12'
    assert node_number('gros-10') == ('gros', 10)
    assert schedule().node_names == ['gros-1', 'gros-2', 'gros-3', 'gros-4', 'gros-10']


def test_a_job_on_many_nodes_is_one_reservation() -> None:
    """Job 11 is listed on gros-1 and gros-2: one reservation, both nodes."""
    job = next(r for r in schedule().reservations if r.uid == 11)
    assert job.nodes == {'gros-1', 'gros-2'}
    assert (job.start, job.end) == (SCHEDULE_NOW - HOUR, SCHEDULE_NOW + 2 * HOUR)
    assert job.is_running


def test_a_waiting_job_starts_when_scheduled() -> None:
    """A waiting job starts at its scheduled_at; it's maintenance (admin)."""
    job = next(r for r in schedule().reservations if r.uid == 22)
    assert job.start == SCHEDULE_NOW + 4 * HOUR
    assert job.is_maintenance
    assert not job.is_running


def test_a_job_not_scheduled_yet_is_left_out() -> None:
    """Job 33 has no start time: nothing to draw."""
    assert 33 not in [r.uid for r in schedule().reservations]


def test_free_at() -> None:
    """Now: gros-1 and 2 are taken, 3 is dead: gros-4 and gros-10 are free."""
    assert schedule().up == 4
    assert schedule().free_at(SCHEDULE_NOW) == 2
    assert schedule().free_at(SCHEDULE_NOW + 5 * HOUR) == 3  # 11 ended, 22 runs


def test_on_a_node() -> None:
    """The reservations on one node."""
    assert [r.uid for r in schedule().on('gros-10')] == [22]
    assert schedule().on('gros-4') == []


def test_besteffort() -> None:
    """The besteffort queue or type is best-effort."""
    assert Reservation(1, queue='besteffort').is_besteffort
    assert Reservation(1, types=('besteffort',)).is_besteffort
    assert not Reservation(1, queue='default').is_besteffort


def test_odd_answers() -> None:
    """A broken answer gives an empty schedule."""
    assert Schedule.from_status({}) == Schedule()
    assert Schedule.from_status({'nodes': {'x': 'n/a'}}) == Schedule()


# Finding a free slot


def test_a_slot_now_when_enough_nodes_are_free() -> None:
    """2 nodes (gros-4 and gros-10) are free for the next 2 hours: slot now."""
    slot = schedule().find_slot(2, 2 * HOUR, SCHEDULE_NOW)
    assert slot == (SCHEDULE_NOW, ['gros-4', 'gros-10'])


def test_a_slot_opens_when_a_job_ends() -> None:
    """3 nodes free for 1 h: only once job 11 ends (gros-1 and 2 come free)."""
    slot = schedule().find_slot(3, HOUR, SCHEDULE_NOW)
    assert slot is not None
    assert slot[0] == SCHEDULE_NOW + 2 * HOUR
    assert len(slot[1]) >= 3


def test_a_reservation_later_blocks_a_long_slot() -> None:
    """gros-10 is free now but taken at +4 h: 2 nodes for 5 h must wait."""
    start, nodes = schedule().find_slot(2, 5 * HOUR, SCHEDULE_NOW)
    assert start == SCHEDULE_NOW + 2 * HOUR  # gros-1, 2 and 4 are free from then
    assert 'gros-10' not in nodes


def test_no_slot_for_more_nodes_than_are_up() -> None:
    """5 nodes can never be free: one of the five is dead."""
    assert schedule().find_slot(5, HOUR, SCHEDULE_NOW) is None
    assert schedule().find_slot(0, HOUR, SCHEDULE_NOW) is None
