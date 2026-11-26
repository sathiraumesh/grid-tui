"""Tests for Usage: how busy the nodes are, from a status answer."""

from grid_tui.models import Usage
from tests.grid5000.fakes import STATUS


def test_counts_busy_among_up_nodes() -> None:
    """Up is alive or standby; busy is a soft state starting with 'busy'."""
    usage = Usage.from_status(STATUS['nancy'])
    assert usage == Usage(busy=3, up=4)  # the dead node isn't counted
    assert usage.percent == 75


def test_free_now_busy_later_is_free() -> None:
    """'free_busy' is free now (and busy soon): not counted as busy."""
    assert Usage.from_status(STATUS['lyon']) == Usage(busy=1, up=2)


def test_sites_add_up() -> None:
    """Two sites' counts add up."""
    total = Usage.from_status(STATUS['nancy']) + Usage.from_status(STATUS['lyon'])
    assert total == Usage(busy=4, up=6)
    assert total.percent == 67


def test_no_nodes_is_zero_percent() -> None:
    """With no node up, it's 0%, not a division by zero."""
    assert Usage().percent == 0


def test_odd_answers_count_nothing() -> None:
    """An answer without nodes, or with broken ones, counts nothing."""
    assert Usage.from_status({}) == Usage()
    assert Usage.from_status([]) == Usage()
    assert Usage.from_status({'nodes': {'x': 'n/a', 'y': {'hard': 'alive'}}}) == Usage(
        busy=0, up=1
    )
