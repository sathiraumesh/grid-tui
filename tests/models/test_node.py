"""Node: what a machine does at a given moment."""

from datetime import datetime, timedelta

from grid_tui.models import Node, Reservation, node_order

NOW = datetime(2026, 11, 22, 14, 30).astimezone()
H = timedelta(hours=1)


def job(id: int, start: float, end: float, queue: str = "default") -> Reservation:
    return Reservation(id, NOW + start * H, NOW + end * H, queue=queue)


def test_now() -> None:
    assert Node("a", "alive", reservations=(job(1, -1, 1),)).now(NOW) == "busy"
    assert Node("a", "alive", reservations=(job(1, 1, 2),)).now(NOW) == "free"
    assert Node("a", "alive", reservations=(job(1, -1, 1, "besteffort"),)).now(NOW) == "besteffort"
    assert Node("a", "alive", reservations=(job(1, -1, 1, "besteffort"), job(2, -1, 1))).now(NOW) == "busy"
    assert Node("a", "dead").now(NOW) == "down"
    assert Node("a", "alive", reservations=(job(1, -2, 0),)).now(NOW) == "free"  # ended right now


def test_job_is_the_current_one_else_the_next() -> None:
    n = Node("a", "alive", reservations=(job(1, -1, 1, "besteffort"), job(2, -1, 1), job(3, 2, 3)))
    assert n.job(NOW).job_id == 2  # regular before besteffort
    assert n.job(NOW + 1.5 * H).job_id == 3  # nothing now: the next one
    assert n.job(NOW + 5 * H) is None


def test_node_order() -> None:
    names = ["gros-10", "gros-2", "gros-1", "graffiti-3", "odd"]
    assert [n.name for n in sorted((Node(x) for x in names), key=node_order)] == [
        "graffiti-3", "gros-1", "gros-2", "gros-10", "odd",
    ]
