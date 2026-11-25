"""Tests for format: how sizes, numbers, flags and times read on screen."""

from grid_tui.format import duration, interval, number, size, yes_no


def test_size():
    """Sizes use the biggest unit that fits; 0 is empty."""
    assert size(96 * 1024**3) == '96 GiB'
    assert size(2 * 1024**4) == '2 TiB'
    assert size(512 * 1024**2) == '512 MiB'
    assert size(32 * 1024) == '32 KiB'
    assert size(100) == '100 B'
    assert size(0) == ''


def test_number():
    """Numbers drop a needless .0; 0 is empty."""
    assert number(18) == '18'
    assert number(2.5) == '2.5'
    assert number(0) == ''


def test_yes_no():
    """A flag reads as yes or no."""
    assert (yes_no(True), yes_no(False)) == ('yes', 'no')


def test_duration():
    """Seconds read as hours and minutes; 0 is empty."""
    assert duration(7200) == '2 h'
    assert duration(5400) == '1 h 30 min'
    assert duration(600) == '10 min'
    assert duration(30) == '30 s'
    assert duration(0) == ''


def test_interval():
    """Milliseconds read as ms, s or min; 0 is empty."""
    assert interval(20) == '20 ms'
    assert interval(1000) == '1 s'
    assert interval(2500) == '2.5 s'
    assert interval(60000) == '1 min'
    assert interval(0) == ''
