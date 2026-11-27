"""The Clusters panel: a table of every Grid'5000 cluster, or one site's.

The quota is per cluster (2 h on all its cores, each working day), so the
table's last column is your share of today's quota on each cluster.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, Label, Select

from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Cluster
from grid_tui.my_usage import MyUsage, my_usage
from grid_tui.policy import PARIS
from grid_tui.utils import ssh
from grid_tui.widgets.usage_bar.usage_bar import MUTED, bar, level_colour

QUOTA_BAR = 6  # cells in each row's quota bar


def quota_cell(mine: MyUsage | None, key: str) -> Text:
    """Your quota on one cluster: '██░░░░ 30%'; '…' while it loads.

    Args:
        mine: Your usage (None: still loading).
        key: The cluster, as 'site/cluster'.
    """
    if mine is None:
        return Text('…', MUTED)
    if mine.quota_percent is None:
        return Text('no quota today', MUTED)  # a weekend or a holiday
    percent = mine.by_cluster.get(key, 0)
    text = bar(percent, QUOTA_BAR)
    text.append(f' {percent}%', level_colour(percent) if percent else MUTED)
    return text


class ClusterPanel(Widget):
    """A table of clusters, loaded from the API: every site's, or one site's."""

    DEFAULT_CSS = (Path(__file__).parent / 'clusters.tcss').read_text()
    BINDINGS = [Binding('s', 'ssh', 'SSH to site')]

    class Chosen(Message):
        """Sent when a cluster is chosen in the table (Enter, or a click)."""

        def __init__(self, site: str, cluster: str) -> None:
            """Make the message.

            Args:
                site: The chosen cluster's site, e.g. 'nancy'.
                cluster: The chosen cluster's uid, e.g. 'gros'.
            """
            super().__init__()
            self.site = site
            self.cluster = cluster

    def __init__(
        self,
        client: Client,
        site: str | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        **kwargs: Any,
    ) -> None:
        """Make the panel.

        Args:
            client: Where to load the clusters from.
            site: Show only this site's clusters, e.g. 'nancy';
                None shows the clusters of every site.
            clock: What gives the time now (for today's quota); tests pass
                a fixed one.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client
        self.site = site
        self.clock = clock or (lambda: datetime.now(PARIS))
        self.mine: MyUsage | None = None  # your usage on the clusters shown
        self._dropdown_sites: set[str] = set()  # the sites the dropdown has

    def compose(self) -> ComposeResult:
        """The panel's widgets: a site dropdown and the SSH button, then the table."""
        with Horizontal(id='toolbar'):
            yield Label('Site', id='site-label')
            yield Select(
                [], prompt='All sites', allow_blank=True, compact=True, id='site-select'
            )
            yield Button('SSH ›', compact=True, id='ssh-button')
        yield DataTable(cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Add the columns and start loading, once the panel is shown."""
        table = self.query_one(DataTable)
        table.add_columns('Site', 'Cluster', 'Model', 'Queues', 'Exotic', 'KaVLAN')
        table.add_column('Your quota', key='quota')
        self.load_sites()
        self.load()

    def show_site(self, site: str | None) -> None:
        """Switch to one site's clusters (or every site's, with None) and load.

        Args:
            site: The site's uid, e.g. 'nancy'; None for every site.
        """
        self.site = site
        self._select_site(site)
        self._update_ssh_label()
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
            self._update_ssh_label()
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
    async def load(self, refresh: bool = False) -> None:
        """Fetch the clusters and show them: from the cache, once they're saved.

        Args:
            refresh: Ask the API again instead of using the cache (the r key).
        """
        self.loading = True  # shows a spinner over the panel
        sites = self.client.sites
        try:
            if self.site:
                clusters = await sites.list_clusters(self.site, refresh=refresh)
                by_site = {self.site: clusters}
            else:
                by_site = await sites.all_clusters(refresh=refresh)
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load clusters", severity='error')
            return
        finally:
            self.loading = False
        self.show(by_site)
        self.load_quota(refresh=refresh)

    @work(exclusive=True, group='quota')
    async def load_quota(self, refresh: bool = False) -> None:
        """Fetch your usage on the site (or every site) and fill the quota column.

        Your jobs are remembered for a few minutes, so this mostly costs no
        request: the top-right line has just asked for them.

        Args:
            refresh: Ask the API again, not what was asked a moment ago (r).
        """
        self.mine = None
        self._fill_quota()
        site = self.site
        try:
            mine = await my_usage(self.client, self.clock(), site, refresh=refresh)
        except (ApiError, httpx.HTTPError):
            return  # the cells keep their '…'; the top-right line says '?'
        if site == self.site:  # still the same site
            self.mine = mine
            self._fill_quota()

    def _fill_quota(self) -> None:
        """Write your quota in every row's last cell."""
        try:
            table = self.query_one(DataTable)
        except NoMatches:
            return  # the app closed while your jobs were on their way
        for row in list(table.rows):
            table.update_cell(row, 'quota', quota_cell(self.mine, row.value))

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
                    quota_cell(self.mine, f'{site}/{cluster.uid}'),
                    key=f'{site}/{cluster.uid}',
                )
        self._update_ssh_label()

    def ssh_site(self) -> str | None:
        """The site the SSH button connects to: the dropdown's, else the cursor's.

        With 'All sites' in the dropdown, it is the highlighted cluster's site;
        None if there are no clusters yet.
        """
        if self.site:
            return self.site
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        return key.split('/', 1)[0]  # the key is 'site/cluster'

    @on(DataTable.RowHighlighted)
    def _update_ssh_label(self) -> None:
        """Name the site the SSH button connects to: 'SSH nancy ›'."""
        site = self.ssh_site()
        self.query_one('#ssh-button', Button).label = (
            f'SSH {site} ›' if site else 'SSH ›'
        )

    @on(Button.Pressed, '#ssh-button')
    def action_ssh(self) -> None:
        """Open a shell on the site's frontend (the s key, or the SSH button).

        The app steps aside while the session runs, and comes back when you
        leave it (exit, or Ctrl-D).
        """
        site = self.ssh_site()
        if site is None:
            return
        if not ssh.ssh_available():
            self.notify('Install OpenSSH to connect.', title='No ssh', severity='error')
            return
        command = ssh.ssh_command(site, self.client.sites.user)
        away = getattr(self.app, 'away', None)  # stop polling during the session
        try:
            if away:
                away(True)
            with self.app.suspend():
                code = ssh.run(command)
        except SuspendNotSupported:
            self.notify(
                'Run the app in a terminal to connect: ' + ' '.join(command),
                title="Can't open SSH here",
                severity='warning',
            )
            return
        finally:
            if away:
                away(False)
        if code == ssh.SSH_FAILED:
            self.notify(
                "Check that your SSH key is added to your Grid'5000 account.",
                title=f"Couldn't connect to {site}",
                severity='error',
            )
        self.query_one(DataTable).focus()

    @on(DataTable.RowSelected)
    def _cluster_chosen(self, event: DataTable.RowSelected) -> None:
        """A row was chosen: tell the app which cluster it is."""
        site, cluster = event.row_key.value.split('/', 1)  # the key is 'site/cluster'
        self.post_message(self.Chosen(site, cluster))
