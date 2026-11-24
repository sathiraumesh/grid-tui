from textual.widgets import Label

from grid_tui.app import Grid5KApp


async def test_shows_title_and_copyright():
    app = Grid5KApp()
    async with app.run_test():  # runs the app headless, no real terminal
        title = app.query_one('#title', Label)
        assert str(title.render()) == "Grid'5000"

        copyright = app.query_one('#copyright', Label)
        assert str(copyright.render()) == 'Powered by IP Paris'


async def test_stylesheet_is_applied():
    app = Grid5KApp()
    async with app.run_test():
        assert app.screen.styles.background.hex == '#1E1E2E'

        title = app.query_one('#title', Label)
        assert title.styles.color.hex == '#FAB387'  # orange
        assert title.styles.dock == 'top'

        copyright = app.query_one('#copyright', Label)
        assert copyright.styles.dock == 'bottom'


async def test_q_quits():
    app = Grid5KApp()
    async with app.run_test() as pilot:  # pilot presses keys and clicks
        await pilot.press('q')
    assert app.return_code == 0
