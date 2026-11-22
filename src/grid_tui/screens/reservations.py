"""A cluster's reservations: a time line, a week or a month (widgets/timeline.py).

Opened from a cluster's detail (enter on a node, or g: with the nodes it
has) or from the clusters (g: it loads them). esc goes back.

    t w m   the time line, the week, the month (v: the next one)
    n       back to the time now
    r       load the nodes again (the zoom and the cursors are kept)

On the time line:  ↑↓ nodes · ←→ a cell · H L a day · [ ] previous / next job · + - zoom
On the week:       ←→ days · ↑↓ 2-hour slots · [ ] weeks · enter: the time line there
On the month:      ←→ days · ↑↓ weeks · [ ] months · enter: the time line on that day

A clock ticks every CLOCK_EVERY seconds while the screen is open: the now
marks move with the time, with no call to the API.
"""

from __future__ import annotations

from datetime import datetime

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from grid_tui.format import duration
from grid_tui.models import Cluster, Gantt, Mode, Node, Site
from grid_tui.models.gantt import DAY
from grid_tui.screens.base import Api
from grid_tui.widgets import ReservationsView

CLOCK_EVERY = 30.0  # seconds


def now() -> datetime:
    return datetime.now().astimezone()


class ReservationsScreen(Screen):
    """The reservations of one cluster."""

    BINDINGS = [
        Binding("escape,backspace", "app.pop_screen", "Back"),
        Binding("t", "view('timeline')", "Timeline"),
        Binding("w", "view('week')", "Week"),
        Binding("m", "view('month')", "Month"),
        Binding("v", "next_view", "Next view", show=False),
        Binding("n", "now", "Now"),
        Binding("r", "reload", "Reload"),
        Binding("q", "app.quit", "Quit"),
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
    ReservationsScreen ReservationsView {
        border: round $accent;
        border-title-color: $text;
        border-subtitle-color: $text-muted;
        padding: 0 1;
    }
    ReservationsScreen #status { height: 1; padding: 0 1; color: $text-muted; }
    ReservationsScreen #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, site: Site, cluster: Cluster, nodes: list[Node] | None = None, node: int = 0) -> None:
        super().__init__()
        self.api, self.site, self.cluster = api, site, cluster
        self.gantt: Gantt | None = Gantt(nodes, now(), node=node) if nodes is not None else None

    def compose(self) -> ComposeResult:
        yield Header()
        view = ReservationsView(self.gantt)
        view.border_subtitle = "$ " + self.api.command(f"/sites/{self.site.uid}/clusters/{self.cluster.uid}/status")
        yield view
        yield Static("", id="status", markup=False)
        yield Footer()

    @property
    def view(self) -> ReservationsView:
        return self.query_one(ReservationsView)

    def on_mount(self) -> None:
        self.redraw()
        if self.gantt is None:
            self.load()
        self.set_interval(CLOCK_EVERY, self.tick)

    def tick(self) -> None:
        """The clock: the now marks move; nothing is loaded."""
        if self.gantt is not None:
            self.gantt.clock = now()
            self.redraw()

    # Loading.

    def action_reload(self) -> None:
        self.load()

    @work(exclusive=True)
    async def load(self) -> None:
        """Load the nodes, keeping the view, the zoom and the cursors."""
        self.set_status("loading…")
        try:
            nodes = await self.api.nodes(self.site.uid, self.cluster.uid)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            return
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
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")

    def redraw(self) -> None:
        g = self.gantt
        title = f"site: {self.site.uid} · cluster: {self.cluster.uid} · reservations"
        if g is not None:
            title += f": {g.mode.value}"
            if g.mode is Mode.TIMELINE:
                title += f" · zoom {duration(g.cell)}"
        self.view.border_title = title
        self.view.show(g)

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
