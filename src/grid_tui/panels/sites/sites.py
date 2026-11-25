"""The Sites panel: a table of every Grid'5000 site."""

from pathlib import Path

import httpx
from textual import on, work
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from grid_tui.grid5000 import ApiError, Client
from grid_tui.models import Site


class SitesPanel(Widget):
    """A table of every Grid'5000 site, loaded from the API."""

    DEFAULT_CSS = (Path(__file__).parent / 'sites.tcss').read_text()

    class Chosen(Message):
        """Sent when a site is chosen in the table (Enter, or a click)."""

        def __init__(self, site: str) -> None:
            """Make the message.

            Args:
                site: The chosen site's uid, e.g. 'nancy'.
            """
            super().__init__()
            self.site = site

    def __init__(self, client: Client, **kwargs) -> None:
        """Make the panel.

        Args:
            client: Where to load the sites from.
            **kwargs: Passed on to Widget, e.g. id or classes.
        """
        super().__init__(**kwargs)
        self.client = client

    def compose(self):
        """The panel's widgets: one table, one row per site."""
        yield DataTable(cursor_type='row', zebra_stripes=True)

    def on_mount(self) -> None:
        """Add the columns and start loading, once the panel is shown."""
        self.query_one(DataTable).add_columns('Site', 'Name', 'Description')
        self.load()

    @work(exclusive=True)  # runs in the background; a new load cancels the old one
    async def load(self) -> None:
        """Fetch the sites from the API and show them."""
        self.loading = True  # shows a spinner over the panel
        try:
            sites = await self.client.sites.list()
        except (ApiError, httpx.HTTPError) as error:
            self.notify(str(error), title="Couldn't load sites", severity='error')
            return
        finally:
            self.loading = False
        self.show(sites)

    def show(self, sites: list[Site]) -> None:
        """Put sites in the table."""
        table = self.query_one(DataTable)
        table.clear()
        for site in sites:
            table.add_row(site.uid, site.name, site.description, key=site.uid)

    @on(DataTable.RowSelected)
    def _site_chosen(self, event: DataTable.RowSelected) -> None:
        """A row was chosen: tell the app which site it is."""
        self.post_message(self.Chosen(event.row_key.value))
