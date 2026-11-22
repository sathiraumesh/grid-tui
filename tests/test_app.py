from grid_tui.app import GridTUI


async def test_app_starts_and_quits() -> None:
    app = GridTUI()
    async with app.run_test() as pilot:
        assert app.query_one("#main").content == "nothing to show yet"
        await pilot.press("q")
    assert app.return_code == 0
