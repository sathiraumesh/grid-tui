"""The Search panel: find the clusters whose nodes meet some hardware needs.

The nodes of every cluster are loaded in the background the first time the
tab is shown (that also lists the GPU models to choose from), and kept, so
searches are instant. load() (the r key) loads them again.
"""

import asyncio
from pathlib import Path
from typing import Any, TypeVar

import httpx
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select

from grid_tui.format import number, size
from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Cluster, Node
from grid_tui.panels.nodes.nodes import disks, gpus
from grid_tui.requirements import (
    ANY_GPU,
    DISK_TYPES,
    Match,
    Requirements,
    gpu_models,
    has_wattmeter,
    search,
)

HINT = 'Set what a node needs, then Search (or Enter in a box).'
GPU_LOADING = 'GPU models load in the background…'
COLUMNS = (
    'Site',
    'Cluster',
    'Nodes',
    'CPU',
    'Cores',
    'RAM',
    'GPUs',
    'Disks',
    'Wattmeter',
)

Found = dict[tuple[str, str], tuple[Cluster, list[Node]]]


def match_row(match: Match) -> tuple[str, ...]:
    """The table row of a match: its cluster, and its first good node's hardware."""
    node = match.nodes[0]
    return (
        match.site,
        match.cluster.uid,
        f'{len(match.nodes)}/{match.total}',  # good nodes / all nodes
        node.processor.name,
        number(node.architecture.nb_cores),
        size(round(node.ram_gib * 1024**3)),
        gpus(node),
        disks(node),
        'yes' if has_wattmeter(node, match.cluster) else '',
    )


NumberT = TypeVar('NumberT', int, float)  # what a form box is read as


class SearchPanel(Widget):
    """A form of hardware needs, and the clusters whose nodes meet them."""

    DEFAULT_CSS = (Path(__file__).parent / 'search.tcss').read_text()

    class Chosen(Message):
        """Sent when a cluster is chosen in the results (Enter, or a click)."""

        def __init__(self, site: str, cluster: str) -> None:
            """Make the message.

            Args:
                site: The chosen cluster's site, e.g. 'nancy'.
                cluster: The chosen cluster's uid, e.g. 'gros'.
            """
            super().__init__()
            self.site = site
            self.cluster = cluster

    def __init__(self, client: Client, **kwargs: Any) -> None:
        """Make the panel.

        Args:
            client: Where to load the sites, clusters and nodes from.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.found: Found | None = None  # every cluster's nodes, once loaded
        self._load_task: asyncio.Task | None = None  # the loading, while it runs
        self.matches: list[Match] = []
        self.searched = False  # has a search been run

    def compose(self) -> ComposeResult:
        """The form on two short lines, a status line, then the results."""
        with Horizontal(id='search-form', classes='form-row'):
            yield Label('Cores ≥', classes='form-label')
            yield Input(placeholder='0', type='integer', compact=True, id='min-cores')
            yield Label('RAM ≥', classes='form-label')
            yield Input(placeholder='0', type='number', compact=True, id='min-ram')
            yield Label('GiB', classes='form-label')
            yield Checkbox('Wattmeter', id='need-wattmeter')
            yield Button('Search', compact=True, id='search-button')
        with Horizontal(id='search-where', classes='form-row'):
            yield Label('GPU', classes='form-label')
            yield Select(
                [('Any GPU', ANY_GPU)],
                prompt='No need',
                allow_blank=True,
                compact=True,
                id='need-gpu',
            )
            yield Label('Disk', classes='form-label')
            yield Select(
                [(kind, kind) for kind in DISK_TYPES],
                prompt='Any',
                allow_blank=True,
                compact=True,
                id='need-disk',
            )
            yield Label('Site', classes='form-label')
            yield Select(
                [], prompt='All sites', allow_blank=True, compact=True, id='search-site'
            )
        yield Label(HINT, id='search-status')
        yield DataTable(cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Add the columns, and fill the site list."""
        self.query_one(DataTable).add_columns(*COLUMNS)
        self.load_sites()

    def on_show(self) -> None:
        """The tab is shown: start loading the nodes, for the GPU list."""
        if self.found is None and self._load_task is None:
            self.preload()

    @work(group='search-preload')
    async def preload(self) -> None:
        """Load every cluster's nodes ahead of a search; errors wait for it."""
        try:
            await self._ensure_loaded()
        except (ApiError, httpx.HTTPError):
            pass  # a search will try again, and say what went wrong

    async def _ensure_loaded(self) -> Found:
        """Every cluster's nodes: loaded once, then kept.

        A search and the preload share one loading, so nothing loads twice, and
        stopping a search doesn't stop the loading.
        """
        if self.found is not None:
            return self.found
        if self._load_task is None:
            self._load_task = asyncio.ensure_future(self._load_everything())
        task = self._load_task
        try:
            found = await asyncio.shield(task)
        except (ApiError, httpx.HTTPError):
            if self._load_task is task:
                self._load_task = None  # so the next try loads again
            raise
        if self._load_task is task:
            self.found = found
            self._load_task = None
            self._fill_gpu_list(found)
        return found

    def _fill_gpu_list(self, found: Found) -> None:
        """List the GPU models found, after 'Any GPU', keeping what was picked."""
        select = self.query_one('#need-gpu', Select)
        picked = select.selection
        models = gpu_models(found)
        select.set_options(
            [('Any GPU', ANY_GPU), *((model, model) for model in models)]
        )
        if picked == ANY_GPU or picked in models:
            select.value = picked

    @work(group='search-sites')
    async def load_sites(self) -> None:
        """Fill the site list (an error is shown when searching)."""
        try:
            sites = await self.client.sites.list()
        except (ApiError, httpx.HTTPError):
            return
        select = self.query_one('#search-site', Select)
        select.set_options((site.name or site.uid, site.uid) for site in sites)

    def requirements(self) -> Requirements:
        """What the form asks for. An empty or odd box is no need."""

        def read(box_id: str, kind: type[NumberT]) -> NumberT:
            text = self.query_one(box_id, Input).value.strip()
            try:
                return max(kind(text), 0) if text else 0
            except ValueError:
                return 0

        return Requirements(
            min_cores=read('#min-cores', int),
            min_ram_gib=read('#min-ram', float),
            gpu=self.query_one('#need-gpu', Select).selection,
            disk=self.query_one('#need-disk', Select).selection,
            wattmeter=self.query_one('#need-wattmeter', Checkbox).value,
            site=self.query_one('#search-site', Select).selection,
        )

    @on(Button.Pressed, '#search-button')
    @on(Input.Submitted)
    def _search_asked(self) -> None:
        """Search was pressed, or Enter in a box: run the search."""
        self.run_search()

    def load(self) -> None:
        """Forget what was loaded; search again if a search was run (the r key)."""
        self.found = None
        self._load_task = None
        if self.searched:
            self.run_search()
        elif self.is_on_screen:
            self.preload()

    @work(exclusive=True)  # a new search cancels the one before
    async def run_search(self) -> None:
        """Load every cluster's nodes (the first time), then show the matches."""
        self.searched = True
        status = self.query_one('#search-status', Label)
        if self.found is None:
            self.loading = True  # shows a spinner over the panel
            status.update('Loading the nodes of every cluster…')
            try:
                await self._ensure_loaded()
            except (ApiError, httpx.HTTPError) as error:
                self.notify(str(error), title="Couldn't search", severity='error')
                self.show([])  # first, so its 'no match' line is replaced below
                status.update("Couldn't load the clusters. Press r to try again.")
                return
            finally:
                self.loading = False
        self.show(search(self.found, self.requirements()))

    async def _load_everything(self) -> Found:
        """Every cluster of every site, and its nodes, at the same time.

        A cluster whose nodes can't be loaded is left out, and a warning says
        how many were; if the clusters themselves can't be loaded, it raises.
        """
        by_site = await self.client.sites.all_clusters()
        clusters = [(site, c) for site, cs in by_site.items() for c in cs]
        answers = await asyncio.gather(
            *(self.client.nodes.list(site, c.uid) for site, c in clusters),
            return_exceptions=True,
        )
        found: Found = {}
        failed = 0
        for (site, cluster), answer in zip(clusters, answers):
            if isinstance(answer, (ApiError, httpx.HTTPError)):
                failed += 1
            elif isinstance(answer, BaseException):
                raise answer  # not an API problem: don't hide it
            else:
                found[(site, cluster.uid)] = (cluster, answer)
        if failed:
            self.notify(
                f"Couldn't load the nodes of {failed} cluster(s); "
                'they are left out of the results.',
                title='Some clusters missing',
                severity='warning',
            )
        return found

    def show(self, matches: list[Match]) -> None:
        """Put the matches in the table, and say how many there are."""
        self.matches = matches
        table = self.query_one(DataTable)
        table.clear()
        for match in matches:
            table.add_row(*match_row(match), key=f'{match.site}/{match.cluster.uid}')
        if self.searched:
            nodes = sum(len(match.nodes) for match in matches)
            self.query_one('#search-status', Label).update(
                f'{len(matches)} cluster(s), {nodes} node(s) match.'
                if matches
                else 'No cluster has a node that meets all of that.'
            )

    @on(DataTable.RowSelected)
    def _cluster_chosen(self, event: DataTable.RowSelected) -> None:
        """A result was chosen: tell the app which cluster it is."""
        site, cluster = event.row_key.value.split('/', 1)  # the key is 'site/cluster'
        self.post_message(self.Chosen(site, cluster))
