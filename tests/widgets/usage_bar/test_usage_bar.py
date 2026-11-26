"""Tests for UsageBar: the policy period, your usage and how busy it is."""

from datetime import datetime

from textual.app import App, ComposeResult

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Client
from grid_tui.my_usage import MyUsage
from grid_tui.policy import PARIS
from grid_tui.widgets.usage_bar import UsageBar, bar
from grid_tui.widgets.usage_bar.usage_bar import TABS_WIDTH, jobs_text
from tests.grid5000.fakes import fake_grid5000, g5k_client
from tests.widgets.panels.helpers import settle

THURSDAY_10 = datetime(2026, 11, 26, 10, 0, tzinfo=PARIS)


def test_bar() -> None:
    """The bar fills with the percentage, and is never longer than its width."""
    assert bar(0).plain == '░░░░░░░░'
    assert bar(50).plain == '████░░░░'
    assert bar(100).plain == '████████'
    assert bar(250).plain == '████████'


def test_bar_is_green_until_the_quota_is_used_up() -> None:
    """Green while under 100%, red from 100%."""
    assert '#a6e3a1' in str(bar(60).spans[0].style)
    assert '#f38ba8' in str(bar(100).spans[0].style)


def test_jobs_text() -> None:
    """What you run, in a few words."""
    assert jobs_text(MyUsage(jobs=1, cores=32)) == '1 job, 32 cores'
    assert jobs_text(MyUsage(jobs=2, cores=8)) == '2 jobs, 8 cores'
    assert jobs_text(MyUsage(waiting=1)) == '1 waiting'
    assert jobs_text(MyUsage()) == 'no jobs'


class BarApp(App):
    """A tiny app with only the usage line, at a fixed time."""

    def compose(self) -> ComposeResult:
        """The only widget: the usage line, on Thursday at 10:00."""
        yield UsageBar(g5k_client(), clock=lambda: THURSDAY_10)


def text(app: App) -> str:
    """The usage line as plain text."""
    return str(app.query_one(UsageBar).render())


async def test_shows_the_period_your_usage_and_how_busy() -> None:
    """Day until 19:00, your quota and jobs, and G5K 67% busy."""
    app = BarApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        line = text(app)
        assert line.startswith('Day · until 19:00')
        assert 'You' in line and '0% quota · no jobs' in line
        assert line.endswith('G5K 67% busy')


async def test_sits_in_the_top_right_corner() -> None:
    """Its right edge is the screen's right edge, on the top row."""
    app = BarApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        region = app.query_one(UsageBar).region
        assert region.y == 0
        assert region.right == 120


async def test_a_narrow_screen_shows_less_and_keeps_clear_of_the_tabs() -> None:
    """At 80 columns, details go before the line runs into the tabs."""
    app = BarApp()
    async with app.run_test(size=(80, 10)) as pilot:
        await settle(app, pilot)
        assert 'G5K' not in text(app)
        assert app.query_one(UsageBar).region.x >= TABS_WIDTH


async def test_if_the_api_fails_it_says_so() -> None:
    """Logged in, but with every call failing: the numbers show as '?'."""

    class FailingApp(App):
        def compose(self) -> ComposeResult:
            client = Client(user='alice', transport=fake_grid5000(status=500))
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    app = FailingApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        assert 'You ?' in text(app)
        assert 'G5K ?' in text(app)


async def test_the_tabs_stay_full_width_and_clickable() -> None:
    """In the app the line takes no room: the tabs still fill the screen."""
    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        from grid_tui.widgets.main_tabs import MainTabs

        tabs = app.query_one(MainTabs)
        assert tabs.region.width >= 116  # the screen less its border
        await pilot.click('Tab#--content-tab-clusters')
        assert tabs.active == 'clusters'


async def test_show_site_switches_to_that_site() -> None:
    """After show_site('lyon'), the line says how busy lyon is."""
    app = BarApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        app.query_one(UsageBar).show_site('lyon')
        await settle(app, pilot)
        assert text(app).endswith('lyon 50% busy')
        app.query_one(UsageBar).show_site(None)
        await settle(app, pilot)
        assert text(app).endswith('G5K 67% busy')


async def test_choosing_a_site_in_the_app_follows_it() -> None:
    """Choosing nancy in the Sites tab makes the line about nancy."""
    from textual.widgets import DataTable

    from grid_tui.widgets.panels.sites import SitesPanel

    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert text(app).endswith('G5K 67% busy')
        table = app.query_one(SitesPanel).query_one(DataTable)
        table.focus()
        table.move_cursor(row=0)  # nancy
        await pilot.press('enter')
        await settle(app, pilot)
        assert text(app).endswith('nancy 75% busy')
