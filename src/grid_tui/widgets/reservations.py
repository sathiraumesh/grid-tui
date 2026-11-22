"""The widget that shows a Gantt: it draws what fits its size."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from grid_tui.models import Gantt
from grid_tui.widgets.timeline import draw, window


class ReservationsView(Widget):
    """A cluster's reservations: the time line, the week or the month."""

    DEFAULT_CSS = """
    ReservationsView { height: 1fr; }
    """

    def __init__(self, gantt: Gantt | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.gantt = gantt

    def show(self, gantt: Gantt | None) -> None:
        self.gantt = gantt
        self.refresh()

    def render(self) -> Text:
        if self.gantt is None:
            return Text("nothing to show yet", style="dim")
        width, height = self.size.width or 100, self.size.height or 30
        lines, pinned, focus = draw(self.gantt, width)
        return Text("\n").join(window(lines, pinned, focus, height))
