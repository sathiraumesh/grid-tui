"""A pop-up that asks before doing something that can't be undone.

app.push_screen(Confirm('Cancel job #42?', 'It stops now.'), callback)
# callback(True) for yes, callback(False) for no (or Esc)
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class Confirm(ModalScreen[bool]):
    """A question, what it means, and two buttons: yes (red) and no."""

    DEFAULT_CSS = (Path(__file__).parent / 'confirm.tcss').read_text()
    BINDINGS = [
        Binding('escape', 'no', 'No'),
        Binding('y', 'yes', 'Yes', show=False),
        Binding('n', 'no', 'No', show=False),
    ]

    def __init__(
        self, question: str, details: str | Text = '', yes: str = 'Yes', no: str = 'No'
    ) -> None:
        """Make the question.

        Args:
            question: What is asked, e.g. 'Cancel job #42 on nancy?'.
            details: What it means, under the question.
            yes: The yes button's label, e.g. 'Cancel job'.
            no: The no button's label, e.g. 'Keep it'.
        """
        super().__init__()
        self.question, self.details = question, details
        self.yes_label, self.no_label = yes, no

    def compose(self) -> ComposeResult:
        """The box: the question, the details, the buttons."""
        with Vertical(id='confirm') as box:
            box.border_title = self.question
            box.border_subtitle = 'y: yes · n or Esc: no'
            yield Static(self.details, id='confirm-details')
            with Horizontal(id='confirm-buttons'):
                yield Button(self.yes_label, compact=True, id='yes')
                yield Button(self.no_label, compact=True, id='no')

    def on_mount(self) -> None:
        """No has the focus: Enter alone doesn't do the harm."""
        self.query_one('#no', Button).focus()

    @on(Button.Pressed, '#yes')
    def action_yes(self) -> None:
        """Yes: close, answering True."""
        self.dismiss(True)

    @on(Button.Pressed, '#no')
    def action_no(self) -> None:
        """No (or Esc): close, answering False."""
        self.dismiss(False)
