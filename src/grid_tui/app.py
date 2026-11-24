from textual.app import App
from textual.widgets import Label


class Grid5KApp(App):
    CSS_PATH = 'app.tcss'  # next to this file
    BINDINGS = [('q', 'quit', 'Quit')]  # q runs Textual's built-in quit action

    def compose(self):
        # not `self.title`: App already uses `title` for the app's name (a string)
        self.title_label = Label("Grid'5000", id='title')
        self.copyright = Label('Powered by IP Paris', id='copyright')
        yield self.title_label
        yield self.copyright


def main() -> None:
    Grid5KApp().run()
