"""A pop-up to reserve nodes of a cluster: how many, how long, from when.

It opens over the Reservations tab, filled in from its slot finder, and says
before you send it what the reservation costs: which period it falls in, and
how much of the day's quota it would use. Reserve sends nothing itself: it
closes with the request, and the tab sends it.

    app.push_screen(NewReservation(...), callback)  # callback(request or None)
"""

from __future__ import annotations

import time as clock
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from grid_tui.my_usage import planned_quota
from grid_tui.policy import PARIS, period_at
from grid_tui.widgets.usage_bar.usage_bar import MUTED, level_colour

START_FORMAT = '%Y-%m-%d %H:%M'  # how the start is typed: 2026-11-27 16:00
GREEN, RED = '#a6e3a1', '#f38ba8'


@dataclass(frozen=True)
class ReservationRequest:
    """What the pop-up asks for, once you press Reserve."""

    nodes: int
    seconds: float
    start: float | None  # seconds since 1970; None: as soon as they are free
    name: str = ''
    deploy: bool = False


def read_start(text: str, now: float) -> float | None:
    """The typed start: 'now' (or nothing, or a past time) is None, else a
    Paris time.

    Raises:
        ValueError: It isn't 'now' nor like 2026-11-27 16:00.
    """
    text = text.strip().lower()
    if text in ('', 'now', 'asap'):
        return None
    moment = datetime.strptime(text, START_FORMAT).replace(tzinfo=PARIS)
    start = moment.timestamp()
    return None if start <= now else start


def start_text(start: float | None) -> str:
    """How a start is shown in its box: 'now', or 2026-11-27 16:00."""
    if start is None:
        return 'now'
    return datetime.fromtimestamp(start, PARIS).strftime(START_FORMAT)


class NewReservation(ModalScreen[ReservationRequest | None]):
    """The form: nodes, hours, start, name, deploy; then Reserve or Cancel."""

    DEFAULT_CSS = (Path(__file__).parent / 'new_reservation.tcss').read_text()
    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]

    def __init__(
        self,
        site: str,
        cluster: str,
        *,
        nodes: int = 1,
        seconds: float = 3600,
        start: float | None = None,
        node_cores: int = 0,
        cluster_cores: int = 0,
        free_nodes: int = 0,
        now: Callable[[], float] | None = None,
    ) -> None:
        """Make the form, filled in.

        Args:
            site: The cluster's site, e.g. 'nancy'.
            cluster: The cluster, e.g. 'gros'.
            nodes: How many nodes, to start with.
            seconds: For how long, to start with.
            start: When, to start with (None: now).
            node_cores: Each node's cores (for the quota; 0 if not known).
            cluster_cores: All the cluster's cores (for the quota).
            free_nodes: How many nodes can run jobs (to say if it can't fit).
            now: What gives the time now, in seconds; tests pass a fixed one.
        """
        super().__init__()
        self.site, self.cluster = site, cluster
        self.filled = (nodes, seconds, start)  # what the boxes start with
        self.node_cores, self.cluster_cores = node_cores, cluster_cores
        self.free_nodes = free_nodes
        self.now = now or clock.time

    def compose(self) -> ComposeResult:
        """A title, the form, what it costs, and the buttons."""
        with Vertical(id='new-res') as box:
            box.border_title = f'New reservation · {self.site} / {self.cluster}'
            box.border_subtitle = 'Enter: reserve · Esc: cancel'
            with Grid(id='new-res-form'):
                yield Label('Nodes', classes='form-label')
                yield Input(
                    str(self.filled[0]), type='integer', compact=True, id='new-nodes'
                )
                yield Label('Hours', classes='form-label')
                yield Input(
                    f'{self.filled[1] / 3600:g}',
                    type='number',
                    compact=True,
                    id='new-hours',
                )
                yield Label('Start', classes='form-label')
                yield Input(
                    start_text(self.filled[2]),
                    placeholder='now, or 2026-11-27 16:00',
                    compact=True,
                    id='new-start',
                )
                yield Label('Name', classes='form-label')
                yield Input(placeholder='optional', compact=True, id='new-name')
                yield Label('', classes='form-label')
                yield Checkbox(
                    'Deploy (install your own system with kadeploy)',
                    compact=True,
                    id='new-deploy',
                )
            yield Static('', id='new-cost')
            with Horizontal(id='new-buttons'):
                yield Button('Reserve', compact=True, id='reserve')
                yield Button('Cancel', compact=True, id='cancel')

    def on_mount(self) -> None:
        """Say what it costs as filled in, with the cursor on the nodes."""
        self._update_cost()
        self.query_one('#new-nodes', Input).focus()

    # ---- reading the form -------------------------------------------------

    def request(self) -> ReservationRequest:
        """The form as a request.

        Raises:
            ValueError: Something isn't filled in right; the message says what.
        """
        nodes_text = self.query_one('#new-nodes', Input).value.strip()
        hours_text = self.query_one('#new-hours', Input).value.strip()
        nodes = int(nodes_text) if nodes_text.isdigit() else 0
        if nodes < 1:
            raise ValueError('Ask for 1 node or more.')
        try:
            hours = float(hours_text)
        except ValueError:
            hours = 0
        if hours <= 0:
            raise ValueError('Ask for some time: hours above 0.')
        start_box = self.query_one('#new-start', Input).value
        try:
            start = read_start(start_box, self.now())
        except ValueError:
            raise ValueError('Start: "now", or a time like 2026-11-27 16:00.') from None
        return ReservationRequest(
            nodes=nodes,
            seconds=hours * 3600,
            start=start,
            name=self.query_one('#new-name', Input).value.strip(),
            deploy=self.query_one('#new-deploy', Checkbox).value,
        )

    @on(Input.Changed)
    @on(Checkbox.Changed)
    def _update_cost(self) -> None:
        """Say what the reservation, as filled in, costs under the policy."""
        cost = self.query_one('#new-cost', Static)
        try:
            request = self.request()
        except ValueError as error:
            cost.update(Text(str(error), RED))
            return
        cost.update(self.cost(request))

    def cost(self, request: ReservationRequest) -> Text:
        """The period it starts in, its share of the quota, and if it fits."""
        now = self.now()
        start = request.start if request.start is not None else now
        period = period_at(datetime.fromtimestamp(start, PARIS))
        text = Text.assemble(
            ('Starts ', MUTED),
            ('now' if request.start is None else start_text(start), 'bold'),
            (f' · {period.name.lower()}: {period.rule}', MUTED),
        )
        share = planned_quota(
            request.nodes,
            self.node_cores,
            self.cluster_cores,
            start,
            request.seconds,
            now,
        )
        text.append('\n')
        if share is None:
            text.append("Doesn't count toward the daytime quota", GREEN)
            text.append(' (an exception of the policy)', MUTED)
        elif not self.node_cores:
            text.append("Quota: can't tell (the nodes' cores aren't known)", MUTED)
        elif share == 0:
            text.append('Outside daytime: no quota used', GREEN)
        else:
            colour = level_colour(share)
            text.append(f'About {share}% of the day’s quota', f'bold {colour}')
            text.append(' on this cluster (2 h on all its cores)', MUTED)
            if share >= 100:
                text.append(
                    '\nOver the quota: make it shorter, smaller, or at night', RED
                )
        if self.free_nodes and request.nodes > self.free_nodes:
            text.append(f'\nOnly {self.free_nodes} nodes can run jobs', RED)
        return text

    # ---- the buttons --------------------------------------------------------

    @on(Button.Pressed, '#reserve')
    @on(Input.Submitted)
    def action_reserve(self) -> None:
        """Close with the request (Reserve, or Enter in a box), if it's right."""
        try:
            request = self.request()
        except ValueError as error:
            self.notify(str(error), title='Not yet', severity='warning')
            return
        self.dismiss(request)

    @on(Button.Pressed, '#cancel')
    def action_cancel(self) -> None:
        """Close without reserving (Cancel, or Esc)."""
        self.dismiss(None)
