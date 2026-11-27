"""Tests for the Jobs panel: your jobs on every site, and choosing one."""

from contextlib import nullcontext
from datetime import datetime

import httpx
import pytest
from textual.app import App, ComposeResult, SuspendNotSupported
from textual.pilot import Pilot
from textual.widgets import DataTable, Label, OptionList

from grid_tui.grid5000 import Client
from grid_tui.models import Job
from grid_tui.policy import PARIS
from grid_tui.utils import ssh
from grid_tui.widgets.panels.jobs import JobsPanel
from grid_tui.widgets.panels.jobs.jobs import (
    CANCEL_COLOUR,
    COLUMNS,
    NO_LOGIN,
    NONE,
    JobsTable,
    cancel_button,
    ends,
    machine_order,
    machines,
    machines_text,
    order,
    state_text,
    summary,
    when,
)
from grid_tui.widgets.popups.confirm import Confirm
from tests.grid5000.fakes import SITES, fake_client, fake_grid5000
from tests.widgets.panels.helpers import settle

HOUR = 3600
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=PARIS).timestamp()  # Thursday noon

RUNNING = {
    'uid': 1,
    'state': 'running',
    'queue': 'default',
    'started_at': NOW - HOUR,
    'walltime': 2 * HOUR,
    'assigned_nodes': ['gros-1.nancy.grid5000.fr'],
    'resources_by_type': {'cores': ['1', '2']},
}
WAITING = {
    'uid': 2,
    'state': 'waiting',
    'queue': 'default',
    'submitted_at': NOW - 600,
    'walltime': HOUR,
}
FINISHED = {
    'uid': 3,
    'state': 'terminated',
    'queue': 'besteffort',
    'started_at': NOW - 5 * HOUR,
    'stopped_at': NOW - 4 * HOUR,
    'walltime': 3 * HOUR,
    'assigned_nodes': ['nova-1.lyon.grid5000.fr', 'nova-2.lyon.grid5000.fr'],
    'resources_by_type': {'cores': ['1', '2', '3', '4']},
}
LAST_WEEK = {**FINISHED, 'uid': 4, 'started_at': NOW - 7 * 24 * HOUR}
JOBS = {'nancy': [RUNNING, WAITING], 'lyon': [FINISHED, LAST_WEEK]}


class JobsApp(App):
    """A tiny app that shows only the Jobs panel, and keeps the jobs chosen."""

    def __init__(self, client: Client) -> None:
        """Make the app.

        Args:
            client: What the panel loads your jobs from.
        """
        super().__init__()
        self.client = client
        self.chosen: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        """The only widget: the Jobs panel, at a fixed time."""
        yield JobsPanel(self.client, now=lambda: NOW)

    def on_jobs_panel_chosen(self, message: JobsPanel.Chosen) -> None:
        """Keep each job's cluster the panel says was chosen."""
        self.chosen.append((message.site, message.cluster))


def alice(jobs: dict | None = None, status: int = 200) -> Client:
    """A client logged in as alice, on the fake API with these jobs."""
    return fake_client(
        SITES, jobs=JOBS if jobs is None else jobs, user='alice', status=status
    )


def table(app: App) -> DataTable:
    """The panel's table of jobs."""
    return app.query_one(JobsPanel).query_one(DataTable)


def texts(app: App) -> list[list[str]]:
    """Every row of the table, as plain text."""
    t = table(app)
    return [[str(cell) for cell in t.get_row_at(i)] for i in range(t.row_count)]


def status(app: App) -> str:
    """The line above the table."""
    return str(app.query_one('#jobs-status', Label).render())


async def shown(app: App, pilot: Pilot) -> None:
    """Wait for the first load to finish."""
    await settle(app, pilot)


# The table


async def test_has_the_columns() -> None:
    """The table has a job's site, number, state, nodes and times."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert [str(c.label) for c in table(app).columns.values()] == list(COLUMNS)


async def test_shows_your_jobs_running_first_then_waiting_then_finished() -> None:
    """Running, then waiting, then finished; a job from last week is left out."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert [(row[0], row[1], row[2]) for row in texts(app)] == [
            ('nancy', '#1', 'running'),
            ('nancy', '#2', 'waiting'),
            ('lyon', '#3', 'terminated'),
        ]


async def test_a_running_jobs_row() -> None:
    """A running job shows its cluster, nodes, cores and times in Paris."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert texts(app)[0] == [
            'nancy',
            '#1',
            'running',
            'default',
            'gros',
            '1',
            '2',
            'Thu 11:00',
            '2 h',
            'Thu 13:00',
            '✕ Cancel',
        ]


async def test_a_waiting_job_has_not_started_yet() -> None:
    """A waiting job has no nodes, starts 'not yet' and has no end."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        row = texts(app)[1]
        assert (row[4], row[5], row[7], row[9]) == ('', '', 'not yet', '')


async def test_a_finished_job_ends_when_it_stopped() -> None:
    """A finished job's end is when it stopped, not start + walltime."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        row = texts(app)[2]
        assert (row[4], row[5], row[6]) == ('nova', '2', '4')
        assert (row[7], row[9]) == ('Thu 07:00', 'Thu 08:00')


async def test_the_status_counts_the_jobs() -> None:
    """The line above the table counts running, waiting and finished jobs."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert status(app) == '1 running · 1 waiting · 1 finished in the last 24 h'


async def test_no_jobs_says_so() -> None:
    """With no jobs anywhere, the table is empty and the status says so."""
    app = JobsApp(alice({'nancy': [], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert table(app).row_count == 0
        assert status(app) == NONE


async def test_without_a_login_it_says_how_to_log_in() -> None:
    """With no user, nothing is asked and the status says to set G5K_USER."""
    seen = []
    app = JobsApp(Client(transport=fake_grid5000(SITES, jobs=JOBS, seen=seen)))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert table(app).row_count == 0
        assert status(app) == NO_LOGIN
        assert seen == []  # no request without a login


async def test_an_error_shows_a_notification() -> None:
    """If no site's jobs can be read, a red toast says so."""
    app = JobsApp(alice(status=401))
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await shown(app, pilot)
        assert table(app).row_count == 0
        assert [n.severity for n in app._notifications] == ['error']
        assert 'r to try again' in status(app)


async def test_loading_again_does_not_add_the_rows_twice() -> None:
    """Loading again replaces the rows."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        app.query_one(JobsPanel).load(refresh=True)
        await settle(app, pilot)
        assert table(app).row_count == 3


async def test_the_timer_reloads_while_it_shows() -> None:
    """The timer's reload picks up a new job."""
    jobs = {'nancy': [RUNNING], 'lyon': []}
    app = JobsApp(alice(jobs))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert table(app).row_count == 1
        jobs['nancy'].append(WAITING)
        app.query_one(JobsPanel)._poll()
        await settle(app, pilot)
        assert table(app).row_count == 2


# Choosing a job


async def test_enter_on_a_job_sends_its_site_and_cluster() -> None:
    """Enter on a job with nodes sends Chosen with its site and cluster."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('enter')  # #1 on gros
        await pilot.pause()
        assert app.chosen == [('nancy', 'gros')]


async def test_enter_on_a_waiting_job_does_nothing() -> None:
    """A waiting job has no cluster yet: choosing it sends nothing."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('down', 'enter')  # #2, waiting
        await pilot.pause()
        assert app.chosen == []


# How the cells read


def job(**fields: object) -> Job:
    """A job with these fields."""
    return Job.model_validate({'uid': 1, 'site': 'nancy', **fields})


def test_when_is_in_paris_time() -> None:
    """Times read in Paris, whatever the computer's time zone."""
    assert when(NOW) == 'Thu 12:00'
    assert when(None) == ''


def test_ends() -> None:
    """A job ends when it stopped, or at start + walltime; None if not started."""
    assert ends(job(started_at=100, walltime=50)) == 150
    assert ends(job(started_at=100, stopped_at=120, walltime=50)) == 120
    assert ends(job(state='waiting', walltime=50)) is None


def test_order_puts_running_then_waiting_then_finished_latest_first() -> None:
    """Running first, then waiting, then finished; the latest first in each."""
    jobs = [
        job(uid=1, state='terminated', started_at=10),
        job(uid=2, state='waiting', submitted_at=5),
        job(uid=3, state='running', started_at=1),
        job(uid=4, state='terminated', started_at=20),
    ]
    assert [j.uid for j in sorted(jobs, key=order)] == [3, 2, 4, 1]


def test_state_colours() -> None:
    """Running is green, waiting yellow, error red, the rest grey."""
    colour = {
        state: str(state_text(job(state=state)).style)
        for state in ('running', 'waiting', 'error', 'terminated')
    }
    assert colour == {
        'running': '#a6e3a1',
        'waiting': '#f9e2af',
        'error': '#f38ba8',
        'terminated': '#6c7086',
    }


def test_summary() -> None:
    """The summary leaves out the kinds with no jobs."""
    assert summary([job(state='running')]) == '1 running'
    assert summary([]) == NONE


# The machines under the table


def machines_box(app: App) -> tuple[str, list[str]]:
    """The Machines box: its title, and the lines it lists."""
    box = app.query_one('#job-machines', OptionList)
    lines = [str(box.get_option_at_index(i).prompt) for i in range(box.option_count)]
    return box.border_title, lines


async def test_the_first_jobs_machines_show_at_once() -> None:
    """After loading, the box lists the first job's machines."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert machines_box(app) == ('Machines of #1 (1)', ['gros-1'])


async def test_moving_onto_a_job_shows_its_machines() -> None:
    """The box follows the cursor: a waiting job has none yet."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('down')  # #2, waiting
        await pilot.pause()
        assert machines_box(app) == (
            'Machines of #2',
            ['None yet: the job is waiting for its start.'],
        )
        await pilot.press('down')  # #3, on two nova machines
        await pilot.pause()
        assert machines_box(app) == ('Machines of #3 (2)', ['nova-1', 'nova-2'])


async def test_no_jobs_no_machines() -> None:
    """With no jobs, the box says to move onto one."""
    app = JobsApp(alice({'nancy': [], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        assert machines_box(app) == (
            'Machines',
            ['Move onto a job to see its machines.'],
        )


# SSH to a machine

TWO_MACHINES = {
    **RUNNING,
    'uid': 8,
    'assigned_nodes': ['gros-1.nancy.grid5000.fr', 'gros-2.nancy.grid5000.fr'],
}
DEPLOYED = {**RUNNING, 'uid': 9, 'types': ['deploy']}


@pytest.fixture
def ran(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """The commands ssh.run was given; ssh is 'installed' and the app can
    step aside (as in a real terminal)."""
    commands: list[list[str]] = []
    monkeypatch.setattr(ssh, 'run', lambda command: commands.append(command) or 0)
    monkeypatch.setattr(ssh, 'ssh_available', lambda: True)
    monkeypatch.setattr(App, 'suspend', lambda self: nullcontext())
    return commands


async def test_s_opens_ssh_on_the_jobs_first_machine(ran: list[list[str]]) -> None:
    """s on a running job: SSH to its site, and from there to its first machine."""
    app = JobsApp(alice({'nancy': [TWO_MACHINES], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('s')
        await pilot.pause()
    assert ran == [
        ['ssh', '-t', '-J', 'alice@access.grid5000.fr', 'alice@nancy', 'ssh', 'gros-1']
    ]


async def test_enter_on_a_machine_in_the_list_opens_ssh_on_it(
    ran: list[list[str]],
) -> None:
    """Tab into the Machines list, go to the second machine, Enter: SSH there."""
    app = JobsApp(alice({'nancy': [TWO_MACHINES], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('tab')
        assert app.focused is app.query_one('#job-machines')
        await pilot.press('down', 'enter')
        await pilot.pause()
    assert ran and ran[0][-2:] == ['ssh', 'gros-2']


async def test_s_in_the_machines_list_uses_the_machine_highlighted(
    ran: list[list[str]],
) -> None:
    """s while the Machines list has the focus opens its highlighted machine."""
    app = JobsApp(alice({'nancy': [TWO_MACHINES], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('tab', 'down', 's')
        await pilot.pause()
    assert ran and ran[0][-2:] == ['ssh', 'gros-2']


async def test_a_deploy_job_is_reached_as_root_from_the_frontend(
    ran: list[list[str]],
) -> None:
    """A job of type deploy (your own system): root on the machine, via the site."""
    app = JobsApp(alice({'nancy': [DEPLOYED], 'lyon': []}))
    async with app.run_test(size=(120, 30)) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('s')
        await pilot.pause()
    assert ran and ran[0][-3:] == ['alice@nancy', 'ssh', 'root@gros-1']


async def test_a_waiting_job_has_nothing_to_ssh_to(ran: list[list[str]]) -> None:
    """s on a waiting job warns and runs nothing."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('down', 's')  # #2, waiting
        await pilot.pause()
        assert ran == []
        assert [n.severity for n in app._notifications] == ['warning']


async def test_a_finished_jobs_machines_cant_be_reached(ran: list[list[str]]) -> None:
    """A finished job's machines are no longer yours: nothing is run."""
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('down', 'down', 's')  # #3, terminated
        await pilot.pause()
        assert ran == []
        [note] = app._notifications
        assert 'running job' in note.message


async def test_without_a_terminal_it_shows_the_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where the app can't step aside, the command is shown instead."""

    def no_suspend(self: App) -> None:
        raise SuspendNotSupported

    monkeypatch.setattr(ssh, 'ssh_available', lambda: True)
    monkeypatch.setattr(App, 'suspend', no_suspend)
    app = JobsApp(alice())
    async with app.run_test(size=(120, 30), notifications=True) as pilot:
        await shown(app, pilot)
        table(app).focus()
        await pilot.press('s')
        await pilot.pause()
        [note] = app._notifications
        assert 'alice@nancy ssh gros-1' in note.message


def test_machines_are_short_names_in_number_order() -> None:
    """Machines lose their domain, appear once, and gros-2 comes before gros-10."""
    nodes = [
        'gros-10.nancy.grid5000.fr',
        'gros-2.nancy.grid5000.fr',
        'gros-2.nancy.grid5000.fr',
        'grisou-1.nancy.grid5000.fr',
    ]
    assert machines(job(assigned_nodes=nodes)) == ['grisou-1', 'gros-2', 'gros-10']
    assert machine_order('gros-2') < machine_order('gros-10')


def test_a_finished_job_with_no_machines() -> None:
    """A finished job that never ran on any machine says so."""
    title, text = machines_text(job(uid=5, state='error'))
    assert (title, text) == ('Machines of #5', 'None: the job never ran on any.')


# Cancelling a job


def cancelling_client(sent: list, jobs: dict | None = None) -> Client:
    """alice's jobs on the fake API, which also takes DELETEs."""
    fake = fake_grid5000(SITES, jobs=JOBS if jobs is None else jobs)

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == 'DELETE':
            return httpx.Response(202, json={})
        return fake.handler(request)

    return Client(user='alice', transport=httpx.MockTransport(handle))


async def cursor_on(app: App, pilot: Pilot, uid: int) -> None:
    """Show the jobs, and put the cursor on job uid."""
    await shown(app, pilot)
    t = table(app)
    t.focus()
    row = next(i for i in range(t.row_count) if str(t.get_row_at(i)[1]) == f'#{uid}')
    t.move_cursor(row=row)
    await settle(app, pilot)


async def test_x_asks_then_cancels_the_job() -> None:
    """x on the waiting job: a question; yes sends DELETE and reloads."""
    sent: list = []
    app = JobsApp(cancelling_client(sent))
    async with app.run_test(size=(140, 30)) as pilot:
        await cursor_on(app, pilot, 2)
        await pilot.press('x')
        await settle(app, pilot)
        assert isinstance(app.screen, Confirm)
        assert '#2' in str(app.screen.question)
        sent.clear()
        await pilot.click('#yes')
        await settle(app, pilot)
        deletes = [r for r in sent if r.method == 'DELETE']
        assert [r.url.path for r in deletes] == ['/stable/sites/nancy/jobs/2']
        assert any(r.method == 'GET' for r in sent)  # the list again


async def test_saying_no_keeps_the_job() -> None:
    """x, then Esc: nothing is sent."""
    sent: list = []
    app = JobsApp(cancelling_client(sent))
    async with app.run_test(size=(140, 30)) as pilot:
        await cursor_on(app, pilot, 1)
        await pilot.press('x')
        await settle(app, pilot)
        await pilot.press('escape')
        await settle(app, pilot)
        assert not isinstance(app.screen, Confirm)
        assert not [r for r in sent if r.method == 'DELETE']


async def test_a_finished_job_cant_be_cancelled() -> None:
    """x on a finished job: no question, nothing sent."""
    sent: list = []
    app = JobsApp(cancelling_client(sent))
    async with app.run_test(size=(140, 30)) as pilot:
        await cursor_on(app, pilot, 3)
        await pilot.press('x')
        await settle(app, pilot)
        assert not isinstance(app.screen, Confirm)
        assert not [r for r in sent if r.method == 'DELETE']


def test_the_cancel_button_is_red_until_the_job_ends() -> None:
    """Red while the job can be cancelled; grey and struck out once it ended."""
    running = Job.from_api(RUNNING, 'nancy')
    finished = Job.from_api(FINISHED, 'lyon')
    assert CANCEL_COLOUR in str(cancel_button(running).style)
    assert 'strike' in str(cancel_button(finished).style)
    assert CANCEL_COLOUR not in str(cancel_button(finished).style)


async def click_cancel(app: App, pilot: Pilot, uid: int) -> None:
    """Click the Cancel cell of job uid's row."""
    t = table(app)
    row = next(i for i in range(t.row_count) if str(t.get_row_at(i)[1]) == f'#{uid}')
    # the Cancel column starts after every other column (and their padding)
    columns = list(t.columns.values())
    x = sum(c.get_render_width(t) for c in columns[:-1]) + 2
    await pilot.click(JobsTable, offset=(x, row + 1))  # + 1: the header
    await settle(app, pilot)


async def test_clicking_cancel_asks_then_cancels() -> None:
    """A click on the waiting job's Cancel: the question; yes sends DELETE."""
    sent: list = []
    app = JobsApp(cancelling_client(sent))
    async with app.run_test(size=(140, 30)) as pilot:
        await shown(app, pilot)
        await click_cancel(app, pilot, 2)
        assert isinstance(app.screen, Confirm)
        assert '#2' in app.screen.question
        await pilot.click('#yes')
        await settle(app, pilot)
        deletes = [r.url.path for r in sent if r.method == 'DELETE']
        assert deletes == ['/stable/sites/nancy/jobs/2']
        assert app.chosen == []  # the click didn't open the job


async def test_a_grey_cancel_does_nothing() -> None:
    """A click on a finished job's Cancel: no question, nothing sent."""
    sent: list = []
    app = JobsApp(cancelling_client(sent))
    async with app.run_test(size=(140, 30)) as pilot:
        await shown(app, pilot)
        await click_cancel(app, pilot, 3)
        assert not isinstance(app.screen, Confirm)
        assert not [r for r in sent if r.method == 'DELETE']
