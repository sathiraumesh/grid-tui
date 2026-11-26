"""Tests for the timeline drawing: axis, policy band, rows, bars, free strip."""

from datetime import datetime

from rich.text import Text

from grid_tui.models import Reservation, Schedule
from grid_tui.policy import PARIS
from grid_tui.widgets.panels.reservations.timeline import (
    ADMIN,
    MINE,
    Row,
    Window,
    axis_lines,
    bar_line,
    colour_of,
    free_strip,
    group_rows,
    label_of,
    now_label,
    policy_band,
    slot_line,
    tick_hours,
    with_now,
)
from tests.grid5000.fakes import HOUR, SCHEDULE, SCHEDULE_NOW

WIDTH = 48
# 24 h from 21:00 Thursday: 2 columns an hour
WINDOW = Window(SCHEDULE_NOW - HOUR, SCHEDULE_NOW + 23 * HOUR)


def colour_at(text: Text, offset: int) -> str:
    """The colour of the character at an offset (from the text's spans)."""
    styles = [str(span.style) for span in text.spans if span.start <= offset < span.end]
    return styles[-1] if styles else ''


def test_window_around_starts_a_little_before_now() -> None:
    """around() puts now an eighth of the way in."""
    window = Window.around(SCHEDULE_NOW, 24)
    assert window.span == 24 * HOUR
    assert window.start == SCHEDULE_NOW - 3 * HOUR


def test_columns_and_moments() -> None:
    """Each column is half an hour here; moment() is its middle."""
    assert WINDOW.column(SCHEDULE_NOW, WIDTH) == 2
    assert WINDOW.moment(0, WIDTH) == WINDOW.start + HOUR / 4


def test_colours() -> None:
    """Yours green, maintenance red, others by number (the same each time)."""
    assert colour_of(Reservation(1, user='alice'), me='alice') == MINE
    assert colour_of(Reservation(1, queue='admin')) == ADMIN
    assert colour_of(Reservation(5)) == colour_of(Reservation(5))
    assert colour_of(Reservation(5)) not in (MINE, ADMIN)


def test_labels() -> None:
    """'#uid yours', else '#uid name', else '#uid user'."""
    assert label_of(Reservation(7, user='alice'), me='alice') == '#7 yours'
    assert label_of(Reservation(7, user='bob', name='train')) == '#7 train'
    assert label_of(Reservation(7, user='bob')) == '#7 bob'


def test_tick_hours_keep_labels_apart() -> None:
    """Wider windows get labels every few hours."""
    assert tick_hours(Window(0, 12 * HOUR), 100) == 1
    assert tick_hours(Window(0, 24 * HOUR), 48) == 3
    assert tick_hours(Window(0, 7 * 24 * HOUR), 100) == 12
    assert tick_hours(Window(0, 7 * 24 * HOUR), 60) == 24


def test_axis_shows_hours_and_the_next_day() -> None:
    """The hours line has hour labels; the days line names Friday at midnight."""
    days, hours = axis_lines(WINDOW, WIDTH)
    assert len(days.plain) == len(hours.plain) == WIDTH
    assert days.plain.startswith('Thu 26')
    assert 'Fri 27' in days.plain
    assert '00' in hours.plain


def test_policy_band_is_lighter_in_the_daytime() -> None:
    """Friday 09:00 to 19:00 is daytime: those columns are another colour."""
    band = policy_band(WINDOW, WIDTH)
    assert len(band.plain) == WIDTH
    night = colour_at(band, 0)
    friday_noon = WINDOW.column(
        datetime(2026, 11, 27, 12, tzinfo=PARIS).timestamp(), WIDTH
    )
    day = colour_at(band, friday_noon)
    assert night != day


def test_rows_put_alike_neighbours_together() -> None:
    """gros-1 and 2 share job 11: one row; gros-3 is dead: its own row."""
    rows = group_rows(Schedule.from_status(SCHEDULE))
    assert [row.nodes for row in rows] == [
        ('gros-1', 'gros-2'),
        ('gros-3',),
        ('gros-4',),
        ('gros-10',),
    ]
    assert rows[0].label == 'gros-1…2'
    assert not rows[1].is_up


def test_a_bar_with_its_label_and_the_now_line() -> None:
    """Your job is a labelled bar, labelled just after the now line."""
    rows = group_rows(Schedule.from_status(SCHEDULE))
    window = Window(SCHEDULE_NOW - HOUR, SCHEDULE_NOW + 11 * HOUR)  # 8 columns/h
    width = 96
    line = bar_line(rows[0], window, width, me='alice', now=SCHEDULE_NOW)
    now = window.column(SCHEDULE_NOW, width)
    assert len(line.plain) == width
    assert line.plain[now] == '┃'
    assert line.plain[now + 1 :].startswith(' #11 yours')
    assert line.plain[-1] == '·'  # free after the job ends: the dotted guide


def test_a_down_node_is_dashed() -> None:
    """A dead node's row is a dashed line."""
    line = bar_line(Row(('gros-3',), 'dead', ()), WINDOW, WIDTH)
    assert set(line.plain) == {'╌'}


def test_best_effort_is_hatched() -> None:
    """A best-effort job is drawn with ░, not a solid bar."""
    job = Reservation(
        9, queue='besteffort', start=int(WINDOW.start), end=int(WINDOW.end)
    )
    line = bar_line(Row(('n-1',), 'alive', (job,)), WINDOW, WIDTH)
    assert set(line.plain) == {'░'}


def test_a_label_shows_only_if_its_number_fits() -> None:
    """A bar too short for '#uid' has no label: no stray fragments."""
    start = int(WINDOW.start + 10 * HOUR)
    short = Reservation(7081934, user='bob', start=start, end=start + HOUR)
    line = bar_line(Row(('n-1',), 'alive', (short,)), WINDOW, WIDTH)
    assert '#' not in line.plain


def test_free_strip() -> None:
    """Red where no node is free; green bars, scaled to the most free."""
    schedule = Schedule.from_status(SCHEDULE)
    strip = free_strip(schedule, WINDOW, WIDTH)
    assert len(strip.plain) == WIDTH
    assert '█' in strip.plain  # the most free in the window is a full bar
    full = Schedule(
        {'n-1': 'alive'},
        (
            Reservation(
                1,
                start=int(WINDOW.start),
                end=int(WINDOW.end),
                nodes=frozenset({'n-1'}),
            ),
        ),
    )
    none_free = free_strip(full, WINDOW, WIDTH)
    assert set(none_free.plain) == {'▁'}
    assert ADMIN in colour_at(none_free, 0)


def test_slot_line_marks_the_slot() -> None:
    """The slot's columns are ━, with ┣ and ┫ at its ends; the rest blank."""
    start = SCHEDULE_NOW + 2 * HOUR
    line = slot_line(WINDOW, WIDTH, start, start + 3 * HOUR)
    first, last = (
        WINDOW.column(start, WIDTH),
        WINDOW.column(start + 3 * HOUR - 1, WIDTH),
    )
    assert line.plain[first] == '┣'
    assert line.plain[last] == '┫'
    assert set(line.plain[first + 1 : last]) == {'━'}
    assert line.plain[:first].strip() == ''


def test_now_runs_down_every_line() -> None:
    """with_now marks now's column with ┃ on any line, at the same place."""
    column = WINDOW.column(SCHEDULE_NOW, WIDTH)
    marked = with_now(Text(' ' * WIDTH), WINDOW, WIDTH, SCHEDULE_NOW)
    assert marked.plain[column] == '┃'
    assert len(marked.plain) == WIDTH
    band = with_now(policy_band(WINDOW, WIDTH), WINDOW, WIDTH, SCHEDULE_NOW)
    assert band.plain[column] == '┃'


def test_now_label() -> None:
    """The top line says 'now' beside the line; on the left edge, after it."""
    label = now_label(WINDOW, WIDTH, SCHEDULE_NOW)  # column 2: near the left
    assert label.plain.startswith('  ┃ now')
    later = SCHEDULE_NOW + 6 * HOUR
    label = now_label(WINDOW, WIDTH, later)
    column = WINDOW.column(later, WIDTH)
    assert label.plain[column - 4 : column + 1] == 'now ┃'


def test_now_outside_the_window_draws_nothing() -> None:
    """Panned away from now: no line, no label."""
    later = Window(SCHEDULE_NOW + 2 * 24 * HOUR, SCHEDULE_NOW + 3 * 24 * HOUR)
    assert '┃' not in with_now(Text(' ' * WIDTH), later, WIDTH, SCHEDULE_NOW).plain
    assert now_label(later, WIDTH, SCHEDULE_NOW).plain.strip() == ''


def test_free_time_is_a_dotted_line() -> None:
    """A row with nothing reserved is dots all along, to follow it across."""
    line = bar_line(Row(('gros-4',), 'alive', ()), WINDOW, WIDTH)
    assert set(line.plain) == {'·'}


def test_now_is_red() -> None:
    """The now line is the strong red, not maintenance's softer one."""
    from grid_tui.widgets.panels.reservations.timeline import NOW_RED

    column = WINDOW.column(SCHEDULE_NOW, WIDTH)
    marked = with_now(Text(' ' * WIDTH), WINDOW, WIDTH, SCHEDULE_NOW)
    assert NOW_RED in colour_at(marked, column)
    assert NOW_RED != ADMIN
