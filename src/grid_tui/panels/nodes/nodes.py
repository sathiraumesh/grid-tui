"""The Nodes panel: a table of a cluster's nodes and their hardware."""

from pathlib import Path

import httpx
from textual import work
from textual.widget import Widget
from textual.widgets import DataTable, Label

from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Node

HINT = 'Choose a cluster in the Clusters tab (Enter) to see its nodes.'
COLUMNS = ('Node', 'CPU', 'GHz', 'Cores', 'Threads', 'RAM', 'Disks', 'Network', 'GPUs')


def size(num_bytes: int) -> str:
    """A size in bytes, for a person: 96 GiB → '96 GiB', 2 TiB → '2 TiB'."""
    if num_bytes <= 0:
        return ''
    for unit, factor in (('TiB', 1024**4), ('GiB', 1024**3), ('MiB', 1024**2)):
        if num_bytes >= factor:
            return f'{num_bytes / factor:.3g} {unit}'
    return f'{num_bytes} B'


def number(value: float) -> str:
    """A number for the table: '' for 0, so empty cells stay empty."""
    return f'{value:g}' if value else ''


def disks(node: Node) -> str:
    """A node's disks in one cell, e.g. '447 GiB SSD, 1.75 TiB HDD'."""
    return ', '.join(
        ' '.join(part for part in (size(disk.size), disk.storage) if part)
        for disk in node.storage_devices
    )


def network(node: Node) -> str:
    """A node's connected cards in one cell, e.g. '25 Gb/s, 100 Gb/s IB'."""
    cards = []
    for card in node.connected_adapters:
        text = f'{card.gbps:g} Gb/s' if card.rate else card.device
        if card.interface == 'InfiniBand':
            text += ' IB'
        cards.append(text)
    return ', '.join(cards)


def gpus(node: Node) -> str:
    """A node's GPUs in one cell, e.g. '2× Tesla V100'."""
    if not node.gpu_devices:
        return ''
    models = [gpu.model or gpu.vendor or 'GPU' for gpu in node.gpu_devices]
    if len(set(models)) == 1:
        return f'{len(models)}× {models[0]}'
    return ', '.join(models)


def row(node: Node) -> tuple[str, ...]:
    """The table row of a node, in the order of COLUMNS."""
    return (
        node.uid,
        node.processor.name,
        number(round(node.processor.ghz, 2)),
        number(node.architecture.nb_cores),
        number(node.architecture.nb_threads),
        size(node.main_memory.ram_size) or size(round(node.ram_gib * 1024**3)),
        disks(node),
        network(node),
        gpus(node),
    )


class NodesPanel(Widget):
    """A table of one cluster's nodes and their hardware, loaded from the API."""

    DEFAULT_CSS = (Path(__file__).parent / 'nodes.tcss').read_text()

    def __init__(
        self,
        client: Client,
        site: str | None = None,
        cluster: str | None = None,
        **kwargs,
    ) -> None:
        """Make the panel.

        Args:
            client: Where to load the nodes from.
            site: The site of the cluster to show, e.g. 'nancy'.
            cluster: The cluster to show, e.g. 'gros'; with no cluster the
                panel says to choose one.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.site = site
        self.cluster = cluster

    def compose(self):
        """The panel's widgets: which cluster it is, then the table of nodes."""
        yield Label(HINT, id='nodes-title')
        yield DataTable(cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Add the columns, and load if a cluster was given."""
        self.query_one(DataTable).add_columns(*COLUMNS)
        self.load()

    def show_cluster(self, site: str, cluster: str) -> None:
        """Switch to a cluster's nodes and load them.

        Args:
            site: The cluster's site, e.g. 'nancy'.
            cluster: The cluster, e.g. 'gros'.
        """
        self.site = site
        self.cluster = cluster
        self.load()

    def _show_title(self) -> None:
        """Say which cluster is shown, or how to choose one."""
        title = self.query_one('#nodes-title', Label)
        if self.site and self.cluster:
            title.update(f'{self.site} / {self.cluster}')
            title.add_class('-chosen')
        else:
            title.update(HINT)
            title.remove_class('-chosen')

    @work(exclusive=True)  # runs in the background; a new load cancels the old one
    async def load(self) -> None:
        """Fetch the cluster's nodes from the API and show them."""
        self._show_title()
        if not (self.site and self.cluster):
            self.show([])
            return
        self.loading = True  # shows a spinner over the panel
        try:
            nodes = await self.client.nodes.list(self.site, self.cluster)
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load nodes", severity='error')
            self.show([])
            return
        finally:
            self.loading = False
        self.show(nodes)

    def show(self, nodes: list[Node]) -> None:
        """Put nodes in the table, one row each."""
        table = self.query_one(DataTable)
        table.clear()
        for node in nodes:
            table.add_row(*row(node), key=node.uid)
