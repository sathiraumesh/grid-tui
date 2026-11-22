"""A cluster's reservations, seen three ways (Gantt.mode):

  - a time line: a row per node, a column ("cell") per period of time, from
    when the nodes were loaded on. A time cursor (col) picks a cell; with
    the selected node (node) it picks a job.
  - a week: a column per day, a row per WEEK_SLOT; each slot says how many
    nodes are free all through it.
  - a month: a calendar of days; each says how many nodes are free at its
    worst and best moments, and how many jobs start.

The week and the month share their own cursor (day): a slot's or a day's
start. The cells stay where the load put them; the clock (the time now)
moves on its own, so the now marks move without loading again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from grid_tui.models.node import Node, Reservation

MINUTE, HOUR, DAY = timedelta(minutes=1), timedelta(hours=1), timedelta(days=1)

# How long one cell of the time line lasts, from the closest to the widest.
ZOOMS = [15 * MINUTE, 30 * MINUTE, HOUR, 2 * HOUR, 4 * HOUR, 12 * HOUR]
DEFAULT_ZOOM = 2  # 1 hour per cell

SPAN = 6 * 7 * DAY  # how far ahead it goes: six weeks, so a month has something to show
WEEK_SLOT = 2 * HOUR  # how long one row of the week lasts


class Mode(Enum):
    TIMELINE = "timeline"
    WEEK = "week"
    MONTH = "month"


def midnight(t: datetime) -> datetime:
    """The start of t's day."""
    return t.replace(hour=0, minute=0, second=0, microsecond=0)


def slot_start(t: datetime, slot: timedelta) -> datetime:
    """The start of the slot holding t, slots counted from midnight (so
    cells fall on round hours)."""
    m = midnight(t)
    return m + ((t - m) // slot) * slot


def monday(t: datetime) -> datetime:
    """The start of t's week."""
    return midnight(t) - t.weekday() * DAY


@dataclass
class Gantt:
    nodes: list[Node]
    loaded_at: datetime  # when the nodes were loaded: where the cells start
    clock: datetime | None = None  # the time now, kept up to date; None: loaded_at
    mode: Mode = Mode.TIMELINE
    zoom: int = DEFAULT_ZOOM  # index into ZOOMS
    col: int = 0  # the time line's cursor: cells from origin
    node: int = 0  # the selected node
    day: datetime | None = field(default=None)  # the week's and the month's cursor

    # Time.

    @property
    def now(self) -> datetime:
        """The clock if it has moved on since the load, else the load."""
        return self.clock if self.clock is not None and self.clock > self.loaded_at else self.loaded_at

    @property
    def cell(self) -> timedelta:
        return ZOOMS[self.zoom]

    @property
    def origin(self) -> datetime:
        """When the first cell starts: the start of the cell holding the load."""
        return slot_start(self.loaded_at, self.cell)

    @property
    def end(self) -> datetime:
        return self.loaded_at + SPAN

    def cell_start(self, col: int) -> datetime:
        return self.origin + col * self.cell

    @property
    def max_col(self) -> int:
        return int(SPAN / self.cell) - 1

    @property
    def cursor_time(self) -> datetime:
        return self.cell_start(self.col)

    @property
    def now_col(self) -> int:
        """The cell holding the time now."""
        return int((self.now - self.origin) / self.cell)

    # Moving.

    def move_node(self, step: int) -> None:
        self.node = max(min(self.node + step, len(self.nodes) - 1), 0)

    def move_time(self, step: int) -> None:
        self.col = max(min(self.col + step, self.max_col), 0)

    def zoom_by(self, step: int) -> None:
        """Shorter (negative) or longer cells, the cursor at about the same time."""
        at = self.cursor_time
        self.zoom = max(min(self.zoom + step, len(ZOOMS) - 1), 0)
        self.col = int((at - self.origin) / self.cell)
        self.move_time(0)

    def zoom_to(self, i: int) -> None:
        self.zoom = max(min(i, len(ZOOMS) - 1), 0)

    def to_now(self) -> None:
        """The cursor back on the time now, in every view."""
        self.col, self.day = 0, None
        if self.mode is Mode.TIMELINE:
            self.move_time(self.now_col)
        else:
            self.set_mode(self.mode)

    def set_mode(self, mode: Mode) -> None:
        """Show another view, the cursor at about the same time."""
        at = self.cursor_time if self.mode is Mode.TIMELINE else (self.day or self.now)
        self.mode = mode
        if mode is Mode.TIMELINE:
            self.col = int((max(at, self.origin) - self.origin) / self.cell)
            self.move_time(0)
        elif mode is Mode.WEEK:
            self.day = slot_start(at, WEEK_SLOT)
        else:
            self.day = midnight(at)

    def move_day(self, days: int = 0, slots: int = 0) -> None:
        """Move the week's or the month's cursor, within the shown time."""
        at = (self.day or self.now) + days * DAY + slots * WEEK_SLOT
        if self.mode is Mode.MONTH:
            at, first, last = midnight(at), midnight(self.now), midnight(self.end)
        else:
            first, last = slot_start(self.now, WEEK_SLOT), slot_start(self.end, WEEK_SLOT)
        self.day = min(max(at, first), last)

    # What the nodes do.

    @property
    def selected(self) -> Node | None:
        return self.nodes[self.node] if self.nodes else None

    def job_in(self, n: Node, col: int) -> Reservation | None:
        """Node n's job in cell col: the regular job overlapping it most,
        else a besteffort one."""
        start = self.cell_start(col)
        end = start + self.cell
        best, best_overlap = None, timedelta(0)
        for r in n.reservations:
            overlap = min(r.end, end) - max(r.start, start)
            if overlap <= timedelta(0):
                continue
            if r.besteffort:
                overlap /= 1000  # a regular job wins
            if best is None or overlap > best_overlap:
                best, best_overlap = r, overlap
        return best

    def selected_job(self) -> Reservation | None:
        n = self.selected
        return self.job_in(n, self.col) if n else None

    def jump_job(self, step: int) -> None:
        """The cursor to the next (step > 0) or previous job of the node."""
        n = self.selected
        if n is None:
            return
        cur = self.job_in(n, self.col)
        col = self.col + step
        while 0 <= col <= self.max_col:
            r = self.job_in(n, col)
            if r is not None and (cur is None or r.job_id != cur.job_id):
                if step < 0:  # go to that job's first cell
                    while col > 0 and (p := self.job_in(n, col - 1)) is not None and p.job_id == r.job_id:
                        col -= 1
                self.col = col
                return
            col += step

    def free_between(self, start: datetime, end: datetime) -> tuple[int, int]:
        """How many usable nodes have no regular job at any time in
        [start, end), and how many are usable."""
        free = usable = 0
        for n in self.nodes:
            slot = n.slot(start, end)
            if slot == "down":
                continue
            usable += 1
            if slot != "busy":
                free += 1
        return free, usable

    def free_in(self, col: int) -> tuple[int, int]:
        start = self.cell_start(col)
        return self.free_between(start, start + self.cell)

    def job_nodes(self, job_id: int) -> int:
        """How many nodes job_id holds."""
        return sum(any(r.job_id == job_id for r in n.reservations) for n in self.nodes)

    def free_span(self, n: Node) -> tuple[datetime, datetime | None]:
        """The free time around the cursor on n: from the end of the job
        before it (or now) to the start of the next (None: none known)."""
        at, start, end = self.cursor_time, self.now, None
        for r in n.reservations:
            if r.besteffort:
                continue
            if r.end <= at and r.end > start:
                start = r.end
            if r.start > at and (end is None or r.start < end):
                end = r.start
        return start, end

    def day_free(self, day: datetime) -> tuple[int, int, int]:
        """The fewest and the most nodes free during the day (hour by hour,
        from now on), and the usable ones."""
        least, most, usable = None, 0, 0
        t, end = max(day, slot_start(self.now, HOUR)), min(day + DAY, self.end)
        while t < end:
            free, usable = self.free_between(t, t + HOUR)
            least = free if least is None else min(least, free)
            most = max(most, free)
            t += HOUR
        return least or 0, most, usable

    def jobs_starting(self, start: datetime, end: datetime) -> int:
        return len({r.job_id for n in self.nodes for r in n.reservations if not r.besteffort and start <= r.start < end})

    def jobs_during(self, start: datetime, end: datetime) -> int:
        return len({r.job_id for n in self.nodes for r in n.reservations if not r.besteffort and r.start < end and r.end > start})
