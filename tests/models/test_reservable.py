"""Which clusters can take a reservation for a window."""

from datetime import datetime, timedelta

from grid_tui.models import Availability, Node, Reservation
from grid_tui.models.reservable import availability, by_cluster, cluster_of, rank

NOW = datetime(2026, 11, 22, 14, 0).astimezone()
H = timedelta(hours=1)


def test_cluster_of() -> None:
    assert cluster_of("gros-12") == "gros"
    assert cluster_of("dahu-3") == "dahu"
    assert cluster_of("chirop-1") == "chirop"
    assert cluster_of("odd") == "odd"


def test_by_cluster() -> None:
    nodes = [Node("gros-10"), Node("graffiti-1"), Node("gros-2")]
    assert {c: [n.name for n in ns] for c, ns in by_cluster(nodes).items()} == {
        "graffiti": ["graffiti-1"], "gros": ["gros-2", "gros-10"],
    }


def test_availability() -> None:
    nodes = [
        Node("gros-1", "alive"),  # free
        Node("gros-2", "alive", reservations=(Reservation(1, NOW + H, NOW + 3 * H),)),  # busy in the window
        Node("gros-3", "alive", reservations=(Reservation(2, NOW, NOW + 5 * H, queue="besteffort"),)),  # counts as free
        Node("gros-4", "dead"),
    ]
    a = availability("nancy", "gros", nodes, NOW + 2 * H, NOW + 4 * H, wanted=2)
    assert (a.free, a.usable, a.reservable, a.reason()) == (2, 3, True, "yes")
    assert availability("nancy", "gros", nodes, NOW + 2 * H, NOW + 4 * H, wanted=3).reason() == "no: only 2 free"
    assert availability("nancy", "gros", nodes, NOW + 2 * H, NOW + 4 * H, wanted=4).reason() == (
        "no: it has 3 usable node(s)"
    )
    # after job 1 ends, gros-2 is free too
    assert availability("nancy", "gros", nodes, NOW + 3 * H, NOW + 4 * H, wanted=3).reservable


def test_rank() -> None:
    found = [Availability("a", "x", 1, 5, 2), Availability("b", "y", 9, 9, 2), Availability("a", "z", 3, 3, 2)]
    assert [a.cluster for a in rank(found)] == ["y", "z", "x"]  # reservable first, the most free first
