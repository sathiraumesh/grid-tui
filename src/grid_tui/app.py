from textual.app import App
from textual.widgets import Footer


class Grid5KApp(App):
    CSS_PATH = 'app.tcss'  # next to this file
    BINDINGS = [
        ('q', 'quit', 'Quit'),
        ('r', 'reload', 'Reload'),
        
        ]  # q runs Textual's built-in quit action

    def on_mount(self):
        self.screen.border_title = "Grid'5000"
        self.screen.border_subtitle = 'Powered by IP Paris'
    
    def compose(self):
        yield Footer()

    def action_reload(self) -> None:
        self.notify('Reloading…')

def main() -> None:
    Grid5KApp().run()
