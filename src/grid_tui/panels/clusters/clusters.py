"""The Clusters panel: a table of every Grid'5000 cluster, or one site's."""

from pathlib import Path

import httpx
from textual import on, work
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, Label, Select

from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Cluster


class ClusterPanel(Widget):
    """A table of clusters, loaded from the API: every site's, or one site's."""

    DEFAULT_CSS = (Path(__file__).parent / 'clusters.tcss').read_text()

    def __init__(self, client: Client, site: str | None = None, **kwargs) -> None:
        """Make the panel.

        Args:
            client: Where to load the clusters from.
            site: Show only this site's clusters, e.g. 'nancy';
                None shows the clusters of every site.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.site = site
        self._dropdown_sites: set[str] = set()  # the sites the dropdown has

    def compose(self):
        """The panel's widgets: a site dropdown on the right, then the table."""
        with Horizontal(id='toolbar'):
            yield Label('Site', id='site-label')
            yield Select(
                [], prompt='All sites', allow_blank=True, compact=True, id='site-select'
            )
        yield DataTable(cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Add the columns and start loading, once the panel is shown."""
        self.query_one(DataTable).add_columns(
            'Site', 'Cluster', 'Model', 'Queues', 'Exotic', 'KaVLAN'
        )
        self.load_sites()
        self.load()

    def show_site(self, site: str | None) -> None:
        """Switch to one site's clusters (or every site's, with None) and load.

        Args:
            site: The site's uid, e.g. 'nancy'; None for every site.
        """
        self.site = site
        self._select_site(site)
        self.load()

    def _select_site(self, site: str | None) -> None:
        """Show site in the dropdown (if the dropdown has it yet)."""
        select = self.query_one('#site-select', Select)
        if site is None:
            select.clear()
        elif site in self._dropdown_sites:
            select.value = site

    @on(Select.Changed, '#site-select')
    def _dropdown_changed(self, event: Select.Changed) -> None:
        """A site was picked in the dropdown: show its clusters."""
        site = event.select.selection  # None for 'All sites'
        if site != self.site:
            self.site = site
            self.load()

    @work(group='sites')
    async def load_sites(self) -> None:
        """Fill the dropdown with every site (an error is shown by load())."""
        try:
            sites = await self.client.sites.list()
        except (ApiError, httpx.HTTPError):
            return
        select = self.query_one('#site-select', Select)
        select.set_options((site.name or site.uid, site.uid) for site in sites)
        self._dropdown_sites = {site.uid for site in sites}
        self._select_site(self.site)  # a site may have been chosen meanwhile

    @work(exclusive=True)  # runs in the background; a new load cancels the old one
    async def load(self) -> None:
        """Fetch the clusters from the API and show them."""
        self.loading = True  # shows a spinner over the panel
        try:
            if self.site:
                by_site = {self.site: await self.client.sites.list_clusters(self.site)}
            else:
                by_site = await self.client.sites.all_clusters()
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load clusters", severity='error')
            return
        finally:
            self.loading = False
        self.show(by_site)

    def show(self, by_site: dict[str, list[Cluster]]) -> None:
        """Put the clusters in the table, site by site."""
        table = self.query_one(DataTable)
        table.clear()
        for site, clusters in by_site.items():
            for cluster in clusters:
                table.add_row(
                    site,
                    cluster.uid,
                    cluster.model,
                    ', '.join(cluster.queues),
                    'yes' if cluster.exotic else '',
                    'yes' if cluster.kavlan else '',
                    key=f'{site}/{cluster.uid}',
                )
