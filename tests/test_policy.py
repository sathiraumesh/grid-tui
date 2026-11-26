"""Tests for the usage-policy periods: day, night, weekend and holidays."""

from datetime import date, datetime, timezone

import pytest

from grid_tui.policy import PARIS, easter, french_holidays, is_working_day, period_at


def paris(*args: int) -> datetime:
    """A Paris time, e.g. paris(2026, 11, 26, 10) for Thursday 10:00."""
    return datetime(*args, tzinfo=PARIS)


@pytest.mark.parametrize(
    ('year', 'sunday'),
    [
        (2000, date(2000, 4, 23)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_easter(year: int, sunday: date) -> None:
    """Easter Sunday is worked out right, early and late years alike."""
    assert easter(year) == sunday


def test_holidays_that_move_with_easter() -> None:
    """Easter Monday, Ascension and Whit Monday follow Easter."""
    holidays = french_holidays(2026)
    assert date(2026, 4, 6) in holidays  # Easter Monday
    assert date(2026, 5, 14) in holidays  # Ascension
    assert date(2026, 5, 25) in holidays  # Whit Monday
    assert date(2026, 7, 14) in holidays
    assert len(holidays) == 11


def test_working_days() -> None:
    """Monday to Friday are working days, except holidays."""
    assert is_working_day(date(2026, 11, 26))  # a Thursday
    assert not is_working_day(date(2026, 11, 28))  # a Saturday
    assert not is_working_day(date(2026, 11, 11))  # Armistice Day, a Wednesday


@pytest.mark.parametrize(
    ('now', 'name', 'rule', 'until'),
    [
        (paris(2026, 11, 26, 10), 'Day', '2 h quota', '19:00'),
        (paris(2026, 11, 26, 18, 59), 'Day', '2 h quota', '19:00'),
        (paris(2026, 11, 26, 8, 30), 'Night', 'free use', '09:00'),
        (paris(2026, 11, 26, 19), 'Night', 'free use', 'tomorrow 09:00'),
        (paris(2026, 11, 27, 20), 'Weekend', 'free use', 'Mon 09:00'),
        (paris(2026, 11, 28, 12), 'Weekend', 'free use', 'Mon 09:00'),
        (paris(2026, 11, 30, 8), 'Night', 'free use', '09:00'),
        (paris(2026, 11, 11, 12), 'Holiday', 'free use', 'tomorrow 09:00'),
        (paris(2026, 11, 10, 20), 'Holiday', 'free use', 'Thu 09:00'),
    ],
)
def test_period_at(now: datetime, name: str, rule: str, until: str) -> None:
    """The period, its rule, and when it ends, at different times of the week."""
    period = period_at(now)
    assert (period.name, period.rule, period.until(now)) == (name, rule, until)


def test_describe() -> None:
    """describe() says it all on one line."""
    now = paris(2026, 11, 26, 10)
    assert period_at(now).describe(now) == 'Day · 2 h quota · until 19:00'


def test_other_timezones_are_read_in_paris_time() -> None:
    """08:30 UTC in winter is 09:30 in Paris: day, not night."""
    now = datetime(2026, 11, 26, 8, 30, tzinfo=timezone.utc)
    assert period_at(now).name == 'Day'


def test_a_naive_time_is_paris_time() -> None:
    """A time with no timezone is taken as Paris time."""
    assert period_at(datetime(2026, 11, 26, 10)).name == 'Day'
