"""Drawing a cluster's reservations as a timeline, one text line at a time.

Time runs left to right over a window; each column is a slice of it. These
functions only build Rich Text, so they are easy to test on their own; the
ReservationsPanel puts them on screen.

    window = Window.around(now, hours=24)
    axis_lines(window, width)            # the dates and hours on top
    policy_band(window, width)           # daytime (quota) vs free time
    group_rows(schedule)                 # nodes with the same jobs, together
    bar_line(row, window, width, me)     # one row of reservation bars
    free_strip(schedule, window, width)  # how many nodes are free, over time
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from rich.text import Text

from grid_tui.models.reservation import UP, Reservation, Schedule, node_number
from grid_tui.policy import PARIS, period_at

# colours (the app's palette)
BACKGROUND = '#181818'
DARK = '#1e1e2e'  # text on a bar
MUTED = '#6c7086'
FAINT = '#313244'
NOW = '#fab387'  # orange: warnings, e.g. a slot in daytime-quota hours
NOW_RED = '#ff4d5e'  # the now line: a strong red (brighter than maintenance)
MINE = '#a6e3a1'  # your jobs: green
ADMIN = '#f38ba8'  # maintenance: red
DOWN = '#45475a'
DAY = '#45475a'  # daytime (the quota applies)
FREE_TIME = '#2a2b3d'  # nights, weekends, holidays
# no reds or pinks (maintenance is red) and no green (yours) or orange (now)
JOB_COLOURS = (
    '#89b4fa',  # blue
    '#cba6f7',  # mauve
    '#94e2d5',  # teal
    '#f9e2af',  # yellow
    '#74c7ec',  # sapphire
    '#b4befe',  # lavender
    '#89dceb',  # sky
)
SPARKS = ' ▁▂▃▄▅▆▇█'
NOW_LINE = '┃'  # now, drawn down the whole timeline
GUIDE = '·'  # a row's free time: a dotted line to follow it across
GUIDE_COLOUR = '#45475a'


@dataclass(frozen=True)
class Window:
    """The stretch of time on screen."""

    start: float  # seconds since 1970
    end: float

    @classmethod
    def around(cls, now: float, hours: float) -> Window:
        """A window of some hours, starting a little before now (1/8 of it)."""
        span = hours * 3600
        start = now - span / 8
        return cls(start, start + span)

    @property
    def span(self) -> float:
        """How long it is, in seconds."""
        return self.end - self.start

    def moment(self, column: int, width: int) -> float:
        """The time in the middle of a column."""
        return self.start + (column + 0.5) * self.span / width

    def column(self, moment: float, width: int) -> int:
        """The column a moment falls in (may be outside 0..width-1)."""
        return int((moment - self.start) * width / self.span)


def colour_of(reservation: Reservation, me: str = '') -> str:
    """A job's colour: yours green, maintenance red, others by their number."""
    if me and reservation.user == me:
        return MINE
    if reservation.is_maintenance:
        return ADMIN
    return JOB_COLOURS[reservation.uid % len(JOB_COLOURS)]


def label_of(reservation: Reservation, me: str = '') -> str:
    """What a bar says: 'yours', the job's name, or its user, then its number."""
    if me and reservation.user == me:
        who = 'yours'
    else:
        who = reservation.name or reservation.user
    return f'#{reservation.uid} {who}'.strip()


# The top: dates, hours, and the policy band


def tick_hours(window: Window, width: int) -> int:
    """How many hours between labels, so they don't crowd: 1, 3, 6, 12 or 24."""
    hours = window.span / 3600
    for step in (1, 3, 6, 12, 24):
        if width / (hours / step) >= 6:  # at least 6 columns per label
            return step
    return 24


def tick_days(window: Window, width: int) -> int:
    """How many days between date labels, so they don't crowd: 1, 2, 3, 7 or 14.

    Used when even one label a day is too many hours to name (a week or a
    month on screen).
    """
    days = window.span / 86400
    for step in (1, 2, 3, 7, 14):
        if width / (days / step) >= 8:  # at least 8 columns per label
            return step
    return 14


def axis_lines(window: Window, width: int) -> tuple[Text, Text]:
    """Two lines over the bars: the days, and the hours.

    Over a week or a month, the hours give way to dates: the top line names
    the month, the second a date every day or few days.

    Returns:
        (days, hours): e.g. 'Thu 26 ... Fri 27' and '18    21    00 ...'; or,
        over a month, 'November 2026 ... December' and '26 Nov  29 Nov ...'.
    """
    days: list[tuple[str, str]] = [(' ', MUTED)] * width
    hours: list[tuple[str, str]] = [(' ', MUTED)] * width
    step = tick_hours(window, width)
    moment = datetime.fromtimestamp(window.start, PARIS).replace(
        minute=0, second=0, microsecond=0
    )
    day_style = f'bold {MUTED}'
    if step >= 24 and tick_days(window, width) > 1:
        return _date_axis(window, width, moment)
    _put(days, 0, moment.strftime('%a %d'), day_style)  # the first day
    while moment.timestamp() < window.end:
        column = window.column(moment.timestamp(), width)
        if 0 <= column < width:
            if moment.hour % step == 0:
                label = f'{moment.hour:02}' if step < 24 else moment.strftime('%a %d')
                _put(hours, column, label, MUTED)
            if moment.hour == 0 and step < 24 and column > 0:
                _put(days, column, moment.strftime('%a %d'), day_style)
        moment += timedelta(hours=1)
    return _text(days), _text(hours)


def _date_axis(window: Window, width: int, moment: datetime) -> tuple[Text, Text]:
    """The axis over many days: the months, and a date every few days.

    The dates are those whose day number since 1 January 1 divides by the
    step, so they stay the same days while you move earlier and later.
    """
    months: list[tuple[str, str]] = [(' ', MUTED)] * width
    dates: list[tuple[str, str]] = [(' ', MUTED)] * width
    every = tick_days(window, width)
    style = f'bold {MUTED}'
    _put(months, 0, moment.strftime('%B %Y'), style)  # the first month
    day = moment.replace(hour=0)
    while day.timestamp() < window.end:
        column = window.column(day.timestamp(), width)
        if 0 <= column < width:
            if day.toordinal() % every == 0:
                _put(dates, column, day.strftime('%d %b'), MUTED)
            if day.day == 1 and column > 0:
                _put(months, column, day.strftime('%B'), style)
        day = (day + timedelta(days=1)).replace(hour=0)  # midnight, even on DST days
    return _text(months), _text(dates)


def policy_band(window: Window, width: int) -> Text:
    """A thin band: lighter where the daytime quota applies, dark where it's free."""
    band = Text()
    for column in range(width):
        moment = datetime.fromtimestamp(window.moment(column, width), PARIS)
        colour = DAY if period_at(moment).name == 'Day' else FREE_TIME
        band.append('▀', colour)
    return band


# The rows: nodes with the same reservations, together


@dataclass(frozen=True)
class Row:
    """One line of the timeline: one node, or a run of nodes alike."""

    nodes: tuple[str, ...]
    state: str  # the nodes' hard state, e.g. 'alive', 'dead'
    reservations: tuple[Reservation, ...]

    @property
    def label(self) -> str:
        """'gros-1', or 'gros-77…124' for a run of nodes."""
        if len(self.nodes) == 1:
            return self.nodes[0]
        first, last = self.nodes[0], self.nodes[-1]
        prefix, number = node_number(last)
        if node_number(first)[0] == prefix and prefix:
            return f'{first}…{number}'
        return f'{first}…{last}'

    @property
    def is_up(self) -> bool:
        """Can these nodes run jobs."""
        return self.state in UP


def group_rows(schedule: Schedule) -> list[Row]:
    """The timeline's rows: neighbouring nodes with the same jobs share one.

    Two nodes are alike when they are in the same state and hold exactly the
    same reservations. Only neighbours (in number order) are put together, so
    the rows still read in order.
    """
    rows: list[Row] = []
    for node in schedule.node_names:
        state = schedule.nodes[node]
        on = tuple(schedule.on(node))
        uids = [r.uid for r in on]
        if rows:
            last = rows[-1]
            if last.state == state and [r.uid for r in last.reservations] == uids:
                rows[-1] = Row((*last.nodes, node), state, last.reservations)
                continue
        rows.append(Row((node,), state, on))
    return rows


def bar_line(
    row: Row, window: Window, width: int, me: str = '', now: float = 0
) -> Text:
    """One row: a coloured bar for each reservation, labelled when it fits.

    Args:
        row: The row to draw.
        window: The time on screen.
        width: How many columns.
        me: Your login, so your jobs show green and say 'yours'.
        now: The time now, drawn as a thin orange line; 0 for none.
    """
    if not row.is_up:
        return Text('╌' * width, DOWN)
    now_column = window.column(now, width) if now else -1
    cells: list[tuple[str, str]] = [(GUIDE, GUIDE_COLOUR)] * width
    for reservation in row.reservations:
        first = max(window.column(reservation.start, width), 0)
        last = min(window.column(reservation.end - 1, width), width - 1)
        if last < 0 or first >= width or last < first:
            continue
        colour = colour_of(reservation, me)
        if reservation.is_besteffort:
            cells[first : last + 1] = [('░', colour)] * (last - first + 1)
            continue
        cells[first : last + 1] = [(' ', f'on {colour}')] * (last - first + 1)
        # the label: after the now line if the bar runs across it (that's
        # where you look), else at the bar's start; only if it fits
        start = now_column + 1 if first <= now_column < last else first
        if last - start + 1 < 4:
            start = first
        room = last - start + 1
        label = label_of(reservation, me)
        if room >= len(f'#{reservation.uid}') + 2:  # at least its whole number
            text = (' ' + label)[: room - 1]
            for offset, char in enumerate(text):
                cells[start + offset] = (char, f'{DARK} on {colour}')
    if now:
        column = now_column
        if 0 <= column < width:
            char, style = cells[column]
            background = style.split('on ', 1)[1] if 'on ' in style else ''
            cells[column] = (
                NOW_LINE,
                f'bold {NOW_RED}' + (f' on {background}' if background else ''),
            )
    return _text(cells)


def free_strip(schedule: Schedule, window: Window, width: int) -> Text:
    """How many nodes are free over time, as a sparkline; red where none are.

    The bars are scaled to the most free in the window (not to every node),
    so a few free nodes still show: what matters is when they open up.
    """
    counts = [schedule.free_at(window.moment(c, width)) for c in range(width)]
    most = max(counts, default=0)
    strip = Text()
    for free in counts:
        if free == 0:
            strip.append('▁', ADMIN)
            continue
        level = max(1, round(free / most * (len(SPARKS) - 1)))
        strip.append(SPARKS[level], MINE)
    return strip


def _put(cells: list[tuple[str, str]], column: int, label: str, style: str) -> None:
    """Write a label into a line of cells at a column, if it fits there."""
    if column < 0 or column + len(label) > len(cells):
        return
    for offset, char in enumerate(label):
        cells[column + offset] = (char, style)


def _text(cells: list[tuple[str, str]]) -> Text:
    """A line of (character, style) cells as Rich Text."""
    line = Text()
    for char, style in cells:
        line.append(char, style)
    return line


def slot_line(window: Window, width: int, start: float, end: float) -> Text:
    """A line marking a time slot: ━━━ under the columns it covers."""
    first = max(window.column(start, width), 0)
    last = min(window.column(end - 1, width), width - 1)
    cells: list[tuple[str, str]] = [(' ', '')] * width
    if first <= last and last >= 0 and first < width:
        for column in range(first, last + 1):
            cells[column] = ('━', f'bold {MINE}')
        _put(cells, first, '┣', f'bold {MINE}')
        _put(cells, last, '┫', f'bold {MINE}')
    return _text(cells)


def with_now(
    line: Text, window: Window, width: int, now: float, *, over_marks: bool = True
) -> Text:
    """The line with now marked on it: an orange ┃, so now runs top to bottom.

    Args:
        line: The line to mark.
        window: The time on screen.
        width: How many columns.
        now: The time now.
        over_marks: False keeps what's already drawn at now's column (only
            a blank is replaced), e.g. the start of a slot that begins now.
    """
    column = window.column(now, width)
    if not 0 <= column < len(line.plain):
        return line
    if not over_marks and line.plain[column] != ' ':
        return line
    marked = line[:column]
    marked.append(NOW_LINE, f'bold {NOW_RED}')
    marked.append_text(line[column + 1 :])
    return marked


def now_label(window: Window, width: int, now: float) -> Text:
    """The line over the axis: 'now ┃' at now's column (or '┃ now' near the left)."""
    column = window.column(now, width)
    cells: list[tuple[str, str]] = [(' ', '')] * width
    if 0 <= column < width:
        style = f'bold {NOW_RED}'
        if column >= 4:
            _put(cells, column - 4, 'now ', style)
        else:
            _put(cells, column + 1, ' now', style)
        cells[column] = (NOW_LINE, style)
    return _text(cells)
