"""Which Grid'5000 usage-policy period it is: day, night, weekend or holiday.

From https://www.grid5000.fr/w/Grid5000:UsagePolicy, in Paris time:

- Day: working days (Monday to Friday, not French public holidays), 09:00 to
  19:00. In the default queue you may use at most the equivalent of 2 hours on
  all the cores of a cluster per day.
- Any other time (nights, weekends, holidays) is for large experiments.

    period_at(datetime.now(PARIS))
    # Period(name='Day', rule='2 h quota', ends=datetime(..., 19, 0))
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')
DAY_START = time(9, 0)
DAY_END = time(19, 0)
DAY_RULE = '2 h quota'
FREE_RULE = 'free use'


@dataclass(frozen=True)
class Period:
    """A stretch of the week under one rule."""

    name: str  # 'Day', 'Night', 'Weekend' or 'Holiday'
    rule: str  # what you may do: '2 h quota' or 'free use'
    ends: datetime  # when the next period starts, in Paris time

    def until(self, now: datetime) -> str:
        """When it ends, for a person: '19:00' today, 'Mon 09:00' later on.

        Args:
            now: The time to read it from, e.g. datetime.now(PARIS).
        """
        now = now.astimezone(PARIS)
        clock = self.ends.strftime('%H:%M')
        if self.ends.date() == now.date():
            return clock
        if self.ends.date() == now.date() + timedelta(days=1):
            return f'tomorrow {clock}'
        return f'{self.ends.strftime("%a")} {clock}'

    def describe(self, now: datetime) -> str:
        """One line: 'Day · 2 h quota · until 19:00'."""
        return f'{self.name} · {self.rule} · until {self.until(now)}'


def easter(year: int) -> date:
    """Easter Sunday of a year (the Gregorian calendar's rule).

    Easter is the first Sunday after the first full moon on or after 21 March.
    This is the Meeus/Jones/Butcher way of working that out with whole numbers.
    """
    # where the year is in the 19-year cycle after which the moon's phases
    # fall on the same dates again
    moon_cycle_year = year % 19
    century, year_in_century = divmod(year, 100)
    # the Gregorian calendar skips the leap day in 3 of every 4 century years
    skipped_leap_days, century_in_cycle = divmod(century, 4)
    # small corrections: the real moon drifts from the 19-year cycle
    moon_drift = (century + 8) // 25
    moon_correction = (century - moon_drift + 1) // 3
    # days from 21 March to the first full moon after it (the Paschal full moon)
    days_to_full_moon = (
        19 * moon_cycle_year + century - skipped_leap_days - moon_correction + 15
    ) % 30
    leap_years_so_far, years_since_leap = divmod(year_in_century, 4)
    # days from that full moon to the next Sunday
    days_to_sunday = (
        32
        + 2 * century_in_cycle
        + 2 * leap_years_so_far
        - days_to_full_moon
        - years_since_leap
    ) % 7
    # a rare fix-up that keeps Easter from landing a week too late
    late_fix = (moon_cycle_year + 11 * days_to_full_moon + 22 * days_to_sunday) // 451
    month, day_before = divmod(
        days_to_full_moon + days_to_sunday - 7 * late_fix + 114, 31
    )
    return date(year, month, day_before + 1)


def french_holidays(year: int) -> set[date]:
    """France's public holidays in a year (the national ones)."""
    sunday = easter(year)
    return {
        date(year, 1, 1),  # New Year's Day
        sunday + timedelta(days=1),  # Easter Monday
        date(year, 5, 1),  # Labour Day
        date(year, 5, 8),  # Victory in Europe Day
        sunday + timedelta(days=39),  # Ascension Day
        sunday + timedelta(days=50),  # Whit Monday
        date(year, 7, 14),  # Bastille Day
        date(year, 8, 15),  # Assumption
        date(year, 11, 1),  # All Saints' Day
        date(year, 11, 11),  # Armistice Day
        date(year, 12, 25),  # Christmas
    }


def is_working_day(day: date) -> bool:
    """Monday to Friday, and not a French public holiday."""
    return day.weekday() < 5 and day not in french_holidays(day.year)


def next_working_day(day: date) -> date:
    """The first working day after day."""
    day += timedelta(days=1)
    while not is_working_day(day):
        day += timedelta(days=1)
    return day


def period_at(now: datetime) -> Period:
    """The policy period at a moment.

    Args:
        now: The moment; any timezone (it is read in Paris time). A naive
            datetime is taken to be Paris time already.
    """
    now = now.replace(tzinfo=PARIS) if now.tzinfo is None else now.astimezone(PARIS)
    today = now.date()

    def at(day: date, clock: time) -> datetime:
        return datetime.combine(day, clock, tzinfo=PARIS)

    if is_working_day(today):
        if now.time() < DAY_START:
            return Period('Night', FREE_RULE, at(today, DAY_START))
        if now.time() < DAY_END:
            return Period('Day', DAY_RULE, at(today, DAY_END))
    # outside the day: free until the next working day's morning
    back = next_working_day(today)
    ends = at(back, DAY_START)
    if back == today + timedelta(days=1) and is_working_day(today):
        name = 'Night'  # an ordinary weeknight
    elif any(
        (today + timedelta(days=n)).weekday() >= 5 for n in range((back - today).days)
    ):
        name = 'Weekend'
    else:
        name = 'Holiday'
    return Period(name, FREE_RULE, ends)
