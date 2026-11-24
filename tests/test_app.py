from grid_tui.app import Grid5KApp
from grid_tui.widgets.main_tabs import MainTabs
from tests.grid5000.fakes import fake_client


async def test_frame_shows_title_and_subtitle():
    app = Grid5KApp(fake_client())
    async with app.run_test():  # runs the app headless, no real terminal
        assert app.screen.border_title == "Grid'5000"
        assert app.screen.border_subtitle == 'Powered by IP Paris'


async def test_stylesheet_is_applied():
    app = Grid5KApp(fake_client())
    async with app.run_test():
        styles = app.screen.styles
        assert styles.background.hex == '#1E1E2E'

        edge_type, edge_color = styles.border_top
        assert edge_type == 'round'
        assert edge_color.hex == '#FAB387'  # orange frame

        assert styles.border_subtitle_color.hex == '#A6ADC8'


async def test_q_quits():
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:  # pilot presses keys and clicks
        await pilot.press('q')
    assert app.return_code == 0


async def test_number_keys_switch_tabs():
    app = Grid5KApp(fake_client())
    async with app.run_test() as pilot:
        tabs = app.query_one(MainTabs)
        assert tabs.active == 'sites'
        await pilot.press('2')
        assert tabs.active == 'clusters'
        await pilot.press('3')
        assert tabs.active == 'nodes'
        await pilot.press('1')
        assert tabs.active == 'sites'
