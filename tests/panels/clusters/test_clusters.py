from textual.app import App
from textual.widgets import DataTable, Label, Select

from grid_tui.panels.clusters import ClusterPanel
from tests.grid5000.fakes import g5k_client
from tests.panels.helpers import rows, settle


class ClustersApp(App):
    """A tiny app that shows only the ClusterPanel, to test it on its own."""

    def __init__(self, client, site: str | None = None) -> None:
        super().__init__()
        self.client = client
        self.site = site

    def compose(self):
        yield ClusterPanel(self.client, site=self.site)


def table(app: App) -> DataTable:
    return app.query_one(ClusterPanel).query_one(DataTable)


def dropdown(app: App) -> Select:
    return app.query_one('#site-select', Select)


def sites_shown(app: App) -> list[str]:
    """The site of every row, top to bottom."""
    return [row[0] for row in rows(table(app))]


# The table


async def test_shows_every_sites_clusters_by_default():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert rows(table(app)) == [
            ['nancy', 'gros', 'Dell R640', 'default', '', 'yes'],
            ['nancy', 'grisou', 'Dell R630', 'default, admin', '', ''],
            ['lyon', 'nova', 'Dell R430', 'default', 'yes', ''],
        ]


async def test_has_the_columns():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        labels = [str(c.label) for c in table(app).columns.values()]
        assert labels == ['Site', 'Cluster', 'Model', 'Queues', 'Exotic', 'KaVLAN']


async def test_made_with_a_site_shows_only_its_clusters():
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert sites_shown(app) == ['lyon']


async def test_show_site_switches_site():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site('nancy')
        await settle(app, pilot)
        assert sites_shown(app) == ['nancy', 'nancy']


async def test_show_site_none_shows_every_site_again():
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site(None)
        await settle(app, pilot)
        assert sites_shown(app) == ['nancy', 'nancy', 'lyon']


async def test_an_error_shows_a_notification_and_an_empty_table():
    app = ClustersApp(g5k_client(status=401))
    async with app.run_test(notifications=True) as pilot:
        await settle(app, pilot)
        assert table(app).row_count == 0
        [note] = app._notifications  # one: the dropdown keeps quiet
        assert note.severity == 'error'
        assert note.title == "Couldn't load clusters"


async def test_no_spinner_after_loading():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).loading is False


# The site dropdown


async def test_dropdown_starts_on_all_sites():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert dropdown(app).selection is None


async def test_dropdown_lists_every_site():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        select = dropdown(app)
        select.value = 'nancy'  # a site it lists can be picked...
        select.value = 'lyon'
        assert select.selection == 'lyon'


async def test_picking_a_site_in_the_dropdown_shows_its_clusters():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        dropdown(app).value = 'lyon'
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).site == 'lyon'
        assert sites_shown(app) == ['lyon']


async def test_picking_all_sites_shows_every_site():
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        dropdown(app).clear()  # back to 'All sites'
        await settle(app, pilot)
        assert app.query_one(ClusterPanel).site is None
        assert sites_shown(app) == ['nancy', 'nancy', 'lyon']


async def test_show_site_moves_the_dropdown():
    app = ClustersApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(ClusterPanel).show_site('nancy')
        await settle(app, pilot)
        assert dropdown(app).selection == 'nancy'


async def test_dropdown_shows_a_site_given_before_it_loaded():
    app = ClustersApp(g5k_client(), site='lyon')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert dropdown(app).selection == 'lyon'


async def test_dropdown_is_one_row_on_the_right():
    app = ClustersApp(g5k_client())
    async with app.run_test(size=(80, 20)) as pilot:
        await settle(app, pilot)
        panel = app.query_one(ClusterPanel).region
        select = dropdown(app).region
        label = app.query_one('#site-label', Label).region
        assert select.height == 1  # compact
        assert select.right == panel.right  # flush with the right edge
        assert label.right == select.x  # 'Site' just before it
        assert table(app).region.y > select.y  # above the table
