"""Tests for the Reservations panel: the timeline of a cluster on screen."""

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input, Label, Select, Static

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Client
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.panels.clusters import ClusterPanel
from grid_tui.widgets.panels.reservations import ReservationsPanel
from grid_tui.widgets.panels.reservations.reservations import HINT
from tests.grid5000.fakes import (
    CLUSTERS,
    NODES,
    SCHEDULE,
    SCHEDULE_NOW,
    SITES,
    fake_grid5000,
)
from tests.widgets.panels.helpers import settle


def client(user: str = 'alice', seen: list | None = None) -> Client:
    """A client on the fake API, with gros's reservations."""
    return Client(
        user=user,
        transport=fake_grid5000(
            SITES,
            CLUSTERS,
            nodes=NODES,
            schedules={('nancy', 'gros'): SCHEDULE},
            seen=seen,
        ),
    )


class PanelApp(App):
    """A tiny app with only the Reservations panel, at a fixed time."""

    def __init__(self, site: str | None = None, cluster: str | None = None) -> None:
        """Make the app, on a cluster or none."""
        super().__init__()
        self.site, self.cluster = site, cluster

    def compose(self) -> ComposeResult:
        """The only widget: the panel."""
        yield ReservationsPanel(
            client(), self.site, self.cluster, now=lambda: SCHEDULE_NOW
        )


def panel(app: App) -> ReservationsPanel:
    """The panel."""
    return app.query_one(ReservationsPanel)


def static(app: App, widget_id: str) -> str:
    """A Static's text."""
    return str(app.query_one(widget_id, Static).render())


async def test_without_a_cluster_it_says_how_to_choose_one() -> None:
    """With no cluster, the hint shows and there are no rows."""
    app = PanelApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert str(app.query_one('#res-title', Label).render()) == HINT
        assert app.query_one(DataTable).row_count == 0


async def test_a_cluster_shows_its_rows_and_free_nodes() -> None:
    """gros: four rows (alike nodes together), and 2 of 4 nodes free now."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        assert str(app.query_one('#res-title', Label).render()) == 'nancy / gros'
        assert app.query_one(DataTable).row_count == 4
        assert static(app, '#res-free').strip().startswith('2/4 free')


async def test_the_highlighted_row_shows_its_reservations() -> None:
    """On gros-1…2: your job 11, running, on 2 nodes."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        details = static(app, '#res-details')
        assert '#11 yours' in details
        assert 'running' in details
        assert '2 nodes' in details


async def test_a_free_row_says_so() -> None:
    """Moving onto gros-4 (nothing reserved) says it's free."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.query_one(DataTable).move_cursor(row=2)
        await pilot.pause()
        assert 'free, nothing reserved' in static(app, '#res-details')


async def test_z_zooms_out_and_around() -> None:
    """z goes 24 h → 3 days → 7 days → 12 h; Z goes back."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        app.query_one(DataTable).focus()
        hours = []
        for _ in range(4):
            await pilot.press('z')
            hours.append(panel(app).hours)
        assert hours == [72, 168, 12, 24]
        await pilot.press('Z')
        assert panel(app).hours == 12
        assert '12 h' in str(app.query_one('#res-zoom', Label).render())


async def test_reservations_are_remembered_a_minute_and_r_asks_again() -> None:
    """Loading again within a minute asks nothing; refresh (r) asks again."""
    seen: list = []

    class SeenApp(App):
        def compose(self) -> ComposeResult:
            yield ReservationsPanel(
                client(seen=seen), 'nancy', 'gros', now=lambda: SCHEDULE_NOW
            )

    app = SeenApp()
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        panel(app).load()
        await settle(app, pilot)
        asked = [r for r in seen if r.url.path.endswith('/gros/status')]
        assert len(asked) == 1
        panel(app).load(refresh=True)
        await settle(app, pilot)
        asked = [r for r in seen if r.url.path.endswith('/gros/status')]
        assert len(asked) == 2


async def test_finding_a_slot_marks_it_and_says_when() -> None:
    """2 nodes × 2 h: a slot now, marked on the timeline, in night time."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one('#slot-nodes', Input).value = '2'
        app.query_one('#slot-hours', Input).value = '2'
        await pilot.pause()
        summary = static(app, '#res-summary')
        assert 'Slot now · 2 × 2 h · night: free use' in summary
        assert '┣' in static(app, '#res-slot')  # it starts now: ┣ wins over ┃


async def test_no_slot_says_why() -> None:
    """5 nodes can't be free (one of five is down): it says so."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one('#slot-nodes', Input).value = '5'
        app.query_one('#slot-hours', Input).value = '1'
        await pilot.pause()
        assert 'No slot: fewer than 5 nodes are up' in static(app, '#res-summary')
        assert '┣' not in static(app, '#res-slot')


async def test_moving_through_time() -> None:
    """] moves a quarter later, [ earlier, n back to now."""
    app = PanelApp('nancy', 'gros')
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one(DataTable).focus()
        start = panel(app).window().start
        await pilot.press('right_square_bracket')
        assert panel(app).window().start == start + 6 * 3600  # 24 h / 4
        await pilot.press('left_square_bracket', 'left_square_bracket')
        assert panel(app).window().start == start - 6 * 3600
        await pilot.press('n')
        assert panel(app).window().start == start


async def test_picking_a_cluster_in_the_tab() -> None:
    """Picking nancy then gros in the dropdowns shows gros's reservations."""
    app = PanelApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.query_one('#res-site', Select).value = 'nancy'
        await settle(app, pilot)
        app.query_one('#res-cluster', Select).value = 'gros'
        await settle(app, pilot)
        assert (panel(app).site, panel(app).cluster) == ('nancy', 'gros')
        assert app.query_one(DataTable).row_count == 4


# In the app


async def test_4_opens_the_tab_and_a_chosen_cluster_shows_there() -> None:
    """Choosing gros in Clusters makes the Reservations tab about gros."""
    app = Grid5KApp(client())
    async with app.run_test(size=(120, 30)) as pilot:
        await settle(app, pilot)
        clusters = app.query_one(ClusterPanel).query_one(DataTable)
        keys = [row.key.value for row in clusters.ordered_rows]
        clusters.focus()
        clusters.move_cursor(row=keys.index('nancy/gros'))
        await pilot.press('enter')
        await settle(app, pilot)
        await pilot.press('4')
        await settle(app, pilot)
        assert app.query_one(MainTabs).active == 'reservations'
        assert (panel(app).site, panel(app).cluster) == ('nancy', 'gros')
        assert app.query_one(ReservationsPanel).query_one(DataTable).row_count == 4
