"""Reservations › Current: a cluster's reservations, as a time line, a week
or a month (widgets/timeline.py).

It shows the cluster chosen in Nodes (enter on a node: with the nodes it
has), in Clusters (g: it loads them), or from My reservations.

    t w m   the time line, the week, the month (v: the next one)
    n       back to the time now
    r       load the nodes again (the zoom and the cursors are kept)
    b       reserve from the cursor: a dialog to choose in (screens/reserve.py)
    x       cancel your job under the cursor (time line), after a yes

The mouse wheel moves as ↑↓ do, and shift+wheel (or a sideways wheel) as ←→.

On the time line:  ↑↓ nodes · ←→ a cell · H L a day · [ ] previous / next job · + - zoom
On the week:       ←→ days · ↑↓ 2-hour slots · [ ] weeks · enter: the time line there
On the month:      ←→ days · ↑↓ weeks · [ ] months · enter: the time line on that day

A clock ticks every CLOCK_EVERY seconds: the now
marks move with the time, with no call to the API.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from textual import events, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Static

from grid_tui.format import clock, duration
from grid_tui.models import Cluster, Gantt, JobRequest, Mode, Node, Site
from grid_tui.models.gantt import DAY, WEEK_SLOT
from grid_tui.api import Api
from grid_tui.screens.reserve import ConfirmDialog, ReserveDialog
from grid_tui.widgets import ReservationsView

CLOCK_EVERY = 30.0  # seconds


def now() -> datetime:
    return datetime.now().astimezone()


class ReservationsPanel(Vertical):
    """The reservations of one cluster."""

    BINDINGS = [
        Binding("t", "view('timeline')", "Timeline"),
        Binding("w", "view('week')", "Week"),
        Binding("m", "view('month')", "Month"),
        Binding("v", "next_view", "Next view", show=False),
        Binding("n", "now", "Now"),
        Binding("b", "reserve", "Reserve"),
        Binding("x", "cancel_job", "Cancel job"),
        Binding("r", "reload", "Reload"),
        Binding("up,k", "vertical(-1)", "Up", show=False),
        Binding("down,j", "vertical(1)", "Down", show=False),
        Binding("left,h", "horizontal(-1)", "Earlier", show=False),
        Binding("right,l", "horizontal(1)", "Later", show=False),
        Binding("H,shift+left", "far(-1)", "A day earlier", show=False),
        Binding("L,shift+right", "far(1)", "A day later", show=False),
        Binding("left_square_bracket", "jump(-1)", "Previous", show=False),
        Binding("right_square_bracket", "jump(1)", "Next", show=False),
        Binding("plus,equals_sign", "zoom(-1)", "Zoom in", show=False),
        Binding("minus", "zoom(1)", "Zoom out", show=False),
        Binding("enter", "open", "Open", show=False),
    ]

    DEFAULT_CSS = """
    ReservationsPanel ReservationsView {
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
        padding: 0 1;
    }
    ReservationsPanel ReservationsView:focus { border: round $accent-lighten-1; }
    ReservationsPanel .status { height: 1; padding: 0 1; color: $text-muted; }
    ReservationsPanel .status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self.site: Site | None = None
        self.cluster: Cluster | None = None
        self.gantt: Gantt | None = None

    def compose(self) -> ComposeResult:
        yield ReservationsView(None)
        yield Static("", classes="status", markup=False)

    def show_cluster(self, site: Site, cluster: Cluster, nodes: list[Node] | None = None, node: int = 0) -> None:
        """Show cluster's reservations: with the nodes given, or loading them."""
        same = (self.site, self.cluster) == (site, cluster)
        self.site, self.cluster = site, cluster
        self.view.border_subtitle = "$ " + self.api.command(f"/sites/{site.uid}/clusters/{cluster.uid}/status")
        if nodes is not None:
            old = self.gantt if same else None
            self.gantt = Gantt(nodes, now(), node=node, clock=now())
            if old is not None:  # the same cluster again: keep the view and the zoom
                self.gantt.mode, self.gantt.zoom = old.mode, old.zoom
            self.redraw()
        elif not same or self.gantt is None:
            self.gantt = None
            self.redraw()
            self.load()

    @property
    def view(self) -> ReservationsView:
        return self.query_one(ReservationsView)

    def on_mount(self) -> None:
        self.redraw()
        self.set_status("choose a node in Nodes (3), or g on a cluster in Clusters (2)")
        self.set_interval(CLOCK_EVERY, self.tick)

    def tick(self) -> None:
        """The clock: the now marks move; nothing is loaded."""
        if self.gantt is not None:
            self.gantt.clock = now()
            self.redraw()

    # Loading.

    def action_reload(self) -> None:
        if self.cluster is not None:
            self.load()

    @work(exclusive=True)
    async def load(self) -> None:
        """Load the nodes, keeping the view, the zoom and the cursors."""
        assert self.site is not None and self.cluster is not None
        self.set_status("loading…")
        self.view.loading = True
        try:
            nodes = await self.api.nodes(self.site.uid, self.cluster.uid)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            return
        finally:
            self.view.loading = False
        old = self.gantt
        g = Gantt(nodes, now())
        if old is not None:
            g.mode, g.zoom, g.col, g.day = old.mode, old.zoom, old.col, old.day
            g.node = min(old.node, max(len(nodes) - 1, 0))
            g.move_time(0)
        self.gantt = g
        self.redraw()
        self.set_status("")

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one(".status", Static)
        status.update(text)
        status.set_class(error, "error")

    def redraw(self) -> None:
        g = self.gantt
        if self.site is None or self.cluster is None:
            self.view.border_title = "reservations"
            self.view.show(None)
            return
        title = f"site: {self.site.uid} · cluster: {self.cluster.uid} · reservations"
        if g is not None:
            title += f": {g.mode.value}"
            if g.mode is Mode.TIMELINE:
                title += f" · zoom {duration(g.cell)}"
        self.view.border_title = title
        self.view.show(g)

    # The mouse wheel: up and down like ↑↓, sideways (or with shift) like ←→.

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.action_horizontal(1) if event.shift else self.action_vertical(1)
        event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.action_horizontal(-1) if event.shift else self.action_vertical(-1)
        event.stop()

    def on_mouse_scroll_right(self, event: events.MouseScrollRight) -> None:
        self.action_horizontal(1)
        event.stop()

    def on_mouse_scroll_left(self, event: events.MouseScrollLeft) -> None:
        self.action_horizontal(-1)
        event.stop()

    # Keys. Each one does what fits the view on screen.

    def change(self, f) -> None:
        if self.gantt is not None:
            f(self.gantt)
            self.redraw()

    def action_view(self, name: str) -> None:
        self.change(lambda g: g.set_mode(Mode(name)))

    def action_next_view(self) -> None:
        modes = list(Mode)
        self.change(lambda g: g.set_mode(modes[(modes.index(g.mode) + 1) % len(modes)]))

    def action_now(self) -> None:
        self.change(lambda g: g.to_now())

    def action_vertical(self, step: int) -> None:
        def f(g: Gantt) -> None:
            if g.mode is Mode.WEEK:
                g.move_day(slots=step)
            elif g.mode is Mode.MONTH:
                g.move_day(days=7 * step)
            else:
                g.move_node(step)
        self.change(f)

    def action_horizontal(self, step: int) -> None:
        def f(g: Gantt) -> None:
            if g.mode is Mode.TIMELINE:
                g.move_time(step)
            else:
                g.move_day(days=step)
        self.change(f)

    def action_far(self, step: int) -> None:
        """A day on the time line; a week elsewhere."""
        def f(g: Gantt) -> None:
            if g.mode is Mode.TIMELINE:
                g.move_time(step * int(DAY / g.cell))
            else:
                g.move_day(days=7 * step)
        self.change(f)

    def action_jump(self, step: int) -> None:
        """The previous / next job on the time line; a week or a month elsewhere."""
        def f(g: Gantt) -> None:
            if g.mode is Mode.TIMELINE:
                g.jump_job(step)
            elif g.mode is Mode.WEEK:
                g.move_day(days=7 * step)
            else:
                g.move_day(days=30 * step)
        self.change(f)

    def action_zoom(self, step: int) -> None:
        self.change(lambda g: g.zoom_by(step) if g.mode is Mode.TIMELINE else None)

    def action_open(self) -> None:
        """On the week or the month: the time line at the cursor, zoomed in."""
        def f(g: Gantt) -> None:
            if g.mode is Mode.WEEK:
                g.zoom_to(1)  # 30 minutes: a slot is 4 cells
            elif g.mode is Mode.MONTH:
                g.zoom_to(2)  # 1 hour: the day fills the screen
            else:
                return
            g.set_mode(Mode.TIMELINE)
        self.change(f)

    # Reserving and cancelling.

    def action_reserve(self) -> None:
        """b: a dialog to reserve from the cursor's time (a week slot lasts 2h)."""
        g = self.gantt
        if g is None or self.site is None or self.cluster is None:
            return
        start = g.cursor_time if g.mode is Mode.TIMELINE else (g.day or g.now)
        hours = int(WEEK_SLOT / timedelta(hours=1)) if g.mode is Mode.WEEK else 1
        dialog = ReserveDialog(g, self.site.uid, self.cluster.uid, self.cluster.queues, start, hours,
                               command=self.api.submit_command)
        self.app.push_screen(dialog, self.reserve_chosen)

    def reserve_chosen(self, request: JobRequest | None) -> None:
        if request is not None:
            self.submit(request)

    @work(exclusive=True, group="jobs")
    async def submit(self, request: JobRequest) -> None:
        """Send the reservation, then load the nodes again to show it."""
        self.set_status("sending the reservation…")
        try:
            job_id = await self.api.submit_job(request)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            self.notify(str(e), title="Not reserved", severity="error", timeout=10)
            return
        self.notify(f"job #{job_id}: {request.summary()}", title="Reserved")
        self.set_status("")
        self.load()

    def action_cancel_job(self) -> None:
        """x: cancel the job under the cursor, if it is yours, after a yes."""
        g = self.gantt
        if g is None:
            return
        if g.mode is not Mode.TIMELINE:
            self.notify("put the time line's cursor on the job (t)", severity="warning")
            return
        job = g.selected_job()
        if job is None:
            self.notify("no job under the cursor", severity="warning")
            return
        if job.user != self.api.login():
            self.notify(f"job #{job.job_id} is {job.user or 'someone else'}'s: only yours can be cancelled", severity="warning")
            return
        question = (f"Cancel job #{job.job_id} ({job.user}, {clock(job.start, g.now)}→{clock(job.end, g.now)}"
                    f" on {g.job_nodes(job.job_id)} node(s))?")
        self.app.push_screen(ConfirmDialog(question), lambda yes: self.cancel(job.job_id) if yes else None)

    @work(exclusive=True, group="jobs")
    async def cancel(self, job_id: int) -> None:
        assert self.site is not None
        self.set_status(f"cancelling job #{job_id}…")
        try:
            await self.api.cancel_job(self.site.uid, job_id)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            self.notify(str(e), title="Not cancelled", severity="error", timeout=10)
            return
        self.notify(f"job #{job_id}", title="Cancelled")
        self.set_status("")
        self.load()
