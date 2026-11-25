from textual.app import App
from textual.widgets import DataTable

from grid_tui.panels.sites import SitesPanel
from tests.grid5000.fakes import g5k_client
from tests.panels.helpers import rows, settle


class SitesApp(App):
    """A tiny app that shows only the SitesPanel, and keeps the sites chosen."""

    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
        self.chosen: list[str] = []

    def compose(self):
        yield SitesPanel(self.client)

    def on_sites_panel_chosen(self, message: SitesPanel.Chosen) -> None:
        self.chosen.append(message.site)


async def test_shows_a_row_per_site():
    app = SitesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert rows(app.query_one(DataTable)) == [
            ['nancy', 'Nancy', 'Grid5000 Nancy site'],
            ['lyon', 'Lyon', 'Grid5000 Lyon site'],
        ]


async def test_has_the_columns():
    app = SitesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        columns = app.query_one(DataTable).columns.values()
        assert [str(c.label) for c in columns] == ['Site', 'Name', 'Description']


async def test_no_spinner_after_loading():
    app = SitesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert app.query_one(SitesPanel).loading is False


async def test_an_error_shows_a_notification_and_an_empty_table():
    app = SitesApp(g5k_client(status=401))
    async with app.run_test(notifications=True) as pilot:
        await settle(app, pilot)
        assert app.query_one(DataTable).row_count == 0
        [note] = app._notifications
        assert note.severity == 'error'
        assert note.title == "Couldn't load sites"
        assert 'G5K_USER' in note.message


async def test_loading_again_does_not_add_the_rows_twice():
    app = SitesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(SitesPanel).load()
        await settle(app, pilot)
        assert app.query_one(DataTable).row_count == 2


async def test_enter_on_a_row_sends_chosen_with_its_site():
    app = SitesApp(g5k_client())
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.query_one(DataTable).focus()
        await pilot.press('down', 'enter')  # the second row: lyon
        await pilot.pause()
        assert app.chosen == ['lyon']
