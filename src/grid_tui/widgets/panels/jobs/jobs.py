"""The Jobs panel: your jobs on every site, those running or waiting first.

It shows the jobs that run now or will, and those that ran in the last day,
with their nodes and cores. The box under the table lists the machines of
the job the cursor is on: Tab into it and Enter on a machine opens an SSH
session there (s does the same for the job's first machine). Enter on a job
shows its cluster in the Reservations tab.

Jobs change all the time: the list is loaded when the tab is first shown,
then again every few minutes while it shows (and the terminal is in front).
"""

from __future__ import annotations

import re
import time as clock
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Label, OptionList
from textual.widgets.option_list import Option

from grid_tui.format import duration, number
from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Job
from grid_tui.policy import PARIS
from grid_tui.utils import ssh

COLUMNS = (
    'Site',
    'Job',
    'State',
    'Queue',
    'Cluster',
    'Nodes',
    'Cores',
    'Start',
    'Walltime',
    'Ends',
)
DAY = 24 * 3600
SINCE = DAY  # finished jobs are shown if they started this long ago or less
REFRESH_SECONDS = 120  # reload this often, while the tab shows
NO_LOGIN = 'No login: set G5K_USER and G5K_PASSWORD to see your jobs.'
NONE = 'No jobs running or waiting, and none in the last 24 h.'

# the colour of each state; any other state is grey
STATE_COLOURS = {
    'running': '#a6e3a1',  # green
    'launching': '#a6e3a1',
    'waiting': '#f9e2af',  # yellow
    'tolaunch': '#f9e2af',
    'toLaunch': '#f9e2af',
    'hold': '#f9e2af',
    'error': '#f38ba8',  # red
}
FINISHED_COLOUR = '#6c7086'


def when(moment: float | None) -> str:
    """A time in Paris, e.g. 'Fri 14:00'; '' if there is none."""
    if not moment:
        return ''
    return datetime.fromtimestamp(moment, PARIS).strftime('%a %H:%M')


def ends(job: Job) -> float | None:
    """When the job ended, or will at the latest; None if it hasn't started."""
    if job.stopped_at:
        return job.stopped_at
    if job.started_at:
        return job.started_at + job.walltime
    return None


def order(job: Job) -> tuple:
    """Running first, then waiting, then finished; the latest first in each."""
    if job.is_running:
        rank = 0
    elif job.is_active:
        rank = 1
    else:
        rank = 2
    return (rank, -(job.started_at or job.submitted_at or 0), job.site, job.uid)


def state_text(job: Job) -> Text:
    """The job's state, coloured: green running, yellow waiting, red error."""
    colour = STATE_COLOURS.get(job.state, FINISHED_COLOUR)
    return Text(job.state or '?', style=colour)


def job_row(job: Job) -> tuple[Any, ...]:
    """The table row of a job, in the order of COLUMNS."""
    dim = '' if job.is_active else FINISHED_COLOUR  # finished jobs read grey
    cells = (
        job.site,
        f'#{job.uid}',
        None,  # the state: coloured below
        job.queue,
        job.cluster,
        number(len(job.assigned_nodes)),
        number(job.cores),
        when(job.started_at) or ('not yet' if job.is_active else ''),
        duration(job.walltime),
        when(ends(job)),
    )
    return tuple(
        state_text(job) if cell is None else Text(cell, style=dim) for cell in cells
    )


def machine_order(name: str) -> tuple:
    """Sort machine names by their numbers: gros-2 before gros-10."""
    return tuple(
        (0, int(part), '') if part.isdigit() else (1, 0, part)
        for part in re.split(r'(\d+)', name)
    )


def machines(job: Job) -> list[str]:
    """The job's machines, short names (gros-1, not gros-1.nancy…), in order."""
    names = {node.split('.')[0] for node in job.assigned_nodes}
    return sorted(names, key=machine_order)


def machines_text(job: Job | None) -> tuple[str, str]:
    """The Machines box for a job: its title, and the machines (or why none)."""
    if job is None:
        return 'Machines', 'Move onto a job to see its machines.'
    names = machines(job)
    title = f'Machines of #{job.uid}'
    if names:
        title += f' ({len(names)})'
    if names:
        return title, '  '.join(names)
    if job.is_active:
        return title, 'None yet: the job is waiting for its start.'
    return title, 'None: the job never ran on any.'


def summary(jobs: list[Job]) -> str:
    """How many jobs there are of each kind, e.g. '1 running · 2 waiting'."""
    running = sum(job.is_running for job in jobs)
    waiting = sum(job.is_active and not job.is_running for job in jobs)
    finished = len(jobs) - running - waiting
    parts = [
        f'{running} running' if running else '',
        f'{waiting} waiting' if waiting else '',
        f'{finished} finished in the last 24 h' if finished else '',
    ]
    return ' · '.join(part for part in parts if part) or NONE


class JobsPanel(Widget):
    """A table of your jobs on every site: running, waiting, and recent."""

    DEFAULT_CSS = (Path(__file__).parent / 'jobs.tcss').read_text()
    BINDINGS = [Binding('s', 'ssh', 'SSH to machine')]

    class Chosen(Message):
        """Sent when a job with nodes is chosen (Enter, or a click)."""

        def __init__(self, site: str, cluster: str) -> None:
            """Make the message.

            Args:
                site: The job's site, e.g. 'nancy'.
                cluster: The cluster its nodes are in, e.g. 'gros'.
            """
            super().__init__()
            self.site = site
            self.cluster = cluster

    def __init__(
        self,
        client: Client,
        now: Callable[[], float] | None = None,
        **kwargs: Any,
    ) -> None:
        """Make the panel.

        Args:
            client: Where to load your jobs from; its user is whose jobs they are.
            now: What time it is, in seconds; tests give a fixed one.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.now = now or clock.time
        self.jobs: dict[str, Job] = {}  # the jobs in the table, by 'site/uid'
        self.current: Job | None = None  # the job the cursor is on
        self._loaded_at: float | None = None  # when, by clock.monotonic()

    def compose(self) -> ComposeResult:
        """A line saying how many jobs there are, the table, then its machines."""
        yield Label('', id='jobs-status')
        yield DataTable(cursor_type='row', zebra_stripes=True)
        yield OptionList(id='job-machines')

    def on_mount(self) -> None:
        """Add the columns, and check every so often whether to reload."""
        self.query_one(DataTable).add_columns(*COLUMNS)
        self.set_interval(REFRESH_SECONDS, self._poll)

    def on_show(self) -> None:
        """The tab is shown: load the jobs the first time."""
        if self._loaded_at is None:
            self.load()

    def _poll(self) -> None:
        """Reload on the timer, but only if someone is looking."""
        if self.is_on_screen and getattr(self.app, 'polling', True):
            self.load(refresh=True)

    @work(exclusive=True)  # runs in the background; a new load cancels the old one
    async def load(self, refresh: bool = False) -> None:
        """Fetch your jobs from every site and show them.

        Args:
            refresh: Ask the API again, not what was asked a moment ago (r).
        """
        status = self.query_one('#jobs-status', Label)
        if not self.client.jobs.user:
            self._loaded_at = clock.monotonic()
            self.show([])
            status.update(NO_LOGIN)
            return
        self.loading = True  # shows a spinner over the panel
        since = datetime.fromtimestamp(self.now() - SINCE, PARIS)
        try:
            jobs = await self.client.jobs.mine_today(since, refresh=refresh)
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load your jobs", severity='error')
            self.show([])
            status.update("Couldn't load your jobs. Press r to try again.")
            return
        finally:
            self.loading = False
        self._loaded_at = clock.monotonic()
        self.show(jobs)

    def show(self, jobs: list[Job]) -> None:
        """Put the jobs in the table, running first, and count them."""
        jobs = sorted(jobs, key=order)
        self.jobs = {f'{job.site}/{job.uid}': job for job in jobs}
        table = self.query_one(DataTable)
        table.clear()
        for key, job in self.jobs.items():
            table.add_row(*job_row(job), key=key)
        self.query_one('#jobs-status', Label).update(summary(jobs))
        self._show_machines(next(iter(self.jobs.values()), None))

    @on(DataTable.RowHighlighted)
    def _job_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """The cursor moved onto a job: list its machines under the table."""
        self._show_machines(self.jobs.get(event.row_key.value))

    def _show_machines(self, job: Job | None) -> None:
        """Fill the Machines box for job: its machines, or why there are none."""
        self.current = job
        title, text = machines_text(job)
        box = self.query_one('#job-machines', OptionList)
        box.border_title = title
        box.clear_options()
        names = machines(job) if job is not None else []
        if names:
            box.add_options(names)
            box.highlighted = 0  # so ↓ goes to the second machine
            box.border_subtitle = 'Enter: SSH'
        else:
            box.add_option(Option(text, disabled=True))
            box.border_subtitle = ''

    @on(OptionList.OptionSelected, '#job-machines')
    def _machine_chosen(self, event: OptionList.OptionSelected) -> None:
        """Enter on a machine: open an SSH session on it."""
        if self.current is not None:
            self.ssh_into(self.current, str(event.option.prompt))

    def action_ssh(self) -> None:
        """SSH to a machine of the job (the s key).

        The machine the Machines list's cursor is on, if it has the focus;
        else the job's first machine.
        """
        job = self.current
        if job is None:
            return
        names = machines(job)
        if not names:
            self.notify(
                'It has no machines yet: it is waiting for its start.',
                title=f"Can't SSH to #{job.uid}",
                severity='warning',
            )
            return
        box = self.query_one('#job-machines', OptionList)
        machine = names[0]
        if box.has_focus and box.highlighted is not None:
            machine = str(box.get_option_at_index(box.highlighted).prompt)
        self.ssh_into(job, machine)

    def ssh_into(self, job: Job, machine: str) -> None:
        """Open a shell on one of job's machines; the app steps aside meanwhile.

        It goes through the site's frontend, as by hand: ssh site, then ssh
        machine.

        Args:
            job: The job the machine belongs to (only its machines let you in).
            machine: The machine, e.g. 'gros-1'.
        """
        if not job.is_running:
            self.notify(
                'Only the machines of a running job can be reached.',
                title=f"Can't SSH to {machine}",
                severity='warning',
            )
            return
        if not ssh.ssh_available():
            self.notify('Install OpenSSH to connect.', title='No ssh', severity='error')
            return
        command = ssh.machine_command(
            job.site, machine, self.client.jobs.user, deploy=job.is_deploy
        )
        away = getattr(self.app, 'away', None)  # stop polling during the session
        try:
            if away:
                away(True)
            with self.app.suspend():
                code = ssh.run(command)
        except SuspendNotSupported:
            self.notify(
                'Run the app in a terminal to connect: ' + ' '.join(command),
                title="Can't open SSH here",
                severity='warning',
            )
            return
        finally:
            if away:
                away(False)
        if code == ssh.SSH_FAILED:
            self.notify(
                "Check that your SSH key is added to your Grid'5000 account.",
                title=f"Couldn't connect to {machine}",
                severity='error',
            )

    @on(DataTable.RowSelected)
    def _job_chosen(self, event: DataTable.RowSelected) -> None:
        """A job was chosen: show its cluster (if it has nodes yet)."""
        job = self.jobs.get(event.row_key.value)
        if job is not None and job.cluster:
            self.post_message(self.Chosen(job.site, job.cluster))
