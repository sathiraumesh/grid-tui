"""Tests for UsageBar: the policy period, your usage and how busy it is."""

from dataclasses import asdict
from datetime import datetime

import pytest
from textual.app import App, ComposeResult

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Client
from grid_tui.grid5000.cache import Cache
from grid_tui.my_usage import MyUsage
from grid_tui.policy import PARIS
from grid_tui.widgets.usage_bar import UsageBar, bar
from grid_tui.widgets.usage_bar.usage_bar import (
    SETTLE_SECONDS,
    TABS_WIDTH,
    jobs_text,
    level_colour,
)
from tests.grid5000.fakes import SITES, STATUS, fake_grid5000, g5k_client
from tests.widgets.panels.helpers import settle

THURSDAY_10 = datetime(2026, 11, 26, 10, 0, tzinfo=PARIS)


def test_bar() -> None:
    """The bar fills with the percentage, and is never longer than its width."""
    assert bar(0).plain == '░░░░░░░░'
    assert bar(50).plain == '████░░░░'
    assert bar(100).plain == '████████'
    assert bar(250).plain == '████████'


def test_bar_colour_follows_how_full_the_quota_is() -> None:
    """Green under half, yellow from 50%, orange from 80%, red once used up."""
    # the first span's colour (a partial cell is 'colour on grey')
    colours = {
        p: str(bar(p).spans[0].style).split(' on ')[0]
        for p in (10, 49, 50, 79, 80, 99, 100)
    }
    assert colours == {
        10: '#a6e3a1',
        49: '#a6e3a1',
        50: '#f9e2af',
        79: '#f9e2af',
        80: '#fab387',
        99: '#fab387',
        100: '#f38ba8',
    }


def test_level_colour() -> None:
    """The same colours as the bar, for the percentage beside it."""
    assert [level_colour(p) for p in (0, 60, 90, 150)] == [
        '#a6e3a1',
        '#f9e2af',
        '#fab387',
        '#f38ba8',
    ]


def test_the_percentage_has_the_bars_colour() -> None:
    """In the line, 'NN% quota' is the same colour as its bar."""
    line = UsageBar(g5k_client())
    line.mine = MyUsage(jobs=1, cores=8, quota_percent=85)
    text = line.line(0)
    start = text.plain.index('85% quota')
    styles = [str(span.style) for span in text.spans if span.start <= start < span.end]
    assert any('#fab387' in style for style in styles)


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
    """After show_site('lyon'), it says how busy lyon is, and all of Grid'5000."""
    app = BarApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        app.query_one(UsageBar).show_site('lyon')
        await settle(app, pilot)
        assert text(app).endswith('lyon 50% · G5K 67% busy')
        app.query_one(UsageBar).show_site(None)
        await settle(app, pilot)
        assert text(app).endswith('G5K 67% busy')


async def test_choosing_a_site_in_the_app_follows_it() -> None:
    """Choosing nancy in the Sites tab makes the line about nancy."""
    from textual.widgets import DataTable

    from grid_tui.widgets.panels.sites import SitesPanel

    app = Grid5KApp(g5k_client())
    # wide enough for the longest line beside all six tabs
    async with app.run_test(size=(140, 30)) as pilot:
        await settle(app, pilot)
        assert text(app).endswith('G5K 67% busy')
        table = app.query_one(SitesPanel).query_one(DataTable)
        table.focus()
        table.move_cursor(row=0)  # nancy
        await pilot.press('enter')
        await settle(app, pilot)
        assert text(app).endswith('nancy 75% · G5K 67% busy')


async def test_highlighting_a_site_shows_its_usage_without_opening_it() -> None:
    """A single click (or arrow key) on a site switches the line; the tab stays."""
    from textual.widgets import DataTable

    from grid_tui.widgets.main_tabs import MainTabs
    from grid_tui.widgets.panels.sites import SitesPanel

    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.query_one(SitesPanel).query_one(DataTable).focus()
        await pilot.press('down')  # onto lyon
        await settle(app, pilot)
        assert text(app).endswith('lyon 50% · G5K 67% busy')
        assert app.query_one(MainTabs).active == 'sites'  # didn't go inside


async def test_switching_site_shows_its_number_without_asking_again() -> None:
    """Every site's status is already loaded: switching asks for no status."""
    seen: list = []
    client = Client(transport=fake_grid5000(SITES, statuses=STATUS, seen=seen))

    class SeenApp(App):
        def compose(self) -> ComposeResult:
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    app = SeenApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        before = len([r for r in seen if r.url.path.endswith('/status')])
        bar_widget = app.query_one(UsageBar)
        bar_widget.site = 'lyon'  # what show_site sets, without a new load
        bar_widget.redraw()
        assert text(app).endswith('lyon 50% · G5K 67% busy')
        after = len([r for r in seen if r.url.path.endswith('/status')])
        assert after == before


async def test_a_narrow_screen_keeps_the_sites_number() -> None:
    """When space is short, G5K's number goes before the site's."""
    app = BarApp()
    async with app.run_test(size=(98, 10)) as pilot:
        await settle(app, pilot)
        app.query_one(UsageBar).show_site('lyon')
        await pilot.pause(SETTLE_SECONDS + 0.1)  # the cursor has stopped
        await settle(app, pilot)
        line = text(app)
        assert 'lyon 50%' in line
        assert 'G5K' not in line


def counting_client(seen: list) -> Client:
    """A logged-in client on the fake API, keeping the requests in seen."""
    return Client(
        user='alice',
        transport=fake_grid5000(SITES, statuses=STATUS, jobs={'nancy': []}, seen=seen),
    )


async def test_moving_through_sites_asks_once_the_cursor_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Five quick site changes: your usage is worked out once, for the last site."""
    from grid_tui.widgets.usage_bar import usage_bar as module

    asked: list = []
    real = module.my_usage

    async def counting(client: Client, now: datetime, site: str | None = None, **kw):  # noqa: ANN202, ANN003
        asked.append(site)
        return await real(client, now, site, **kw)

    monkeypatch.setattr(module, 'my_usage', counting)
    client = counting_client([])

    class QuickApp(App):
        def compose(self) -> ComposeResult:
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    app = QuickApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        asked.clear()
        usage_bar = app.query_one(UsageBar)
        for site in ('nancy', 'lyon', 'nancy', 'lyon', 'nancy'):
            usage_bar.show_site(site)
        await pilot.pause(SETTLE_SECONDS + 0.2)
        await settle(app, pilot)
        assert asked == ['nancy']


async def test_nothing_is_asked_while_the_app_is_in_the_background() -> None:
    """With polling off, a tick only redraws; it loads again once polling is on."""
    seen: list = []
    client = counting_client(seen)

    class AwayApp(App):
        polling = False

        def compose(self) -> ComposeResult:
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    app = AwayApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        usage_bar = app.query_one(UsageBar)
        usage_bar._busy_at = usage_bar._mine_at = 0.0  # everything is old
        before = len(seen)
        usage_bar._tick()
        await settle(app, pilot)
        assert len(seen) == before
        AwayApp.polling = True
        usage_bar._tick()
        await settle(app, pilot)
        assert len(seen) > before


async def test_the_app_stops_polling_in_the_background() -> None:
    """Blur (terminal in the background) or an SSH session: no polling."""
    app = Grid5KApp(g5k_client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert app.polling
        app.on_app_blur()
        assert not app.polling
        app.on_app_focus()
        app.away(True)
        assert not app.polling
        app.away(False)
        assert app.polling


def test_a_small_share_still_shows_a_coloured_sliver() -> None:
    """3% is a thin coloured sliver, not an empty bar."""
    small = bar(3)
    assert small.plain == '▎░░░░░░░'
    assert small.plain.count('░') == 7
    assert '#a6e3a1' in str(small.spans[0].style)  # green


def test_any_use_shows_at_least_an_eighth() -> None:
    """1% still shows the thinnest sliver; 0% is empty."""
    assert bar(1).plain[0] == '▏'
    assert bar(0).plain == '░' * 8


def test_the_bar_is_drawn_in_eighths() -> None:
    """Halfway through a cell is a half block; the bar stays 8 cells wide."""
    assert bar(25).plain == '██░░░░░░'
    assert bar(31).plain == '██▌░░░░░'  # 2.48 cells: 2 full, then half a cell
    assert all(len(bar(p).plain) == 8 for p in range(0, 130, 3))


def saved_usage_app(cache: Cache, status: int = 500) -> App:
    """A usage line whose API answers with status, saving into cache."""

    class SavedApp(App):
        def compose(self) -> ComposeResult:
            client = Client(
                user='alice', transport=fake_grid5000(status=status), cache=cache
            )
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    return SavedApp()


async def test_your_usage_from_earlier_today_shows_at_once() -> None:
    """The quota last loaded today shows before (here: without) the API."""
    cache = Cache(':memory:')
    saved = {'day': '2026-11-26', **asdict(MyUsage(jobs=1, cores=8, quota_percent=37))}
    cache.put('grid-tui:my-usage:*', saved)
    app = saved_usage_app(cache)
    async with app.run_test(size=(140, 10)) as pilot:
        await settle(app, pilot)
        assert '37% quota · 1 job, 8 cores …' in text(app)


async def test_yesterdays_usage_isnt_shown() -> None:
    """The quota starts again each day: yesterday's saved one is ignored."""
    cache = Cache(':memory:')
    saved = {'day': '2026-11-25', **asdict(MyUsage(quota_percent=37))}
    cache.put('grid-tui:my-usage:*', saved)
    app = saved_usage_app(cache)
    async with app.run_test(size=(140, 10)) as pilot:
        await settle(app, pilot)
        assert '37%' not in text(app)
        assert 'You ?' in text(app)


async def test_your_usage_is_saved_once_loaded() -> None:
    """A loaded usage is saved for today, and shown without the '…'."""
    cache = Cache(':memory:')
    app = saved_usage_app(cache, status=200)
    async with app.run_test(size=(140, 10)) as pilot:
        await settle(app, pilot)
        assert '…' not in text(app)
    saved = cache.get('grid-tui:my-usage:*')
    assert saved is not None and saved['day'] == '2026-11-26'
