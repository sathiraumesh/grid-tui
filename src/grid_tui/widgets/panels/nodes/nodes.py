"""The Nodes panel: a table of a cluster's nodes and their hardware."""

import asyncio
from pathlib import Path
from typing import Any

import httpx
from textual import on, work
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

from grid_tui.format import number, size
from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Cluster, MetricInfo, Node
from grid_tui.widgets.popups.node_details import NodeDetails

HINT = 'Choose a cluster in the Clusters tab (Enter) to see its nodes.'
COLUMNS = ('Node', 'CPU', 'GHz', 'Cores', 'Threads', 'RAM', 'Disks', 'Network', 'GPUs')


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
        **kwargs: Any,
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
        self.nodes: dict[str, Node] = {}  # the nodes in the table, by uid
        self.cluster_info: Cluster | None = None  # the cluster, for its metrics

    def compose(self) -> ComposeResult:
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
    async def load(self, refresh: bool = False) -> None:
        """Fetch the cluster's nodes and show them: from the cache, once saved.

        Args:
            refresh: Ask the API again instead of using the cache (the r key).
        """
        self._show_title()
        if not (self.site and self.cluster):
            self.show([])
            return
        self.loading = True  # shows a spinner over the panel
        self.cluster_info = None
        try:
            # the nodes, and the cluster (for its metrics), at the same time
            nodes, cluster = await asyncio.gather(
                self.client.nodes.list(self.site, self.cluster, refresh=refresh),
                self._cluster_or_none(self.site, self.cluster, refresh=refresh),
            )
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load nodes", severity='error')
            self.show([])
            return
        finally:
            self.loading = False
        self.cluster_info = cluster
        self.show(nodes)

    async def _cluster_or_none(
        self, site: str, cluster: str, *, refresh: bool = False
    ) -> Cluster | None:
        """The cluster, or None if it can't be loaded: the nodes still show."""
        try:
            return await self.client.sites.get_cluster(site, cluster, refresh=refresh)
        except (ApiError, httpx.HTTPError):
            return None

    def show(self, nodes: list[Node]) -> None:
        """Put nodes in the table, one row each."""
        self.nodes = {node.uid: node for node in nodes}
        table = self.query_one(DataTable)
        table.clear()
        for node in nodes:
            table.add_row(*row(node), key=node.uid)

    @on(DataTable.RowSelected)
    def _node_chosen(self, event: DataTable.RowSelected) -> None:
        """A row was chosen (Enter, or a click): show all of that node's details."""
        node = self.nodes.get(event.row_key.value)
        if node is not None:
            self.app.push_screen(NodeDetails(node, self.metrics_for(node)))

    def metrics_for(self, node: Node) -> tuple[MetricInfo, ...]:
        """What node can measure: its cluster's metrics for it; () if unknown."""
        if self.cluster_info is None:
            return ()
        return self.cluster_info.metrics_for(node.uid)
