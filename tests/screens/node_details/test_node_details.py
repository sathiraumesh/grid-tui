"""Tests for the node details pop-up: its sections, and opening and closing it."""

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from grid_tui.models import MetricInfo, Node
from grid_tui.panels.nodes import NodesPanel
from grid_tui.screens.node_details import NodeDetails, sections
from grid_tui.screens.node_details.node_details import metric_text
from tests.grid5000.fakes import NODES, fake_client, g5k_client
from tests.models.test_node import GROS_12
from tests.panels.helpers import settle

WATTMETRE = MetricInfo(
    name='wattmetre_power_watt',
    description='Power from the wattmeter',
    period=1000,
    optional_period=20,
)


def section(found: list, title: str) -> dict[str, str]:
    """The rows of the section with this title, as {label: value}."""
    return dict(dict(found)[title])


# What the sections hold


def test_a_full_node_has_every_section_in_order() -> None:
    """A node with every detail has every section, in a fixed order."""
    titles = [title for title, _ in sections(Node.model_validate(GROS_12))]
    assert titles == [
        'Node',
        'Processor',
        'Memory',
        'Disks',
        'Network',
        'Performance',
        'Jobs',
        'System settings',
        'Monitoring',
        'Power',
        'BIOS',
        'Machine',
    ]


def test_an_empty_node_has_only_what_it_knows() -> None:
    """Sections with nothing in them are left out."""
    titles = [title for title, _ in sections(Node(uid='x'))]
    assert titles == ['Node', 'Jobs', 'System settings', 'Monitoring']


def test_the_processor_section() -> None:
    """The processor's details read for a person."""
    rows = section(sections(Node.model_validate(GROS_12)), 'Processor')
    assert rows['Model'] == 'Intel Xeon Gold 5220'
    assert rows['Clock'] == '2.2 GHz'
    assert (rows['Sockets'], rows['Cores'], rows['Threads']) == ('1', '18', '36')


def test_the_memory_section_lists_the_modules() -> None:
    """Memory has the total RAM, then each module."""
    rows = section(sections(Node.model_validate(GROS_12)), 'Memory')
    assert rows == {'RAM': '96 GiB', 'dimm_a0': '64 GiB', 'dimm_b0': '32 GiB'}


def test_the_network_section_says_which_cards_are_connected() -> None:
    """Each card says if it is connected."""
    rows = section(sections(Node.model_validate(GROS_12)), 'Network')
    assert rows['eth0'] == 'Ethernet · 25 Gb/s · connected'
    assert rows['eth1'] == 'Ethernet · not connected'


def test_the_jobs_section() -> None:
    """Jobs reads yes/no, and 0 as no limit."""
    rows = section(sections(Node.model_validate(GROS_12)), 'Jobs')
    assert rows['Deploy your own system'] == 'yes'
    assert rows['Virtualisation'] == 'ivt'
    assert rows['Longest job'] == 'no limit'
    assert rows['Queues'] == 'default, admin'


def test_rows_with_no_value_are_left_out() -> None:
    """A detail the API didn't give has no row."""
    rows = section(sections(Node(uid='x', cluster='gros')), 'Node')
    assert rows == {'Name': 'x', 'Cluster': 'gros'}  # no 'Exotic' row


# The Metrics section


def test_metrics_section_lists_what_the_node_can_measure() -> None:
    """Each metric is a row: its name, what it is and how often."""
    found = sections(Node(uid='gros-1'), (WATTMETRE,))
    expected = 'Power from the wattmeter · every 1 s (20 ms on request)'
    assert section(found, 'Metrics') == {'wattmetre_power_watt': expected}


def test_no_metrics_no_section() -> None:
    """With no metrics, there is no Metrics section."""
    assert 'Metrics' not in dict(sections(Node(uid='x')))


def test_metric_text() -> None:
    """A metric reads as its description and period, whichever it has."""
    assert metric_text(MetricInfo(name='x', description='Power')) == 'Power'
    assert metric_text(MetricInfo(name='x', period=5000)) == 'every 5 s'
    assert metric_text(MetricInfo(name='x')) == '—'


# Opening and closing it


class DetailsApp(App):
    """A tiny app that opens the pop-up for a node at once."""

    def __init__(self, node: Node, metrics: tuple[MetricInfo, ...] = ()) -> None:
        """Make the app.

        Args:
            node: The node to show.
            metrics: What it can measure.
        """
        super().__init__()
        self.node = node
        self.metrics = metrics

    def on_mount(self) -> None:
        """Open the pop-up."""
        self.push_screen(NodeDetails(self.node, self.metrics))


async def test_shows_the_nodes_name_and_section_titles() -> None:
    """The frame names the node; each section has its title."""
    app = DetailsApp(Node.model_validate(GROS_12), (WATTMETRE,))
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, NodeDetails)
        assert app.screen.query_one('#details').border_title == 'gros-12'
        titles = [str(label.render()) for label in app.screen.query('.section-title')]
        assert titles[:3] == ['Node', 'Processor', 'Memory']
        assert 'Metrics' in titles


async def test_escape_closes_it() -> None:
    """Esc closes the pop-up."""
    app = DetailsApp(Node(uid='x'))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert not isinstance(app.screen, NodeDetails)


async def test_q_closes_it_instead_of_quitting() -> None:
    """q closes the pop-up and leaves the app running."""
    app = DetailsApp(Node(uid='x'))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('q')
        await pilot.pause()
        assert not isinstance(app.screen, NodeDetails)
        assert app.is_running


# From the Nodes panel


class NodesApp(App):
    """A tiny app with a Nodes panel on Nancy's gros cluster."""

    def compose(self) -> ComposeResult:
        """The only widget: the Nodes panel."""
        yield NodesPanel(g5k_client(), site='nancy', cluster='gros')


async def test_enter_on_a_node_opens_its_details_with_its_metrics() -> None:
    """Enter on a node opens the pop-up, with that node's metrics."""
    app = NodesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(app, pilot)
        app.query_one(NodesPanel).query_one(DataTable).focus()
        await pilot.press('enter')  # gros-1
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NodeDetails)
        assert screen.node.uid == 'gros-1'
        assert [m.name for m in screen.metrics] == [
            'wattmetre_power_watt',
            'bmc_node_power_watt',
        ]


async def test_a_metric_only_for_other_nodes_is_left_out() -> None:
    """gros-2 isn't in the wattmeter's only_for: it gets only the BMC metric."""
    app = NodesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await settle(app, pilot)
        app.query_one(NodesPanel).query_one(DataTable).focus()
        await pilot.press('down', 'enter')  # gros-2
        await pilot.pause()
        assert [m.name for m in app.screen.metrics] == ['bmc_node_power_watt']


class NoClusterApp(App):
    """A Nodes panel whose cluster can't be loaded: the fake API has no clusters."""

    def compose(self) -> ComposeResult:
        """The only widget: the Nodes panel on gros, whose cluster is a 404."""
        yield NodesPanel(fake_client(nodes=NODES), site='nancy', cluster='gros')


async def test_nodes_still_show_if_the_cluster_cant_be_loaded() -> None:
    """If the cluster (for its metrics) fails, the nodes show, with no metrics."""
    app = NoClusterApp()
    async with app.run_test(notifications=True) as pilot:
        await settle(app, pilot)
        panel = app.query_one(NodesPanel)
        assert panel.query_one(DataTable).row_count == 2
        assert panel.cluster_info is None
        assert panel.metrics_for(panel.nodes['gros-1']) == ()
        assert list(app._notifications) == []  # no error: the nodes loaded
