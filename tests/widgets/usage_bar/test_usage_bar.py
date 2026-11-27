"""Tests for UsageBar: the policy period, your usage and how busy it is."""

from datetime import datetime

from textual.app import App, ComposeResult

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Client
from grid_tui.policy import PARIS
from grid_tui.widgets.usage_bar import UsageBar, bar
from grid_tui.widgets.usage_bar.usage_bar import (
    TABS_WIDTH,
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


class BarApp(App):
    """A tiny app with only the usage line, at a fixed time."""

    def compose(self) -> ComposeResult:
        """The only widget: the usage line, on Thursday at 10:00."""
        yield UsageBar(g5k_client(), clock=lambda: THURSDAY_10)


def text(app: App) -> str:
    """The usage line as plain text."""
    return str(app.query_one(UsageBar).render())


async def test_shows_the_period_and_how_busy() -> None:
    """Day until 19:00, and G5K 67% busy; your quota is in the Clusters tab."""
    app = BarApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
        line = text(app)
        assert line.startswith('Day · until 19:00')
        assert 'You' not in line and 'quota' not in line
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
    """At 60 columns, when the period ends goes before the line runs into the tabs."""
    app = BarApp()
    async with app.run_test(size=(60, 10)) as pilot:
        await settle(app, pilot)
        assert 'until' not in text(app)
        assert 'G5K 67%' in text(app)
        assert app.query_one(UsageBar).region.x >= TABS_WIDTH


async def test_if_the_api_fails_it_says_so() -> None:
    """With every call failing, the numbers show as '?'."""

    class FailingApp(App):
        def compose(self) -> ComposeResult:
            client = Client(user='alice', transport=fake_grid5000(status=500))
            yield UsageBar(client, clock=lambda: THURSDAY_10)

    app = FailingApp()
    async with app.run_test(size=(120, 10)) as pilot:
        await settle(app, pilot)
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
    async with app.run_test(size=(64, 10)) as pilot:
        await settle(app, pilot)
        app.query_one(UsageBar).show_site('lyon')
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
        usage_bar._busy_at = 0.0  # it's old
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
