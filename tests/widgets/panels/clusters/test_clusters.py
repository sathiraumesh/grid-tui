"""Tests for the Clusters panel: the table of clusters and the site dropdown."""

from contextlib import nullcontext

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, DataTable, Label, Select

from grid_tui.grid5000 import Client
from grid_tui.utils import ssh
from grid_tui.widgets.panels.clusters import ClusterPanel
from tests.grid5000.fakes import CLUSTERS, SITES, fake_grid5000, g5k_client
from tests.widgets.panels.helpers import rows, settle


class ClustersApp(App):
    """A tiny app that shows only the ClusterPanel, to test it on its own."""

    def on_cluster_panel_chosen(self, message: ClusterPanel.Chosen) -> None:
        """Keep each cluster the panel says was chosen."""
        self.chosen.append((message.site, message.cluster))

    def __init__(self, client: Client, site: str | None = None) -> None:
        """Make the app.

        Args:
            client: What the panel loads from.
            site: The site the panel starts on; None for every site.
        """
        super().__init__()
        self.client = client
        self.site = site
        self.chosen: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        """The only widget: the Clusters panel."""
        yield ClusterPanel(self.client, site=self.site)


def table(app: App) -> DataTable:
    """The panel's table of clusters."""
    return app.query_one(ClusterPanel).query_one(DataTable)


def dropdown(app: App) -> Select:
    """The panel's site dropdown."""
    return app.query_one('#site-select', Select)


def sites_shown(app: App) -> list[str]:
    """The site of every row, top to bottom."""
    return [row[0] for row in rows(table(app))]


# The table


async def test_shows_every_sites_clusters_by_default() -> None:
    """With no site, every site's clusters show, with their values."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert rows(table(app)) == [
            ['nancy', 'gros', 'Dell R640', 'default', '', 'yes'],
            ['nancy', 'grisou', 'Dell R630', 'default, admin', '', ''],
            ['lyon', 'nova', 'Dell R430', 'default', 'yes', ''],
        ]


async def test_has_the_columns() -> None:
    """The columns are Site, Cluster, Model, Queues, Exotic and KaVLAN."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        labels = [str(c.label) for c in table(app).columns.values()]
        assert labels == ['Site', 'Cluster', 'Model', 'Queues', 'Exotic', 'KaVLAN']


async def test_made_with_a_site_shows_only_its_clusters() -> None:
    """A panel made with site='lyon' shows only Lyon's clusters."""
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert sites_shown(app) == ['lyon']


async def test_show_site_switches_site() -> None:
    """show_site() switches the table to that site."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site('nancy')
        await settle(app, pilot)
        assert sites_shown(app) == ['nancy', 'nancy']


async def test_show_site_none_shows_every_site_again() -> None:
    """show_site(None) goes back to every site."""
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site(None)
        await settle(app, pilot)
        assert sites_shown(app) == ['nancy', 'nancy', 'lyon']


async def test_an_error_shows_a_notification_and_an_empty_table() -> None:
    """A failed load shows one red toast and leaves the table empty."""
    app = ClustersApp(g5k_client(status=401))
    async with app.run_test(notifications=True) as pilot:
        await settle(app, pilot)
        assert table(app).row_count == 0
        [note] = app._notifications  # one: the dropdown keeps quiet
        assert note.severity == 'error'
        assert note.title == "Couldn't load clusters"


async def test_no_spinner_after_loading() -> None:
    """The spinner is gone once the clusters are in."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).loading is False


# The site dropdown


async def test_dropdown_starts_on_all_sites() -> None:
    """The dropdown starts on 'All sites'."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert dropdown(app).selection is None


async def test_dropdown_lists_every_site() -> None:
    """Every site can be picked in the dropdown."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        select = dropdown(app)
        select.value = 'nancy'  # a site it lists can be picked...
        select.value = 'lyon'
        assert select.selection == 'lyon'


async def test_picking_a_site_in_the_dropdown_shows_its_clusters() -> None:
    """Picking a site in the dropdown shows only its clusters."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        dropdown(app).value = 'lyon'
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).site == 'lyon'
        assert sites_shown(app) == ['lyon']


async def test_picking_all_sites_shows_every_site() -> None:
    """Picking 'All sites' shows every site's clusters again."""
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        dropdown(app).clear()  # back to 'All sites'
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).site is None
        assert sites_shown(app) == ['nancy', 'nancy', 'lyon']


async def test_show_site_moves_the_dropdown() -> None:
    """show_site() also shows that site in the dropdown."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site('nancy')
        await settle(app, pilot)
        assert dropdown(app).selection == 'nancy'


async def test_dropdown_shows_a_site_given_before_it_loaded() -> None:
    """A site given before the dropdown had loaded is shown once it has."""
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert dropdown(app).selection == 'lyon'


async def test_dropdown_is_one_row_on_the_left() -> None:
    """The dropdown is one row, on the left, after 'Site', above the table."""
    app = ClustersApp(g5k_client())
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        panel = app.query_one(ClusterPanel).region
        select = dropdown(app).region
        label = app.query_one('#site-label', Label).region
        assert select.height == 1  # compact
        assert label.x == panel.x  # 'Site' starts at the left edge
        assert label.right == select.x  # the dropdown just after it
        assert table(app).region.y > select.y  # above the table


# Choosing a cluster


async def test_enter_on_a_row_sends_chosen_with_its_site_and_cluster() -> None:
    """Enter on a row sends Chosen with that row's site and cluster."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        table(app).focus()
        await pilot.press('down', 'down', 'enter')  # the third row: lyon / nova
        await pilot.pause()
        assert app.chosen == [('lyon', 'nova')]


# The SSH button, beside the site dropdown


def ssh_label(app: App) -> str:
    """The SSH button's text."""
    return str(app.query_one('#ssh-button', Button).label)


async def test_ssh_follows_the_dropdown() -> None:
    """With a site in the dropdown, the button connects to that site."""
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert ssh_label(app) == 'SSH lyon ›'


async def test_ssh_with_all_sites_follows_the_cursor() -> None:
    """With 'All sites', it's the highlighted cluster's site."""
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        table = app.query_one(DataTable)
        sites = [row[0] for row in rows(table)]
        assert ssh_label(app) == f'SSH {sites[0]} ›'
        last = len(sites) - 1
        table.move_cursor(row=last)
        await pilot.pause()
        assert ssh_label(app) == f'SSH {sites[last]} ›'


def logged_in(site: str | None = 'nancy') -> ClustersApp:
    """The panel on a site, with a client logged in as alice."""
    client = Client(user='alice', transport=fake_grid5000(SITES, CLUSTERS))
    return ClustersApp(client, site=site)


@pytest.fixture
def ran(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """The commands ssh.run was given; ssh is 'installed' and the app can
    step aside (as in a real terminal)."""
    commands: list[list[str]] = []
    monkeypatch.setattr(ssh, 'run', lambda command: commands.append(command) or 0)
    monkeypatch.setattr(ssh, 'ssh_available', lambda: True)
    monkeypatch.setattr(App, 'suspend', lambda self: nullcontext())
    return commands


async def test_s_runs_ssh_to_the_site(ran: list[list[str]]) -> None:
    """s runs ssh through the gateway to the dropdown's site."""
    app = logged_in('nancy')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(DataTable).focus()
        await pilot.press('s')
        await pilot.pause()
    assert ran == [['ssh', '-J', 'alice@access.grid5000.fr', 'alice@nancy']]


async def test_the_button_runs_ssh_too(ran: list[list[str]]) -> None:
    """Clicking SSH does the same as s."""
    app = logged_in('lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        await pilot.click('#ssh-button')
        await pilot.pause()
    assert ran and ran[0][-1] == 'alice@lyon'


async def test_a_failed_connection_says_what_to_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ssh's 255 (couldn't connect) shows a hint about the SSH key."""
    monkeypatch.setattr(ssh, 'run', lambda command: ssh.SSH_FAILED)
    monkeypatch.setattr(ssh, 'ssh_available', lambda: True)
    monkeypatch.setattr(App, 'suspend', lambda self: nullcontext())
    app = logged_in()
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).action_ssh()
        await pilot.pause()
        assert any('SSH key' in n.message for n in app._notifications)


async def test_without_a_terminal_it_shows_the_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Where the app can't step aside (as in tests), it shows what to run."""
    monkeypatch.setattr(ssh, 'ssh_available', lambda: True)
    app = logged_in()
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).action_ssh()
        await pilot.pause()
        assert any('ssh -J' in n.message for n in app._notifications)


async def test_no_ssh_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an ssh command, it says to install OpenSSH."""
    monkeypatch.setattr(ssh, 'ssh_available', lambda: False)
    app = logged_in()
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).action_ssh()
        await pilot.pause()
        assert any('OpenSSH' in n.message for n in app._notifications)
