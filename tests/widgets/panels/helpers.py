"""Helpers for the panel tests."""

from textual.app import App
from textual.pilot import Pilot
from textual.widgets import DataTable


async def settle(app: App, pilot: Pilot) -> None:
    """Wait until every background load has finished and the screen is drawn."""
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


def rows(table: DataTable) -> list[list]:
    """Every row of table, top to bottom."""
    return [table.get_row_at(i) for i in range(table.row_count)]
