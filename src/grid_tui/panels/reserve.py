"""Reservations › Reserve: choose a window and how many nodes, see which
clusters can take it, pick one, and reserve it there.

    ╭─ when ───────────────────╮╭─ reservable: 3 of 12 · Sun 22 Nov 18:00 → 20:00 ────────────╮
    │ Date      [Sun 22 Nov ▾] ││ SITE    CLUSTER    FREE ALL THROUGH   RESERVABLE             │
    │ Time      [18:00      ▾] ││ nancy   graffiti    2 of 2            yes                    │ ← picked
    │ Duration  [2h         ▾] ││ nancy   gros       37 of 124          yes                    │
    │ Nodes     [ 2 ]          ││ rennes  paravance   2 of 72           no: only 2 free        │
    │ Site      [any        ▾] ││                                                              │
    │ [x] Only reservable      ││                                                              │
    │ reserve ──────────────── ││                                                              │
    │ nancy/graffiti: it fits  ││                                                              │
    │ Queue     [default    ▾] ││                                                              │
    │ Project   [ my-lab ]     ││                                                              │
    │ [ ] Deploy  [ ] Exotic   ││                                                              │
    │ [ Reserve ]              ││                                                              │
    ╰──────────────────────────╯╰──────────────────────────────────────────────────────────────╯

The cluster under the results' cursor is the one
to reserve on; Reserve (or enter on it) shows the request and the exact
curl call, and asks: [ Yes, send ] [ Back ]. Only Yes sends it. Changing
anything while it asks goes back to the form.

Every site's nodes load in one call per site (GET /sites/{site}/status),
with its clusters (for their queues); each fills in the results when it
arrives. When a site's status fails (the API sometimes crashes on one
site), its clusters' status is asked one by one instead. It loads the
first time the tab is opened; ctrl+r loads again. g shows the picked
cluster's current reservations.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, time, timedelta

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from grid_tui.format import duration
from grid_tui.models import Availability, Cluster, JobRequest, Node, Site
from grid_tui.models.gantt import SPAN
from grid_tui.models.reservable import availability, by_cluster, rank
from grid_tui.api import Api
from grid_tui.panels.messages import ClusterChosen
from grid_tui.screens.reserve import DURATIONS

HALF_HOUR = timedelta(minutes=30)
COLUMNS = ("SITE", "CLUSTER", "FREE ALL THROUGH", "RESERVABLE")
RESERVE_FIELDS = ("queue", "project", "deploy", "exotic")  # they don't change the results


def now() -> datetime:
    return datetime.now().astimezone()


def next_half_hour(t: datetime) -> datetime:
    """The next :00 or :30 after t."""
    hour = t.replace(minute=0, second=0, microsecond=0)
    return hour + (t.minute // 30 + 1) * HALF_HOUR


class ReservePanel(Vertical):
    """Which clusters can take a reservation for a chosen window, and
    reserving on one of them."""

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("ctrl+g", "reservations", "Its reservations"),  # g is a letter: the fields take it
        Binding("ctrl+r", "reload", "Reload"),  # r is a letter: the fields take it
    ]

    DEFAULT_CSS = """
    ReservePanel #form {
        width: 40; border: round $accent; border-title-color: $text; padding: 0 1;
    }
    ReservePanel #form .row { height: auto; }
    ReservePanel #form .row Label { width: 9; padding-top: 1; color: $text-muted; }
    ReservePanel #form .row Select, ReservePanel #form .row Input { width: 1fr; }
    ReservePanel #reserve-title { margin-top: 1; text-style: bold; color: $text; border-top: solid $accent; }
    ReservePanel #picked { margin: 0 0 0 0; }
    ReservePanel #confirm { margin-top: 1; display: none; }
    ReservePanel #sure { display: none; height: auto; }
    ReservePanel #reserve { margin-top: 1; }
    ReservePanel Button { margin-right: 1; }
    ReservePanel.confirming #confirm, ReservePanel.confirming #sure { display: block; }
    ReservePanel.confirming #reserve { display: none; }
    ReservePanel #results {
        width: 1fr; border: round $accent;
        border-title-color: $text; border-subtitle-color: $text-muted;
    }
    ReservePanel #status { height: 1; padding: 0 1; color: $text-muted; }
    ReservePanel #status.error { color: $error; text-style: bold; }
    """

    def __init__(self, api: Api, sites: list[Site] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.api = api
        self.sites = sites  # None: load them first
        self.started = False  # loaded once already
        self.nodes: dict[str, dict[str, list[Node]]] = {}  # site → cluster → nodes
        self.queues: dict[tuple[str, str], tuple[str, ...]] = {}  # (site, cluster) → queues
        self.sites_total = self.sites_done = 0
        self.found: list[Availability] = []  # what the table shows
        self.site_choices: list[str] = []  # what the Site choice offers now
        self.queue_choices: list[str] = ["default"]  # what the Queue choice offers now
        self.past = False  # the window chosen has passed
        self.sending = False

    # The screen.

    def compose(self) -> ComposeResult:
        start = next_half_hour(now())
        with Horizontal():
            with VerticalScroll(id="form") as form:
                form.border_title = "when"
                days = [now().date() + timedelta(days=i) for i in range(SPAN.days)]
                times = [time(h, m) for h in range(24) for m in (0, 30)]
                with Horizontal(classes="row"):
                    yield Label("Date")
                    yield Select([(f"{d:%a %d %b}", d) for d in days], allow_blank=False, id="date",
                                 value=start.date() if start.date() in days else days[0])
                with Horizontal(classes="row"):
                    yield Label("Time")
                    yield Select([(f"{t:%H:%M}", t) for t in times], value=start.time(), allow_blank=False, id="time")
                with Horizontal(classes="row"):
                    yield Label("Duration")
                    yield Select([(duration(d), d) for d in DURATIONS], value=DURATIONS[2], allow_blank=False,
                                 id="duration")
                with Horizontal(classes="row"):
                    yield Label("Nodes")
                    yield Input("1", type="integer", id="nodes")
                with Horizontal(classes="row"):
                    yield Label("Site")
                    yield Select([], prompt="any", id="site")
                yield Checkbox("Only reservable", value=True, id="only")

                yield Static("reserve", id="reserve-title")
                yield Static(id="picked")
                with Horizontal(classes="row"):
                    yield Label("Queue")
                    yield Select([("default", "default")], value="default", allow_blank=False, id="queue")
                with Horizontal(classes="row"):
                    yield Label("Project")
                    yield Input(os.environ.get("G5K_PROJECT", ""), placeholder="optional", id="project")
                with Horizontal(classes="row"):
                    yield Checkbox("Deploy", id="deploy", tooltip="install your own system (kadeploy)")
                    yield Checkbox("Exotic", id="exotic", tooltip="needed on exotic clusters")
                yield Button("Reserve", variant="primary", id="reserve")
                yield Static(id="confirm", markup=False)
                with Horizontal(id="sure"):
                    yield Button("Yes, send", variant="success", id="send")
                    yield Button("Back", id="back")
            table: DataTable = DataTable(id="results", cursor_type="row", zebra_stripes=True)
            table.border_subtitle = "$ " + self.api.command("/sites/{site}/status") + ", every site"
            yield table
        yield Static("", id="status", markup=False)

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).add_columns(*COLUMNS)
        self.refresh_results()

    def activate(self) -> None:
        """The tab is shown: load every site, the first time."""
        if not self.started:
            self.started = True
            self.load()

    def action_reload(self) -> None:
        self.load()

    def action_back(self) -> None:
        """esc: out of the question, if one is asked."""
        self.unconfirm()

    def action_reservations(self) -> None:
        """The picked cluster's current reservations."""
        a = self.picked
        if a is not None:
            self.post_message(ClusterChosen(Site(a.site), Cluster(a.cluster, queues=self.queues.get((a.site, a.cluster), ())),
                                            reservations=True))

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
        results = self.query_one("#results", DataTable)
        results.loading = True  # until the first site arrives
        errors = []
        for done in asyncio.as_completed([self.load_site(s.uid) for s in sites]):
            site, error = await done
            if error:
                errors.append(f"{site}: {error}")
            self.sites_done += 1
            results.loading = False
            self.refresh_sites()
            self.refresh_results()
        if errors:
            self.set_status("not everything loaded: " + "; ".join(errors), error=True)
        else:
            self.set_status("")

    async def load_site(self, site: str) -> tuple[str, str]:
        """A site's nodes (one call) and its clusters' queues, at the same
        time. If the site's status fails, each of its clusters' status is
        asked instead: the clusters that answer still show."""
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

        answers = await asyncio.gather(*(self.api.nodes(site, c.uid) for c in clusters), return_exceptions=True)
        found = {c.uid: a for c, a in zip(clusters, answers) if not isinstance(a, BaseException)}
        failed = {c.uid: a for c, a in zip(clusters, answers) if isinstance(a, BaseException)}
        if found:
            self.nodes[site] = found
        if not failed:
            return site, ""
        # Say what the site said, and what each cluster said too.
        said = "; ".join(f"{c}: {e}" for c, e in failed.items())
        if not found:
            return site, f"its status failed ({nodes}), and so did every cluster's ({said})"
        return site, f"{', '.join(failed)} didn't answer ({said})"

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
    def changed(self, event) -> None:
        self.unconfirm()  # what is asked has changed: ask again
        if event.control.id not in RESERVE_FIELDS:
            self.refresh_results()  # the window, the nodes or the filter changed

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
        picked = self.picked
        self.found = rank(reservable if only_reservable else found)

        table.clear()
        for a in self.found:
            mark = Text(a.reason(), style="bold green" if a.reservable else "red")
            table.add_row(a.site, a.cluster, f"{a.free} of {a.usable}", mark, key=f"{a.site}/{a.cluster}")
        if self.found:  # keep the same cluster picked if it is still there
            keys = [(a.site, a.cluster) for a in self.found]
            row = keys.index((picked.site, picked.cluster)) if picked and (picked.site, picked.cluster) in keys else 0
            table.move_cursor(row=row)

        title = f"reservable: {len(reservable)} of {len(found)} · {start:%a %d %b %H:%M} → {end:%a %d %H:%M}"
        if self.sites_done < self.sites_total:
            title += f" · loading sites {self.sites_done}/{self.sites_total}"
        table.border_title = title
        self.refresh_picked()

        past = start < now() - HALF_HOUR
        if past:
            self.set_status("that time has passed: choose a later one", error=True)
        elif self.past:
            self.set_status("")  # it was said; it no longer is
        self.past = past

    @property
    def picked(self) -> Availability | None:
        """The cluster under the results' cursor: the one to reserve on."""
        table = self.query_one("#results", DataTable)
        if not self.found or not 0 <= table.cursor_row < len(self.found):
            return None
        return self.found[table.cursor_row]

    @on(DataTable.RowHighlighted)
    def moved(self) -> None:
        self.unconfirm()
        self.refresh_picked()

    def refresh_picked(self) -> None:
        """Say which cluster is picked and whether it fits; offer its queues."""
        a = self.picked
        picked = self.query_one("#picked", Static)
        if a is None:
            picked.update(Text("pick a cluster in the results", style="dim"))
            return
        style = "bold green" if a.reservable else "red"
        picked.update(Text(f"{a.site}/{a.cluster}: {'it fits' if a.reservable else a.reason()}", style=style))
        queues = [q for q in self.queues.get((a.site, a.cluster), ()) if q != "admin"] or ["default"]
        if queues != self.queue_choices:
            select = self.query_one("#queue", Select)
            current = select.value
            with select.prevent(Select.Changed):
                select.set_options([(q, q) for q in queues])
                select.value = current if current in queues else queues[0]
            self.queue_choices = queues

    # Reserving.

    def request(self) -> JobRequest | None:
        """What would be asked of OAR for the picked cluster, or None."""
        a = self.picked
        if a is None:
            return None
        start, end, wanted = self.window()
        types = tuple(t for t in ("deploy", "exotic") if self.query_one(f"#{t}", Checkbox).value)
        return JobRequest(
            site=a.site, cluster=a.cluster, nodes=wanted, walltime=end - start,
            start=start if start > now() else None,  # a start just passed: as soon as possible
            queue=str(self.query_one("#queue", Select).value),
            project=self.query_one("#project", Input).value.strip(),
            types=types,
        )

    @on(DataTable.RowSelected)
    @on(Button.Pressed, "#reserve")
    def ask(self) -> None:
        """Reserve (or enter on a cluster): show the request, and ask."""
        a, r = self.picked, self.request()
        if a is None or r is None:
            self.notify("pick a cluster in the results", severity="warning")
            return
        if not a.reservable:
            self.notify(f"{a.cluster}: {a.reason()}", severity="warning")
            return
        self.query_one("#confirm", Static).update(
            f"Send this reservation?\n{r.summary()}\n\n$ {self.api.submit_command(r)}"
        )
        self.add_class("confirming")
        send = self.query_one("#send", Button)
        send.focus()
        self.call_after_refresh(send.scroll_visible)

    def unconfirm(self) -> None:
        if self.has_class("confirming") and not self.sending:
            self.remove_class("confirming")

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.unconfirm()
        self.query_one("#reserve", Button).focus()

    @on(Button.Pressed, "#send")
    def send(self) -> None:
        r = self.request()
        if r is not None:
            self.submit(r)

    @work(exclusive=True, group="jobs")
    async def submit(self, request: JobRequest) -> None:
        self.sending = True
        self.set_status("sending the reservation…")
        try:
            job_id = await self.api.submit_job(request)
        except Exception as e:
            self.set_status(f"error: {e}", error=True)
            self.notify(str(e), title="Not reserved", severity="error", timeout=10)
            return
        finally:
            self.sending = False
            self.unconfirm()
        self.notify(f"job #{job_id}: {request.summary()}", title="Reserved")
        self.set_status("")
        await self.load_site(request.site)  # the new job takes its nodes
        self.refresh_results()

    def set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        status.set_class(error, "error")
