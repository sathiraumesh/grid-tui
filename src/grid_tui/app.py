from textual.app import App
from textual.widgets import Static


class Grid5KApp(App):
    def compose(self):
        yield Static('Hello World')


def main() -> None:
    Grid5KApp().run()
