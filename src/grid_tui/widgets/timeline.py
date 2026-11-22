"""Drawing a cluster's reservations (a Gantt) as coloured lines, for the
time line, the week and the month. draw() is what the widget calls; it
also says how many lines stay on top (pinned) and which line to keep in
sight (focus) while the rest scrolls.

Time line (a column per cell, from the load on):

    now 14:37 · zoom 1h per cell · Sun 22 14:00 → Sun 03 14:00 · cursor 18:00
    gros-2 · #4600 eve · default · Waiting · 18:00→20:00 (2h) · on 2 nodes
    ███ jobs (a colour each)  █ selected job  ░ besteffort  · free  ┃ now  × down  ▲ cursor

                 Sun 22                    Mon 23
                 ┃     18:00       00:00       06:00
      FREE     ▄▄┃▁▁▄██████████████
                 ┃   ▲
      gros-1   ██┃·#4600█···············
    ▸ gros-2   ░·┃··#4600█··············
      gros-3   ××┃×××××××××××××××××××××

Every job has its own colour (taken in turns, in the order jobs start) and
its number written in it where it fits; the job under the cursor is yellow
on every node it holds. The red ┃ is the time now, through every row.

Week: a column per day, a row per 2-hour slot, each the nodes free all
through it on green (half or more), amber (fewer) or red (none); the time
now is a red line across. Month: a calendar, each day its fewest–most free
nodes and how many jobs start.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from rich.text import Text

from grid_tui.format import clock, duration, jobs
from grid_tui.models import Gantt, Mode, Node, Reservation
from grid_tui.models.gantt import DAY, HOUR, MINUTE, WEEK_SLOT, midnight, monday

# Colours.
JOB_COLORS = [
    "#2563EB", "#EA580C", "#16A34A", "#9333EA", "#DC2626", "#0891B2", "#CA8A04", "#DB2777",
    "#4F46E5", "#65A30D", "#0D9488", "#C026D3", "#B45309", "#0284C7", "#BE123C", "#7C3AED",
]
SELECTED_JOB = "#FDE047"
FREE_CELL = "#3F7D4E"
MUTED = "#9D9D9D"
NOW = "bold #F14C4C"
DOWN = "#F14C4C"
OK = "#73C991"
MANY_FREE, SOME_FREE, NONE_FREE = "white on #1F6F3F", "white on #8A6200", "white on #8B1E1E"
PAST = "#5A5A5A"
CURSOR = "black on #FDE047"

TIMELINE_HEADER = 8  # info (3), an empty line, days, hours, FREE, cursor
WEEK_HEADER = 5  # info (3), an empty line, the day names
MONTH_HEADER = 5  # info (3), an empty line, the weekday names


def draw(g: Gantt, width: int) -> tuple[list[Text], int, int]:
    """The lines of g's view for width columns, how many stay on top, and
    the line to keep in sight."""
    if g.mode is Mode.WEEK:
        return week(g, width), WEEK_HEADER, week_focus(g)
    if g.mode is Mode.MONTH:
        return month(g, width), MONTH_HEADER, month_focus(g)
    return timeline(g, width), TIMELINE_HEADER, TIMELINE_HEADER + g.node


def window(lines: list[Text], pinned: int, focus: int, height: int) -> list[Text]:
    """The lines that fit in height rows: the pinned ones, then the rest
    scrolled as little as needed to keep line focus in sight."""
    pinned = max(min(pinned, len(lines), height), 0)
    rest, room = lines[pinned:], height - pinned
    first = max(focus - pinned - room + 1, 0) if room > 0 else 0
    return lines[:pinned] + rest[first : first + max(room, 0)]


def fit(t: Text, width: int) -> Text:
    """t cut to width columns: a line never wraps."""
    t = t.copy()
    t.truncate(width, overflow="ellipsis")
    return t


# The time line.


def job_colors(g: Gantt) -> dict[int, str]:
    """A colour for every regular job, in turns, in the order jobs start:
    jobs next to each other get different colours."""
    starts: dict[int, datetime] = {}
    for n in g.nodes:
        for r in n.reservations:
            if not r.besteffort:
                starts.setdefault(r.job_id, r.start)
    order = sorted(starts, key=lambda j: (starts[j], j))
    return {j: JOB_COLORS[i % len(JOB_COLORS)] for i, j in enumerate(order)}


def timeline(g: Gantt, width: int) -> list[Text]:
    name_w = max([len("FREE")] + [len(n.name) for n in g.nodes])
    left = 2 + name_w + 1  # "▸ " + name + " "
    cols = max(width - left, 1)
    first = g.col - cols + 1 if g.col >= cols else 0  # scrolled to keep the cursor in sight
    end = min(first + cols, g.max_col + 1)
    now_i = g.now_col - first
    pad = " " * left

    lines = [
        fit(Text(zoom_line(g), style=MUTED), width),
        fit(selected_line(g), width),
        fit(legend(), width),
        Text(""),
        Text(pad) + now_through(day_row(g, first, end), now_i),
        Text(pad) + now_through(hour_row(g, first, end), now_i),
        Text("  " + "FREE".ljust(name_w) + " ") + free_row(g, first, end),
        Text(pad) + now_through(cursor_row(g.col - first, end - first), now_i),
    ]
    if not g.nodes:
        return lines + [Text("no nodes", style=MUTED)]
    colors = job_colors(g)
    sel = g.selected_job()
    for i, n in enumerate(g.nodes):
        selected = i == g.node
        name = Text("▸ " if selected else "  ") + Text(n.name.ljust(name_w), style="reverse" if selected else "")
        lines.append(name + Text(" ") + node_row(g, n, first, end, colors, sel.job_id if sel else None, selected))
    return lines


def zoom_line(g: Gantt) -> str:
    now = g.now
    last = g.cell_start(g.max_col + 1)
    return (f"now {now:%H:%M} · zoom {duration(g.cell)} per cell · "
            f"{g.origin:%a %d %H:%M} → {clock(last, now)} · cursor {clock(g.cursor_time, now)}")


def selected_line(g: Gantt) -> Text:
    """The selected node at the cursor: its job, how long it is free, or down."""
    n, now = g.selected, g.now
    if n is None:
        return Text("")
    if not n.usable:
        return Text(f"{n.name} · down ({n.hard})", style=DOWN)
    r = g.job_in(n, g.col)
    if r is not None:
        held = g.job_nodes(r.job_id)
        return Text(
            f"{n.name} · #{r.job_id} {r.user or '-'} · {r.queue or '-'} · {r.state or '-'} · "
            f"{clock(r.start, now)}→{clock(r.end, now)} ({duration(r.end - r.start)}) · "
            f"on {held} node{'s' if held != 1 else ''}",
            style=f"bold {CURSOR}",
        )
    start, end = g.free_span(n)
    if end is None:
        return Text(f"{n.name} · free from {clock(start, now)}, no job after", style=OK)
    return Text(f"{n.name} · free {clock(start, now)}→{clock(end, now)} ({duration(end - start)})", style=OK)


def legend() -> Text:
    t = Text()
    for c in JOB_COLORS[:3]:
        t.append("█", style=c)
    t.append(" jobs (a colour each)  ")
    t.append("█", style=SELECTED_JOB)
    t.append(" selected job  ")
    t.append("░", style=MUTED)
    t.append(" besteffort  ")
    t.append("·", style=FREE_CELL)
    t.append(" free  ")
    t.append("┃", style=NOW)
    t.append(" now  ")
    t.append("×", style=DOWN)
    t.append(" down  ▲ cursor")
    return t


def place(row: list[str], i: int, free: int, label: str) -> int:
    """Write label into row at i if it fits after free; the next free column."""
    if i < free or i + len(label) > len(row):
        return free
    row[i : i + len(label)] = list(label)
    return i + len(label) + 1


def day_row(g: Gantt, first: int, end: int) -> str:
    """The day ("Mon 23") where each day starts."""
    row, free = [" "] * (end - first), 0
    for col in range(first, end):
        t = g.cell_start(col)
        if col == first or g.cell_start(col - 1).date() != t.date():
            free = place(row, col - first, free, t.strftime("%a %d"))
    return "".join(row)


def label_step(cell: timedelta) -> timedelta | None:
    """How often to write a time: the shortest round period at least 6
    cells long ("18:00" and a space); None: days only."""
    for s in (15 * MINUTE, 30 * MINUTE, HOUR, 2 * HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY):
        if s >= cell and s / cell >= 6:
            return s
    return None


def hour_row(g: Gantt, first: int, end: int) -> str:
    """The time ("18:00") every few cells, on round times."""
    row, free = [" "] * (end - first), 0
    step = label_step(g.cell)
    if step is None:
        return "".join(row)
    for col in range(first, end):
        t = g.cell_start(col)
        if (t - midnight(t)) % step == timedelta(0):
            free = place(row, col - first, free, t.strftime("%H:%M"))
    return "".join(row)


def cursor_row(i: int, n: int) -> str:
    row = [" "] * n
    if 0 <= i < n:
        row[i] = "▲"
    return "".join(row).rstrip()


def now_through(row: str, i: int) -> Text:
    """The red now line at column i of a plain row, where it is blank."""
    if i < 0:
        return Text(row)
    row = row.ljust(i + 1)
    if row[i] != " ":
        return Text(row.rstrip())
    return Text(row[:i]) + Text("┃", style=NOW) + Text(row[i + 1 :].rstrip())


def free_row(g: Gantt, first: int, end: int) -> Text:
    """A bar per cell, as high as the share of nodes free (▁ to █), or a
    red · when none is."""
    bars = "▁▂▃▄▅▆▇█"
    t = Text()
    for col in range(first, end):
        free, usable = g.free_in(col)
        if usable == 0:
            t.append(" ")
        elif free == 0:
            t.append("·", style=DOWN)
        else:
            t.append(bars[(free * len(bars) - 1) // usable], style=OK)
    return t


def node_row(g: Gantt, n: Node, first: int, end: int, colors: dict[int, str], sel: int | None, selected: bool) -> Text:
    """One node's cells: jobs in their colours with their numbers, ░
    besteffort, · free, × down, and the time now as a red ┃. The cursor's
    cell on the selected node is reversed."""
    chars: list[str] = []
    styles: list[str] = []
    ids: list[int | None] = []
    for col in range(first, end):
        r: Reservation | None = g.job_in(n, col)
        if not n.usable:
            ch, st, jid = "×", DOWN, None
        elif r is not None and not r.besteffort:
            ch, st, jid = "█", SELECTED_JOB if r.job_id == sel else colors.get(r.job_id, JOB_COLORS[0]), r.job_id
        elif r is not None:
            ch, st, jid = "░", MUTED, None
        else:
            ch, st, jid = "·", FREE_CELL, None
        chars.append(ch)
        styles.append(st)
        ids.append(jid)

    now_i = g.now_col - first
    # Each job's number at the start of its run of cells, where it fits; the
    # now line may cut the run, then the number goes in the part it fits in.
    i = 0
    while i < len(ids):
        j = i
        while j < len(ids) and ids[j] == ids[i]:
            j += 1
        jid = ids[i]
        if jid is not None:
            at, room = i, j - i
            if i <= now_i < j:
                at, room = i, now_i - i
                if room < len(str(jid)):
                    at, room = now_i + 1, j - now_i - 1
            label = f"#{jid}" if len(f"#{jid}") <= room else str(jid)
            if len(label) <= room:
                bg = SELECTED_JOB if jid == sel else colors.get(jid, JOB_COLORS[0])
                fg = "black" if jid == sel else "white"
                for k, ch in enumerate(label):
                    chars[at + k], styles[at + k] = ch, f"bold {fg} on {bg}"
        i = j

    if 0 <= now_i < len(chars):
        on = f" on {colors.get(ids[now_i], JOB_COLORS[0])}" if ids[now_i] is not None else ""
        chars[now_i], styles[now_i] = "┃", NOW + on
    if selected and 0 <= g.col - first < len(chars):
        styles[g.col - first] += " reverse"

    t = Text()
    for ch, st in zip(chars, styles):
        t.append(ch, style=st)
    return t


# The week.


def free_style(free: int, usable: int) -> str:
    if free == 0:
        return NONE_FREE
    return MANY_FREE if free * 2 >= usable else SOME_FREE


def calendar_legend() -> Text:
    t = Text()
    t.append(" half or more free ", style=MANY_FREE)
    t.append(" ")
    t.append(" fewer ", style=SOME_FREE)
    t.append(" ")
    t.append(" none ", style=NONE_FREE)
    t.append("  ")
    t.append(" cursor ", style=CURSOR)
    t.append("  ")
    t.append("· past or not shown", style=PAST)
    return t


def cell(text: str, w: int) -> str:
    return text[:w].ljust(w) + " "


def now_in_week(g: Gantt, start: datetime) -> tuple[int, int] | None:
    """The slot (row) and day (column) holding now in the week from start."""
    now = g.now
    if not start <= now < start + 7 * DAY:
        return None
    return int((now - midnight(now)) / WEEK_SLOT), (midnight(now) - start).days


def week(g: Gantt, width: int) -> list[Text]:
    now, cur = g.now, g.day or g.now
    start = monday(cur)
    col_w = max((width - 6) // 7 - 1, 4)
    to = cur + WEEK_SLOT
    free, usable = g.free_between(cur, to)
    detail = (f"{cur:%a %d} {cur:%H:%M}–{to:%H:%M} · {free} of {usable} nodes free all through · "
              f"{jobs(g.jobs_during(cur, to))}, {g.jobs_starting(cur, to)} start")
    lines = [
        fit(Text(f"week of {start:%a %d %b} · {duration(WEEK_SLOT)} slots · cursor {clock(cur, now)}", style=MUTED), width),
        fit(Text(detail, style=free_style(free, usable)), width),
        fit(calendar_legend(), width),
        Text(""),
    ]
    head = Text("      ")
    for d in range(7):
        day = start + d * DAY
        head.append(cell(day.strftime("%a %d"), col_w), style="bold underline" if day.date() == now.date() else "bold")
    lines.append(head)

    now_at = now_in_week(g, start)
    for i in range(int(DAY / WEEK_SLOT)):
        row = Text((start + i * WEEK_SLOT).strftime("%H:%M") + " ")
        for d in range(7):
            a = start + d * DAY + i * WEEK_SLOT
            b = a + WEEK_SLOT
            if b <= now or a >= g.end:
                row.append(cell("·", col_w), style=PAST)
                continue
            f, u = g.free_between(a, b)
            label = f"{f} free" if col_w >= len(f"{f} free") else str(f)
            row.append(label[:col_w].ljust(col_w), style=CURSOR if a == g.day else free_style(f, u))
            row.append(" ")
        lines.append(fit(row, width))
        if now_at is not None and i == now_at[0]:
            lines.append(fit(now_line(now, now_at[1], col_w), width))
    return lines


def now_line(now: datetime, day: int, col_w: int) -> Text:
    """The line across the week at the time now: bright red on today's
    column, dim on the others."""
    t = Text(f"{now:%H:%M} ", style=NOW)
    for d in range(7):
        if d == day:
            t.append("━" * (col_w + 1), style=NOW)
        else:
            t.append("─" * col_w + " ", style=PAST)
    return t


def week_focus(g: Gantt) -> int:
    d = g.day or g.now
    slot = int((d - midnight(d)) / WEEK_SLOT)
    now_at = now_in_week(g, monday(d))
    if now_at is not None and slot > now_at[0]:
        slot += 1  # the now line is above it
    return WEEK_HEADER + slot


# The month.


def month(g: Gantt, width: int) -> list[Text]:
    now, cur = g.now, g.day or midnight(g.now)
    first = cur.replace(day=1)
    col_w = max(width // 7 - 1, 6)
    least, most, usable = g.day_free(cur)
    if cur < midnight(now) or cur >= g.end:
        detail = Text(f"{cur:%a %d %b} · not shown: only now to {g.end:%a %d %b} is known", style=PAST)
    else:
        detail = Text(f"{cur:%a %d %b} · {span(least, most)} of {usable} nodes free · "
                      f"{jobs(g.jobs_starting(cur, cur + DAY))} start", style=free_style(least, max(usable, 1)))
    lines = [
        fit(Text(f"{first:%B %Y} · cursor {cur:%a %d %b}", style=MUTED), width),
        fit(detail, width),
        fit(calendar_legend(), width),
        Text(""),
        Text("".join(cell(d, col_w) for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")), style="bold"),
    ]
    w = monday(first)
    while w.month == first.month or w < first:
        top, bottom = Text(), Text()
        for d in range(7):
            t, b = day_cell(g, w + d * DAY, first.month, col_w)
            top += t
            bottom += b
        lines += [fit(top, width), fit(bottom, width)]
        w += 7 * DAY
    return lines


def day_cell(g: Gantt, day: datetime, month_: int, w: int) -> tuple[Text, Text]:
    """A day of the month on two lines: its number and the jobs starting,
    then its free nodes in their colour."""
    now = g.now
    num = f"{day.day:2d}"
    if day.month != month_:
        return Text(cell(num, w), style=PAST), Text(cell("", w))
    if day < midnight(now) or day >= g.end:
        return Text(cell(num, w), style=PAST), Text(cell("·", w), style=PAST)
    least, most, usable = g.day_free(day)
    n = g.jobs_starting(day, day + DAY)
    top = Text(cell(num + (f"  {jobs(n)}" if n else ""), w), style="bold underline" if day == midnight(now) else "")
    style = CURSOR if day == g.day else free_style(least, usable)
    return top, Text(f"{span(least, most)} free"[:w].ljust(w), style=style) + Text(" ")


def month_focus(g: Gantt) -> int:
    d = g.day or midnight(g.now)
    week_i = (monday(d) - monday(d.replace(day=1))).days // 7
    return MONTH_HEADER + 2 * week_i + 1


def span(least: int, most: int) -> str:
    return str(least) if least == most else f"{least}–{most}"

