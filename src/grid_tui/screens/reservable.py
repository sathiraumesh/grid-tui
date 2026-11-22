"""Reservable: for a date, a time and a duration, which clusters can take
how many nodes, all through.

    ╭─ when ───────────────────╮╭─ reservable: 3 of 12 · Sun 22 Nov 18:00 → 20:00 ─────────╮
    │ Date      [Sun 22 Nov ▾] ││ SITE    CLUSTER    FREE ALL THROUGH   RESERVABLE          │
    │ Time      [18:00      ▾] ││ nancy   gros       37 of 124          yes                 │
    │ Duration  [2h         ▾] ││ rennes  paravance   2 of 72           no: only 2 free     │
    │ Nodes     [ 4 ]          ││                                                           │
    │ Site      [any        ▾] ││                                                           │
    │ [x] Only reservable      ││                                                           │
    ╰──────────────────────────╯╰───────────────────────────────────────────────────────────╯

a on the sites opens it. Every site's nodes load in one call per site
(GET /sites/{site}/status), with its clusters (for their queues); each fills
in the results when it arrives. When a site's status fails, its clusters'
status is asked one by one instead (GET …/clusters/{cluster}/status). The screen is kept for the next a; ctrl+r
loads again. enter on a reservable cluster opens the reservation dialog,
filled with that window and that many nodes.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Checkbox, DataTable, Footer, Header, Input, Label, Select, Static

from grid_tui.format import duration
from grid_tui.models import Availability, Gantt, JobRequest, Node, Site
from grid_tui.models.gantt import SPAN
from grid_tui.models.reservable import availability, by_cluster, rank
from grid_tui.screens.base import Api
from grid_tui.screens.reserve import DURATIONS, ReserveDialog

HALF_HOUR = timedelta(minutes=30)
COLUMNS = ("SITE", "CLUSTER", "FREE ALL THROUGH", "RESERVABLE")


def now() -> datetime:
    return datetime.now().astimezone()


def next_half_hour(t: datetime) -> datetime:
    """The next :00 or :30 after t."""
    hour = t.replace(minute=0, second=0, microsecond=0)
    return hour + (t.minute // 30 + 1) * HALF_HOUR


class ReservableScreen(Screen):
    """Which clusters can take a reservation for a chosen window."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "reload", "Reload"),  # r is a letter: the nodes field takes it
    ]

    DEFAULT_CSS = """
    ReservableScreen #when {
        width: 34; border: round $accent; border-title-color: $text; padding: 0 1;
    }
    ReservableScreen #when Label { margin-top: 1; color: $text-muted; }
    ReservableScreen #when Checkbox { margin-top: 1; }
    ReservableScreen #results {
        width: 1fr; border: round $accent;
        border-title-color: $text; border-subtitle-color: $text-muted;
    }
    ReservableScreen #status { height: 1; padding: 0 1; color: $text-muted; }
    ReservableScreen #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, sites: list[Site] | None = None) -> None:
        super().__init__()
        self.api = api
        self.sites = sites  # None: load them first
        self.nodes: dict[str, dict[str, list[Node]]] = {}  # site → cluster → nodes
        self.queues: dict[tuple[str, str], tuple[str, ...]] = {}  # (site, cluster) → queues
        self.loaded_at = now()
        self.sites_total = self.sites_done = 0
        self.found: list[Availability] = []  # what the table shows
        self.site_choices: list[str] = []  # what the Site choice offers now
        self.past = False  # the window chosen has passed

    # The screen.

    def compose(self) -> ComposeResult:
        start = now()
        next_half = next_half_hour(start)
        yield Header()
        with Horizontal():
            with VerticalScroll(id="when") as when:
                when.border_title = "when"
                yield Label("Date")
                days = [start.date() + timedelta(days=i) for i in range(SPAN.days)]
                yield Select([(f"{d:%a %d %b}", d) for d in days], value=next_half.date() if next_half.date() in days
                             else days[0], allow_blank=False, id="date")
                yield Label("Time")
                times = [time(h, m) for h in range(24) for m in (0, 30)]
                yield Select([(f"{t:%H:%M}", t) for t in times], value=next_half.time(), allow_blank=False, id="time")
                yield Label("Duration")
                yield Select([(duration(d), d) for d in DURATIONS], value=DURATIONS[2], allow_blank=False, id="duration")
                yield Label("Nodes")
                yield Input("1", type="integer", id="nodes")
                yield Label("Site")
                yield Select([], prompt="any", id="site")
                yield Checkbox("Only reservable", value=True, id="only")
            table: DataTable = DataTable(id="results", cursor_type="row", zebra_stripes=True)
            table.border_subtitle = "$ " + self.api.command("/sites/{site}/status") + ", every site"
            yield table
        yield Static("", id="status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).add_columns(*COLUMNS)
        self.refresh_results()
        self.load()

    def action_reload(self) -> None:
        self.load()

    # Loading every site.

    @work(exclusive=True)
    async def load(self) -> None:
        self.set_status("loading the sites…")
        try:
            sites = self.sites if self.sites else await self.api.sites()
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            return
        self.sites_total, self.sites_done = len(sites), 0
        errors = []
        for done in asyncio.as_completed([self.load_site(s.uid) for s in sites]):
            site, error = await done
            if error:
                errors.append(f"{site}: {error}")
            self.sites_done += 1
            self.refresh_sites()
            self.refresh_results()
        self.loaded_at = now()
        if errors:
            self.set_status("not everything loaded: " + "; ".join(errors), error=True)
        else:
            self.set_status("")

    async def load_site(self, site: str) -> tuple[str, str]:
        """A site's nodes (one call) and its clusters' queues, at the same time.

        If the site's status fails (the API sometimes crashes on one site),
        each of its clusters' status is asked instead: the clusters that
        answer still show, and only those that fail are said.
        """
        nodes, clusters = await asyncio.gather(self.api.site_nodes(site), self.api.clusters(site),
                                               return_exceptions=True)
        if not isinstance(clusters, BaseException):
            for c in clusters:
                self.queues[(site, c.uid)] = c.queues
        if not isinstance(nodes, BaseException):
            self.nodes[site] = by_cluster(nodes)
            return site, ""
        if isinstance(clusters, BaseException):
            return site, str(nodes)  # nothing to fall back on

        # One call per cluster instead.
        answers = await asyncio.gather(*(self.api.nodes(site, c.uid) for c in clusters), return_exceptions=True)
        found: dict[str, list[Node]] = {}
        failed = []
        for c, answer in zip(clusters, answers):
            if isinstance(answer, BaseException):
                failed.append(c.uid)
            else:
                found[c.uid] = answer
        if not found:
            return site, str(nodes)
        self.nodes[site] = found
        if failed:
            return site, f"{', '.join(failed)} didn't answer (the site's status failed: {nodes})"
        return site, ""

    # The form.

    def window(self) -> tuple[datetime, datetime, int]:
        """The window chosen, and the nodes wanted."""
        day: date = self.query_one("#date", Select).value
        at: time = self.query_one("#time", Select).value
        start = datetime.combine(day, at).astimezone()
        end = start + self.query_one("#duration", Select).value
        text = self.query_one("#nodes", Input).value.strip()
        wanted = int(text) if text.isdigit() and int(text) > 0 else 1
        return start, end, wanted

    @on(Select.Changed)
    @on(Input.Changed)
    @on(Checkbox.Changed)
    def changed(self) -> None:
        self.refresh_results()

    def refresh_sites(self) -> None:
        select = self.query_one("#site", Select)
        current = None if select.is_blank() else select.value
        sites = sorted(self.nodes)
        if self.site_choices == sites:
            return  # the same: leave the Select alone
        self.site_choices = sites
        select.set_options([(s, s) for s in sites])
        if current in sites:
            select.value = current

    # The results.

    def refresh_results(self) -> None:
        table = self.query_one("#results", DataTable)
        start, end, wanted = self.window()
        site_choice = self.query_one("#site", Select)
        only_site = None if site_choice.is_blank() else site_choice.value
        only_reservable = self.query_one("#only", Checkbox).value

        found = [
            availability(site, cluster, nodes, start, end, wanted)
            for site, clusters in self.nodes.items() if only_site in (None, site)
            for cluster, nodes in clusters.items()
        ]
        reservable = [a for a in found if a.reservable]
        self.found = rank(reservable if only_reservable else found)

        row = table.cursor_row
        table.clear()
        for a in self.found:
            mark = Text(a.reason(), style="bold green" if a.reservable else "red")
            table.add_row(a.site, a.cluster, f"{a.free} of {a.usable}", mark, key=f"{a.site}/{a.cluster}")
        if self.found:
            table.move_cursor(row=min(row, len(self.found) - 1))

        title = f"reservable: {len(reservable)} of {len(found)} · {start:%a %d %b %H:%M} → {end:%a %d %H:%M}"
        if self.sites_done < self.sites_total:
            title += f" · loading sites {self.sites_done}/{self.sites_total}"
        table.border_title = title
        past = start < now() - HALF_HOUR
        if past:
            self.set_status("that time has passed: choose a later one", error=True)
        elif self.past:
            self.set_status("")  # it was said; it no longer is
        self.past = past

    # Reserving.

    @on(DataTable.RowSelected)
    def reserve(self) -> None:
        """enter on a reservable cluster: the reservation dialog, filled in."""
        table = self.query_one("#results", DataTable)
        if not self.found or not 0 <= table.cursor_row < len(self.found):
            return
        a = self.found[table.cursor_row]
        if not a.reservable:
            self.notify(f"{a.cluster}: {a.reason()}", severity="warning")
            return
        start, end, wanted = self.window()
        gantt = Gantt(self.nodes[a.site][a.cluster], self.loaded_at, clock=now())
        dialog = ReserveDialog(gantt, a.site, a.cluster, self.queues.get((a.site, a.cluster), ()), start,
                               command=self.api.submit_command, walltime=end - start, nodes=wanted)
        self.app.push_screen(dialog, self.chosen)

    def chosen(self, request: JobRequest | None) -> None:
        if request is not None:
            self.submit(request)

    @work(exclusive=True, group="jobs")
    async def submit(self, request: JobRequest) -> None:
        self.set_status("sending the reservation…")
        try:
            job_id = await self.api.submit_job(request)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            self.notify(str(e), title="Not reserved", severity="error", timeout=10)
            return
        self.notify(f"job #{job_id}: {request.summary()}", title="Reserved")
        self.set_status("")
        await self.load_site(request.site)  # the new job takes its nodes
        self.refresh_results()

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")
