"""The Reservations panel: a cluster's reservations, now and to come, on a timeline.

Three cards, like the Search tab:

    ╭ Reservations ────────────────────────────────────────────────────────╮
    │ Site [nancy ▼]  Cluster [gros ▼]   Find a slot: [ 8] nodes [ 2] h   │
    │ 3/123 free now · 120 running  ·  slot: Fri 01:00 (night, free use)   │
    ╰──────────────────────────────────────────────────────────────────────╯
    ╭ Timeline ─────────────────────────────── Thu 21:00 → Fri 21:00 ──────╮
    │                  Thu 26        Fri 27                                │
    │                  21    00    03    06    09    12    15    18        │
    │                  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀ (lighter: daytime) │
    │ gros-1…4    (4)  ███ #7081934 alice ███│███████                     │
    │ 3/123 free       ▂▂▂▂▁▁▁▁▁▁▂▂▂▂▂▂▇▇▃▃▃▃▃▃▃▃▃▃▁▁▁                     │
    │ slot             ┣━━━━━┫                                             │
    ╰──────────────────────────────────────────────────────────────────────╯
    ╭ Details ─────────────────────────────────────────────────────────────╮
    │ █ #7081934 alice · default · running · Thu 18:00 → Fri 04:00 · 4 nodes│
    ╰──────────────────────────────────────────────────────────────────────╯

Nodes with the same reservations share a row. d shows a day (the standard
view), w a week, m a month; z zooms through them all (12 h to a month).
[ and ] move earlier and later, n comes back to now, on the day view.

Changing the view only redraws: it uses the schedule already loaded (an answer
is remembered for a minute), so it asks the API nothing. The cluster can be
picked here, or by choosing one in the Clusters or Search tab.

Reservations change all the time: they are never cached, and are asked for
again every minute while the tab shows.
"""

from __future__ import annotations

import time as clock
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Input, Label, Select, Static

from grid_tui.format import duration
from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Reservation, Schedule
from grid_tui.policy import PARIS, period_at
from grid_tui.widgets.panels.reservations.timeline import (
    ADMIN,
    MINE,
    MUTED,
    NOW,
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
    with_now,
)

HINT = 'Choose a site and a cluster to see its reservations.'
# the Timeline card's title: what the colours mean
LEGEND = (
    'Timeline   [#a6e3a1]█[/] yours  [#f38ba8]█[/] maintenance'
    '  [#6c7086]░ best-effort[/]  [#45475a]▀[/] daytime quota  [#ff4d5e]┃[/] now'
)
DAY, WEEK, MONTH = 24, 7 * 24, 30 * 24  # the views' hours on screen: d, w, m
ZOOMS = (12, DAY, 72, WEEK, MONTH)  # hours on screen: z goes to the next
LABEL_WIDTH = 16  # the node column
LEFT = LABEL_WIDTH + 3  # where the timeline starts: the column and its padding
REFRESH_SECONDS = 120  # reload this often, while the tab shows and the app has focus
TICK_SECONDS = 30  # redraw this often (the now line moves); costs no request
MAX_DETAILS = 3  # reservations listed in the Details card


def when(moment: float) -> str:
    """A time for a person: 'Thu 18:00'."""
    return datetime.fromtimestamp(moment, PARIS).strftime('%a %H:%M')


def describe(reservation: Reservation, me: str = '') -> Text:
    """One reservation on one line, in its colour."""
    colour = colour_of(reservation, me)
    nodes = len(reservation.nodes)
    text = Text('█ ', colour)
    text.append(label_of(reservation, me), f'bold {colour}')
    text.append(
        f' · {reservation.queue or "default"} · {reservation.state}'
        f' · {when(reservation.start)} → {when(reservation.end)}'
        f' ({duration(reservation.end - reservation.start)})'
        f' · {nodes} node{"s" if nodes != 1 else ""}',
        MUTED,
    )
    return text


def view_name(hours: int) -> str:
    """What the view is called: 'Day', 'Week', 'Month', or its length."""
    names = {DAY: 'Day', WEEK: 'Week', MONTH: 'Month'}
    if hours in names:
        return names[hours]
    return f'{hours} h' if hours < 48 else f'{hours // 24} days'


def read_number(text: str) -> float:
    """A box's number; 0 if it's empty or not a number."""
    try:
        return max(float(text.strip()), 0.0)
    except ValueError:
        return 0.0


class ReservationsPanel(Widget):
    """A cluster's reservations on a timeline, its free nodes, and free slots."""

    DEFAULT_CSS = (Path(__file__).parent / 'reservations.tcss').read_text()
    BINDINGS = [
        Binding('z', 'zoom(1)', 'Zoom out'),
        Binding('Z', 'zoom(-1)', 'Zoom in', show=False),
        Binding('left_square_bracket', 'pan(-1)', 'Earlier'),
        Binding('right_square_bracket', 'pan(1)', 'Later'),
        Binding('n', 'now', 'Now'),
        Binding('d', 'view(24)', 'Day'),
        Binding('w', 'view(168)', 'Week'),
        Binding('m', 'view(720)', 'Month'),
    ]

    def __init__(
        self,
        client: Client,
        site: str | None = None,
        cluster: str | None = None,
        *,
        now: Callable[[], float] | None = None,
        **kwargs: Any,
    ) -> None:
        """Make the panel.

        Args:
            client: Where to load the sites, clusters and reservations from.
            site: The cluster's site, e.g. 'nancy'; None until one is chosen.
            cluster: The cluster, e.g. 'gros'.
            now: What gives the time now, in seconds; tests pass a fixed one.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.site = site
        self.cluster = cluster
        self.now = now or clock.time
        self.hours = 24
        self.shift = 0.0  # how far the window is moved from now, in seconds
        self.schedule: Schedule | None = None
        self.rows: list[Row] = []
        self.slot: tuple[float, list[str]] | None = None  # (start, free nodes)
        self._sites: set[str] = set()  # the sites the site list has
        self._loaded_at = 0.0  # when the reservations were last loaded

    # ---- the cards --------------------------------------------------------

    def compose(self) -> ComposeResult:
        """The controls card, the timeline card, the details card."""
        with Vertical(id='res-card') as card:
            card.border_title = 'Reservations'
            with Grid(id='res-form'):
                yield Label('Site', classes='form-label')
                yield Select(
                    [], prompt='Site', allow_blank=True, compact=True, id='res-site'
                )
                yield Label('Cluster', classes='form-label')
                yield Select(
                    [],
                    prompt='Cluster',
                    allow_blank=True,
                    compact=True,
                    id='res-cluster',
                )
                yield Label('Slot', classes='form-label')
                with Horizontal(classes='with-unit'):
                    yield Input(
                        placeholder='nodes',
                        type='integer',
                        compact=True,
                        id='slot-nodes',
                    )
                    yield Label('nodes ×', classes='unit')
                    yield Input(
                        placeholder='hours',
                        type='number',
                        compact=True,
                        id='slot-hours',
                    )
                    yield Label('h', classes='unit')
            with Horizontal(id='res-toolbar'):
                yield Label(HINT, id='res-title')
                yield Label('', id='res-zoom')
            yield Static('', id='res-summary')
        with Vertical(id='timeline-card') as card:
            card.border_title = LEGEND
            yield Static('', id='res-axis')
            yield DataTable(
                cursor_type='row',
                show_header=False,
                # the bars keep their colours under the cursor: it shows on the name
                cursor_foreground_priority='renderable',
                cursor_background_priority='renderable',
                id='res-table',
            )
            yield Static('', id='res-free')
            yield Static('', id='res-slot')
        with Vertical(id='details-card') as card:
            card.border_title = 'Details'
            yield Static('', id='res-details')

    def on_mount(self) -> None:
        """Add the columns, fill the site list, load, and keep it fresh."""
        table = self.query_one(DataTable)
        table.add_column('Nodes', width=LABEL_WIDTH, key='nodes')
        table.add_column('Timeline', key='timeline')
        self.load_sites()
        self.load()
        self.set_interval(TICK_SECONDS, self._tick)

    def _tick(self) -> None:
        """Every 30 s: move the now line; reload only if the data is old.

        Nothing is asked while the tab is hidden or the app is in the
        background (see Grid5KApp.polling).
        """
        if not (self.is_on_screen and self.site and self.cluster):
            return
        stale = clock.monotonic() - self._loaded_at >= REFRESH_SECONDS
        if stale and getattr(self.app, 'polling', True):
            self.load()
        else:
            self.draw()

    # ---- choosing the cluster -----------------------------------------------

    @work(group='res-sites')
    async def load_sites(self) -> None:
        """Fill the site list (from the cache once it's saved)."""
        try:
            sites = await self.client.sites.list()
        except (ApiError, httpx.HTTPError):
            return  # the timeline says what went wrong when it loads
        select = self.query_one('#res-site', Select)
        self._sites = {site.uid for site in sites}
        with select.prevent(Select.Changed):
            select.set_options((site.name or site.uid, site.uid) for site in sites)
            if self.site in self._sites:
                select.value = self.site
        if self.site:
            self.load_clusters(self.site)

    @work(exclusive=True, group='res-clusters')
    async def load_clusters(self, site: str) -> None:
        """Fill the cluster list with a site's clusters."""
        try:
            clusters = await self.client.sites.list_clusters(site)
        except (ApiError, httpx.HTTPError):
            return
        select = self.query_one('#res-cluster', Select)
        uids = [cluster.uid for cluster in clusters]
        with select.prevent(Select.Changed):
            select.set_options((uid, uid) for uid in uids)
            if site == self.site and self.cluster in uids:
                select.value = self.cluster

    @on(Select.Changed, '#res-site')
    def _site_picked(self, event: Select.Changed) -> None:
        """A site was picked: list its clusters (the timeline waits for one)."""
        site = event.select.selection
        if site and site != self.site:
            self.site, self.cluster = site, None
            self.schedule = None
            self.load_clusters(site)
            self.draw()

    @on(Select.Changed, '#res-cluster')
    def _cluster_picked(self, event: Select.Changed) -> None:
        """A cluster was picked: show its reservations."""
        cluster = event.select.selection
        if self.site and cluster and cluster != self.cluster:
            self.cluster = cluster
            self.schedule = None
            self.load()

    def show_cluster(self, site: str, cluster: str) -> None:
        """Switch to a cluster's reservations (e.g. chosen in another tab).

        Args:
            site: The cluster's site, e.g. 'nancy'.
            cluster: The cluster, e.g. 'gros'.
        """
        if (site, cluster) == (self.site, self.cluster):
            return
        self.site, self.cluster = site, cluster
        self.schedule = None
        sites = self.query_one('#res-site', Select)
        with sites.prevent(Select.Changed):
            if site in self._sites:
                sites.value = site
        self.load_clusters(site)
        self.load()

    # ---- loading ------------------------------------------------------------

    @work(exclusive=True)  # runs in the background; a new load cancels the old one
    async def load(self, refresh: bool = False) -> None:
        """Fetch the cluster's reservations and draw them.

        Args:
            refresh: Ask the API even if it was asked within a minute (r).
        """
        if not (self.site and self.cluster):
            self.draw()
            return
        site, cluster = self.site, self.cluster
        self.loading = self.schedule is None  # a spinner only the first time
        try:
            schedule = await self.client.status.schedule(site, cluster, refresh=refresh)
        except (ApiError, httpx.HTTPError) as error:
            self.notify(
                str(error), title="Couldn't load reservations", severity='error'
            )
            return
        finally:
            self.loading = False
        if (site, cluster) == (self.site, self.cluster):  # still this cluster
            self._loaded_at = clock.monotonic()
            self.schedule = schedule
            self._find_slot()
            self.draw()

    # ---- the slot finder ----------------------------------------------------

    @on(Input.Changed, '#slot-nodes')
    @on(Input.Changed, '#slot-hours')
    def _slot_changed(self) -> None:
        """Nodes or hours changed: look for the first slot again."""
        self._find_slot()
        self.draw()

    def slot_request(self) -> tuple[int, float]:
        """What the slot boxes ask for: (nodes, seconds); zeros if not set."""
        nodes = int(read_number(self.query_one('#slot-nodes', Input).value))
        hours = read_number(self.query_one('#slot-hours', Input).value)
        return nodes, hours * 3600

    def _find_slot(self) -> None:
        """The first slot that fits the request, from now on."""
        nodes, seconds = self.slot_request()
        if self.schedule is None or not nodes or not seconds:
            self.slot = None
            return
        self.slot = self.schedule.find_slot(nodes, seconds, self.now())

    # ---- moving through time ------------------------------------------------

    def action_view(self, hours: int) -> None:
        """Show a day (d), a week (w) or a month (m), from around now.

        Only redraws, from the schedule already loaded: nothing is asked.
        """
        self.hours = hours
        self.shift = 0.0
        self.draw()

    def action_zoom(self, step: int) -> None:
        """Show more (z) or less (Z) time: 12 h, 24 h, 3 days, a week, a month."""
        index = ZOOMS.index(self.hours) if self.hours in ZOOMS else 1
        self.hours = ZOOMS[(index + step) % len(ZOOMS)]
        self.draw()

    def action_pan(self, step: int) -> None:
        """Move a quarter of the window earlier ([) or later (])."""
        self.shift += step * self.hours * 3600 / 4
        self.draw()

    def action_now(self) -> None:
        """Come back to now, on the standard day view (n)."""
        self.hours = DAY
        self.shift = 0.0
        self.draw()

    def on_resize(self) -> None:
        """The panel changed size: draw the timeline to fit."""
        self.draw()

    # ---- drawing ------------------------------------------------------------

    @property
    def me(self) -> str:
        """Your login, so your reservations show green."""
        return self.client.sites.user

    def window(self) -> Window:
        """The time on screen: around now, moved by [ and ]."""
        window = Window.around(self.now(), self.hours)
        return Window(window.start + self.shift, window.end + self.shift)

    def timeline_width(self) -> int:
        """How many columns the timeline has: what the table leaves after names."""
        table_width = self.query_one(DataTable).size.width or self.size.width
        return max(table_width - LEFT - 2, 20)  # 2: the padding and scrollbar

    def draw(self) -> None:
        """Draw everything from the schedule, the window and the panel's width."""
        title = self.query_one('#res-title', Label)
        zoom = self.query_one('#res-zoom', Label)
        table = self.query_one(DataTable)
        timeline_card = self.query_one('#timeline-card')
        if not (self.site and self.cluster):
            title.update(HINT)
            title.remove_class('-chosen')
            zoom.update('')
            for widget in ('#res-axis', '#res-free', '#res-slot', '#res-details'):
                self.query_one(widget, Static).update('')
            self.query_one('#res-summary', Static).update('')
            timeline_card.border_subtitle = ''
            table.clear()
            return
        title.update(f'{self.site} / {self.cluster}')
        title.add_class('-chosen')
        zoom.update(
            Text.assemble(
                (view_name(self.hours), 'bold'),
                ('   d day · w week · m month · z zoom · [ ] move · n now', MUTED),
            )
        )
        if self.schedule is None:
            return
        now = self.now()
        window = self.window()
        width = self.timeline_width()
        pad = ' ' * LEFT
        timeline_card.border_subtitle = f'{when(window.start)} → {when(window.end)}'

        days, hours = axis_lines(window, width)
        band = with_now(policy_band(window, width), window, width, now)
        axis = Text()
        for line in (now_label(window, width, now), days, hours, band):
            axis.append(pad)
            axis.append_text(line)
            axis.append('\n')
        axis.rstrip()
        self.query_one('#res-axis', Static).update(axis)

        cursor = table.cursor_row
        table.clear()
        timeline = table.columns['timeline']
        timeline.width = width
        timeline.auto_width = False
        self.rows = group_rows(self.schedule)
        for index, row in enumerate(self.rows):
            count = f' ({len(row.nodes)})' if len(row.nodes) > 1 else ''
            name = row.label[: LABEL_WIDTH - len(count)]
            label = Text(name, 'bold' if row.is_up else MUTED)
            label.append(count, MUTED)
            table.add_row(
                label, bar_line(row, window, width, self.me, now), key=str(index)
            )
        if self.rows:
            table.move_cursor(row=min(cursor, len(self.rows) - 1))

        free_now = f'{self.schedule.free_at(now)}/{self.schedule.up} free'
        free = Text(' ' + free_now.ljust(LEFT - 1), f'bold {MINE}')
        strip = free_strip(self.schedule, window, width)
        free.append_text(with_now(strip, window, width, now))
        self.query_one('#res-free', Static).update(free)
        self._draw_slot(window, width, now)
        self._draw_summary(now)
        self._show_details()

    def _draw_slot(self, window: Window, width: int, now: float) -> None:
        """Mark the slot found under the free nodes, if there is one."""
        nodes, seconds = self.slot_request()
        if self.slot is not None:
            start = self.slot[0]
            marks = slot_line(window, width, start, start + seconds)
            line = Text(' slot'.ljust(LEFT), f'bold {MINE}')
        else:
            marks = Text(' ' * width)
            line = Text(' ' * LEFT)
        line.append_text(with_now(marks, window, width, now, over_marks=False))
        self.query_one('#res-slot', Static).update(line)

    def _draw_summary(self, now: float) -> None:
        """The line under the controls: free now, running, and the slot."""
        assert self.schedule is not None
        running = {
            node
            for reservation in self.schedule.reservations
            if reservation.covers(now)
            for node in reservation.nodes
        }
        down = len(self.schedule.nodes) - self.schedule.up
        text = Text.assemble(
            (f'{self.schedule.free_at(now)}', f'bold {MINE}'),
            (f'/{self.schedule.up} free', MUTED),
            (' · ', MUTED),
            (f'{len(running)}', 'bold'),
            (' busy', MUTED),
        )
        if down:
            text.append(f' · {down} down', MUTED)
        nodes, seconds = self.slot_request()
        text.append('    ')
        if not nodes or not seconds:
            text.append('Slot: set nodes and hours to find one', MUTED)
        elif self.slot is None:
            text.append(f'No slot: fewer than {nodes} nodes are up', f'bold {ADMIN}')
        else:
            start = datetime.fromtimestamp(self.slot[0], PARIS)
            period = period_at(start)
            label = 'now' if self.slot[0] <= now else when(self.slot[0])
            text.append('Slot ', MUTED)
            text.append(label, f'bold {MINE}')
            text.append(f' · {nodes} × {duration(int(seconds))} · ', MUTED)
            quota = period.name == 'Day'
            text.append(
                f'{period.name.lower()}: {period.rule}',
                f'bold {NOW}' if quota else MUTED,
            )
        self.query_one('#res-summary', Static).update(text)

    @on(DataTable.RowHighlighted)
    def _show_details(self) -> None:
        """In the Details card: the highlighted row's reservations, in full."""
        details = self.query_one('#res-details', Static)
        table = self.query_one(DataTable)
        if not self.rows or not table.row_count:
            details.update('')
            return
        row = self.rows[min(table.cursor_row, len(self.rows) - 1)]
        now = self.now()
        coming = [r for r in row.reservations if r.end > now]
        if not row.is_up:
            details.update(Text(f'{row.label}: {row.state}, can’t run jobs', MUTED))
            return
        if not coming:
            details.update(Text(f'{row.label}: free, nothing reserved', MINE))
            return
        lines = Text()
        for reservation in coming[:MAX_DETAILS]:
            lines.append_text(describe(reservation, self.me))
            lines.append('\n')
        if len(coming) > MAX_DETAILS:
            lines.append(f'… and {len(coming) - MAX_DETAILS} more', MUTED)
        lines.rstrip()
        details.update(lines)
