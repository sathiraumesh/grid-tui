"""The dialogs of the reservations screen: reserving by choosing, and
confirming a cancel.

ReserveDialog, filled from where the cursor was:

    ╭─ Reserve nodes of gros at nancy ─────────────────╮
    │ Start      Sun 22 18:00                            │
    │ [ ] As soon as possible                            │
    │ Nodes      [ 2          ▾]                         │
    │ Duration   [ 2h         ▾]                         │
    │ Queue      [ default    ▾]                         │
    │ Project    [ my-lab        ]  (optional)           │
    │ [ ] Deploy   [ ] Exotic                            │
    │  37 of 124 nodes free all through: it fits         │
    │                       [ Reserve ]  [ Cancel ]      │
    ╰────────────────────────────────────────────────────╯

On a terminal too small for it, the dialog scrolls, up and down and sideways
(the wheel, shift+wheel, or the scroll bars; tab moves to the next field and
scrolls to it).

Reserve shows the request in words and the exact curl call, and asks again:
[ Yes, send ] [ Back ]. Only Yes returns the request; esc or Cancel return
None. Nothing is sent from here: the reservations screen sends it.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from grid_tui.format import duration
from grid_tui.models import Gantt, JobRequest
from grid_tui.widgets.timeline import MANY_FREE, NONE_FREE, SOME_FREE

# The durations to choose from.
DURATIONS = [timedelta(minutes=m) for m in (15, 30, 60, 120, 180, 240, 360, 480, 720, 1440, 2880)]


class ReserveDialog(ModalScreen[JobRequest | None]):
    """Reserve nodes of a cluster, by choosing."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    ReserveDialog { align: center middle; }
    ReserveDialog #dialog {
        width: 76; max-width: 100%;
        height: auto; max-height: 100%;
        overflow: auto auto;          /* scrolls both ways when the terminal is too small */
        border: round $accent; border-title-color: $text;
        padding: 1 2; background: $surface;
    }
    ReserveDialog #form { width: 68; height: auto; }
    ReserveDialog .row { height: auto; }
    ReserveDialog .row Label { width: 11; padding-top: 1; color: $text-muted; }
    ReserveDialog .row Select, ReserveDialog .row Input { width: 1fr; }
    ReserveDialog #fit { margin-top: 1; }
    ReserveDialog #confirm { margin-top: 1; display: none; }
    ReserveDialog #buttons, ReserveDialog #sure { height: auto; align-horizontal: right; margin-top: 1; }
    ReserveDialog #sure { display: none; }
    ReserveDialog Button { margin-left: 2; }
    ReserveDialog.confirming #confirm, ReserveDialog.confirming #sure { display: block; }
    ReserveDialog.confirming #buttons { display: none; }
    """

    def __init__(self, gantt: Gantt, site: str, cluster: str, queues: tuple[str, ...],
                 start: datetime, hours: int = 1, command=None, *,
                 walltime: timedelta | None = None, nodes: int = 1) -> None:
        super().__init__()
        self.gantt, self.site, self.cluster = gantt, site, cluster
        self.queues = [q for q in queues if q != "admin"] or ["default"]
        self.start = start
        self.default = walltime or timedelta(hours=hours)
        self.nodes = nodes
        self.command = command or (lambda r: "")  # the curl command of a request

    def compose(self) -> ComposeResult:
        usable = self.gantt.free_between(self.gantt.now, self.gantt.now + timedelta(seconds=1))[1] or 1
        asap = self.start <= self.gantt.now
        with ScrollableContainer(id="dialog") as dialog:
            dialog.border_title = f"Reserve nodes of {self.cluster} at {self.site}"
            with Vertical(id="form"):  # a fixed width: a narrow terminal scrolls it sideways
                with Horizontal(classes="row"):
                    yield Label("Start")
                    yield Static(id="start")
                yield Checkbox("As soon as possible", value=asap, id="asap", disabled=asap)
                with Horizontal(classes="row"):
                    yield Label("Nodes")
                    counts = range(1, max(usable, self.nodes) + 1)
                    yield Select([(str(n), n) for n in counts], value=self.nodes, allow_blank=False, id="nodes")
                with Horizontal(classes="row"):
                    yield Label("Duration")
                    options = [(duration(d), d) for d in DURATIONS]
                    yield Select(options, value=self.default if self.default in DURATIONS else DURATIONS[2],
                                 allow_blank=False, id="duration")
                with Horizontal(classes="row"):
                    yield Label("Queue")
                    yield Select([(q, q) for q in self.queues], value=self.queues[0], allow_blank=False, id="queue")
                with Horizontal(classes="row"):
                    yield Label("Project")
                    yield Input(value=os.environ.get("G5K_PROJECT", ""), placeholder="optional", id="project")
                with Horizontal(classes="row"):
                    yield Checkbox("Deploy", id="deploy", tooltip="install your own system (kadeploy)")
                    yield Checkbox("Exotic", id="exotic", tooltip="needed on exotic clusters")
                yield Static(id="fit")
                yield Static(id="confirm", markup=False)
                with Horizontal(id="buttons"):
                    yield Button("Reserve", variant="primary", id="reserve")
                    yield Button("Cancel", id="cancel")
                with Horizontal(id="sure"):
                    yield Button("Yes, send", variant="success", id="send")
                    yield Button("Back", id="back")

    def on_mount(self) -> None:
        self.refresh_fit()

    # What is chosen.

    def request(self) -> JobRequest:
        asap = self.query_one("#asap", Checkbox).value
        types = tuple(t for t in ("deploy", "exotic") if self.query_one(f"#{t}", Checkbox).value)
        return JobRequest(
            site=self.site,
            cluster=self.cluster,
            nodes=int(self.query_one("#nodes", Select).value),
            walltime=self.query_one("#duration", Select).value,
            start=None if asap else self.start,
            queue=str(self.query_one("#queue", Select).value),
            project=self.query_one("#project", Input).value.strip(),
            types=types,
        )

    @on(Select.Changed)
    @on(Checkbox.Changed)
    @on(Input.Changed)
    def refresh_fit(self) -> None:
        """Say when, and whether the nodes are free all through."""
        r = self.request()
        start = r.start or self.gantt.now
        end = start + r.walltime
        when = "as soon as possible" if r.start is None else f"{start:%a %d %b %H:%M}"
        self.query_one("#start", Static).update(f"{when} → {end:%a %d %H:%M}")
        free, usable = self.gantt.free_between(start, end)
        if free >= r.nodes:
            text, style = f" {free} of {usable} nodes free all through: it fits ", MANY_FREE
        elif r.start is None:
            text, style = f" {free} of {usable} free now: OAR will start it when {r.nodes} are ", SOME_FREE
        else:
            text, style = f" only {free} of {usable} free all through: OAR will refuse it ", NONE_FREE
        self.query_one("#fit", Static).update(Text(text, style=style))

    # The buttons.

    @on(Button.Pressed, "#reserve")
    def ask(self) -> None:
        """Show the request and ask again."""
        r = self.request()
        self.query_one("#confirm", Static).update(f"Send this reservation?\n{r.summary()}\n\n$ {self.command(r)}")
        self.add_class("confirming")
        send = self.query_one("#send", Button)
        send.focus()
        self.call_after_refresh(send.scroll_visible)  # on a small terminal, scroll down to it

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.remove_class("confirming")
        self.query_one("#reserve", Button).focus()

    @on(Button.Pressed, "#send")
    def send(self) -> None:
        self.dismiss(self.request())

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDialog(ModalScreen[bool]):
    """A yes/no question: True only for Yes."""

    BINDINGS = [Binding("escape", "no", "No"), Binding("y", "yes", "Yes"), Binding("n", "no", "No")]

    DEFAULT_CSS = """
    ConfirmDialog { align: center middle; }
    ConfirmDialog #dialog {
        width: 64; max-width: 100%; height: auto; max-height: 100%;
        overflow: auto auto;
        border: round $warning; padding: 1 2; background: $surface;
    }
    ConfirmDialog #buttons { height: auto; align-horizontal: right; margin-top: 1; }
    ConfirmDialog Button { margin-left: 2; }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="dialog"):
            yield Static(self.question, markup=False)
            with Horizontal(id="buttons"):
                yield Button("Yes", variant="error", id="yes")
                yield Button("No", variant="primary", id="no")

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()  # the safe answer first

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)
