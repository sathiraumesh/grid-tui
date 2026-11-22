"""Reservations › My reservations: your jobs on every site, cancelling one,
and opening one's cluster."""

from __future__ import annotations

from textual.widgets import DataTable

from grid_tui.app import GridTUI
from grid_tui.panels import JobsPanel
from grid_tui.screens import ConfirmDialog
from tests.fakes import TWO_SITES, FakeClient, settle, status

SIZE = (150, 40)

# The fake API's jobs for bob: 4521 running on gros-2 at nancy, 9001 waiting
# (not placed yet) at rennes.


async def open_jobs(pilot) -> JobsPanel:
    await settle(pilot)
    await pilot.press("6")
    await settle(pilot)
    assert pilot.app.screen.active == "mine"
    return pilot.app.screen.mine


def rows(panel: JobsPanel) -> list[list[str]]:
    t = panel.query_one(DataTable)
    return [[str(c) for c in t.get_row_at(i)] for i in range(t.row_count)]


async def test_lists_your_jobs_on_every_site() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        panel = await open_jobs(pilot)
        got = rows(panel)
        assert [r[:4] for r in got] == [["nancy", "4521", "exp", "Running"], ["rennes", "9001", "later", "Waiting"]]
        assert got[0][6:8] == ["3h", "1 × gros"] and got[1][7] == "-"
        assert panel.table.border_title == "my reservations: 2 · bob"
        assert "jobs?user=bob&state=waiting,launching,running" in panel.table.border_subtitle


async def test_x_cancels_after_a_yes() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await open_jobs(pilot)
        await pilot.press("x")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog) and "Cancel job #4521 at nancy" in app.screen.question
        await pilot.press("n")
        await settle(pilot)
        assert client.cancelled == []
        await pilot.press("x")
        await pilot.pause()
        await pilot.click("#yes")
        await settle(pilot)
        assert client.cancelled == [4521]


async def test_enter_opens_the_jobs_cluster_reservations() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await open_jobs(pilot)
        await pilot.press("enter")  # 4521 on gros
        await settle(pilot)
        assert app.screen.active == "current" and app.screen.current.cluster.uid == "gros"


async def test_a_job_not_placed_yet_has_no_cluster_to_open() -> None:
    app = GridTUI(FakeClient(TWO_SITES))
    async with app.run_test(size=SIZE) as pilot:
        await open_jobs(pilot)
        await pilot.press("down", "enter")  # 9001: no nodes yet
        await settle(pilot)
        assert app.screen.active == "mine"


async def test_a_site_that_fails_is_said() -> None:
    client = FakeClient(TWO_SITES)
    app = GridTUI(client)
    async with app.run_test(size=SIZE) as pilot:
        await settle(pilot)
        client.jobs_error = RuntimeError("GET /sites/x/jobs: 500")
        await pilot.press("6")
        await settle(pilot)
        assert status(app).startswith("not every site answered: nancy: GET /sites/x/jobs: 500")
