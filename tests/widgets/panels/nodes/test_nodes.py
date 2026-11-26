"""Tests for the Nodes panel: the table of a cluster's nodes, and how it reads."""

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Label

from grid_tui.grid5000 import Client
from grid_tui.models import Node
from grid_tui.widgets.panels.nodes import NodesPanel
from grid_tui.widgets.panels.nodes.nodes import (
    COLUMNS,
    HINT,
    disks,
    gpus,
    network,
    row,
    size,
)
from tests.grid5000.fakes import fake_client, g5k_client
from tests.widgets.panels.helpers import rows, settle

GIB = 1024**3

# a node with every kind of hardware, as the API might give it
CHIFFLOT_1 = {
    'uid': 'chifflot-1',
    'cluster': 'chifflot',
    'architecture': {'nb_procs': 2, 'nb_cores': 24, 'nb_threads': 48},
    'processor': {'other_description': 'Intel Xeon Gold 6126', 'clock_speed': 2.6e9},
    'main_memory': {'ram_size': 192 * GIB},
    'storage_devices': [
        {'device': 'sda', 'storage': 'SSD', 'size': 447 * GIB},
        {'device': 'sdb', 'storage': 'HDD', 'size': 1792 * GIB},
    ],
    'network_adapters': [
        {'device': 'eth0', 'interface': 'Ethernet', 'rate': 25e9, 'mounted': True},
        {'device': 'eth1', 'interface': 'Ethernet', 'rate': 25e9, 'mounted': False},
        {'device': 'ib0', 'interface': 'InfiniBand', 'rate': 100e9, 'mounted': True},
    ],
    'gpu_devices': {
        '0': {'vendor': 'Nvidia', 'model': 'Tesla P100'},
        '1': {'vendor': 'Nvidia', 'model': 'Tesla P100'},
    },
}


class NodesApp(App):
    """A tiny app that shows only the NodesPanel, to test it on its own."""

    def __init__(
        self, client: Client, site: str | None = None, cluster: str | None = None
    ) -> None:
        """Make the app.

        Args:
            client: What the panel loads the nodes from.
            site: The site of the cluster the panel starts on.
            cluster: The cluster the panel starts on; None for none.
        """
        super().__init__()
        self.client = client
        self.site = site
        self.cluster = cluster

    def compose(self) -> ComposeResult:
        """The only widget: the Nodes panel."""
        yield NodesPanel(self.client, site=self.site, cluster=self.cluster)


def table(app: App) -> DataTable:
    """The panel's table of nodes."""
    return app.query_one(NodesPanel).query_one(DataTable)


def title(app: App) -> Label:
    """The line above the table: which cluster, or how to choose one."""
    return app.query_one('#nodes-title', Label)


# The table


async def test_with_no_cluster_it_says_how_to_choose_one() -> None:
    """With no cluster, the table is empty and the title says what to do."""
    app = NodesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert table(app).row_count == 0
        assert str(title(app).render()) == HINT


async def test_made_with_a_cluster_shows_its_nodes() -> None:
    """A panel made with a cluster shows a row per node, and names the cluster."""
    app = NodesApp(g5k_client(), site='nancy', cluster='gros')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert [r[0] for r in rows(table(app))] == ['gros-1', 'gros-2']
        assert str(title(app).render()) == 'nancy / gros'
        assert title(app).has_class('-chosen')


async def test_has_the_columns() -> None:
    """The columns are the node's name and its hardware."""
    app = NodesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        labels = [str(c.label) for c in table(app).columns.values()]
        assert labels == list(COLUMNS)
        assert labels[:3] == ['Node', 'CPU', 'GHz']


async def test_show_cluster_switches_cluster() -> None:
    """show_cluster() loads that cluster's nodes and names it."""
    app = NodesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(NodesPanel).show_cluster('nancy', 'gros')
        await settle(app, pilot)
        assert table(app).row_count == 2
        assert str(title(app).render()) == 'nancy / gros'


async def test_a_row_shows_the_nodes_hardware() -> None:
    """A node's row has its CPU, cores, RAM, disks, network and GPUs."""
    client = fake_client(nodes={('lille', 'chifflot'): [CHIFFLOT_1]})
    app = NodesApp(client, site='lille', cluster='chifflot')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert rows(table(app)) == [
            [
                'chifflot-1',
                'Intel Xeon Gold 6126',
                '2.6',
                '24',
                '48',
                '192 GiB',
                '447 GiB SSD, 1.75 TiB HDD',
                '25 Gb/s, 100 Gb/s IB',
                '2× Tesla P100',
            ]
        ]


async def test_an_error_shows_a_notification_and_an_empty_table() -> None:
    """A failed load shows a red toast and leaves the table empty."""
    app = NodesApp(g5k_client(status=401), site='nancy', cluster='gros')
    async with app.run_test(notifications=True) as pilot:
        await settle(app, pilot)
        assert table(app).row_count == 0
        [note] = app._notifications
        assert note.severity == 'error'
        assert note.title == "Couldn't load nodes"


async def test_switching_to_a_failing_cluster_empties_the_table() -> None:
    """The rows of the last cluster don't stay when the next one fails."""
    app = NodesApp(g5k_client(), site='nancy', cluster='gros')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(NodesPanel).show_cluster('nancy', 'nowhere')  # a 404
        await settle(app, pilot)
        assert table(app).row_count == 0


async def test_loading_again_does_not_add_the_rows_twice() -> None:
    """Loading again replaces the rows instead of adding to them."""
    app = NodesApp(g5k_client(), site='nancy', cluster='gros')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(NodesPanel).load()
        await settle(app, pilot)
        assert table(app).row_count == 2


async def test_no_spinner_after_loading() -> None:
    """The spinner is gone once the nodes are in."""
    app = NodesApp(g5k_client(), site='nancy', cluster='gros')
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert app.query_one(NodesPanel).loading is False


# How the cells read


def test_size_picks_a_readable_unit() -> None:
    """Sizes are shown in TiB, GiB or MiB, and 0 is an empty cell."""
    assert size(96 * GIB) == '96 GiB'
    assert size(1792 * GIB) == '1.75 TiB'
    assert size(512 * 1024**2) == '512 MiB'
    assert size(0) == ''


def test_disks_lists_each_disk_with_its_kind() -> None:
    """Each disk is its size and SSD/HDD, separated by commas."""
    node = Node.model_validate(CHIFFLOT_1)
    assert disks(node) == '447 GiB SSD, 1.75 TiB HDD'


def test_network_lists_only_connected_cards_and_marks_infiniband() -> None:
    """Unplugged cards are left out; InfiniBand cards are marked IB."""
    assert network(Node.model_validate(CHIFFLOT_1)) == '25 Gb/s, 100 Gb/s IB'


def test_gpus_of_one_model_are_counted() -> None:
    """Several GPUs of the same model read as '2× Tesla P100'."""
    assert gpus(Node.model_validate(CHIFFLOT_1)) == '2× Tesla P100'


def test_gpus_of_different_models_are_listed() -> None:
    """GPUs of different models are listed one by one."""
    node = Node.model_validate(
        {'uid': 'x', 'gpu_devices': [{'model': 'A100'}, {'model': 'V100'}]}
    )
    assert gpus(node) == 'A100, V100'


def test_a_node_with_no_hardware_has_empty_cells() -> None:
    """A node the API says nothing about is its name and empty cells."""
    assert row(Node(uid='x')) == ('x', '', '', '', '', '', '', '', '')
