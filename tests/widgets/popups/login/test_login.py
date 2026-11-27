"""Tests for signing up and logging in with a PIN, in the app."""

import base64
from pathlib import Path

import httpx
import pytest
from textual.widgets import Input, Static

from grid_tui.app import Grid5KApp
from grid_tui.grid5000 import Client
from grid_tui.vault import MAX_TRIES, Credentials, Vault
from grid_tui.widgets.main_tabs import MainTabs
from grid_tui.widgets.popups.login import LoginScreen, SignUpScreen
from tests.grid5000.fakes import CLUSTERS, SITES, STATUS, fake_grid5000
from tests.widgets.panels.helpers import settle

ALICE = Credentials('alice', 'right')


@pytest.fixture(autouse=True)
def _no_login_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app asks for a login only when G5K_USER isn't set."""
    monkeypatch.delenv('G5K_USER', raising=False)


def connect(credentials: Credentials) -> Client:
    """A client on a fake API that only lets alice (password 'right') in."""
    fake = fake_grid5000(SITES, CLUSTERS, statuses=STATUS)
    good = 'Basic ' + base64.b64encode(b'alice:right').decode()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.headers.get('authorization') != good:
            return httpx.Response(401, json={})
        return fake.handler(request)

    return Client(
        user=credentials.user,
        password=credentials.password,
        transport=httpx.MockTransport(handle),
    )


def app_with(tmp_path: Path) -> tuple[Grid5KApp, Vault]:
    """The app, with a vault in a temp folder (cheap scrypt) and the fake API."""
    vault = Vault(tmp_path / 'credentials.vault', cost=2**10)
    return Grid5KApp(vault=vault, connect=connect), vault


def message(app: Grid5KApp) -> str:
    """The line under the boxes of the screen showing."""
    return str(app.screen.query_one('#message', Static).render())


async def fill(app: Grid5KApp, pilot: object, **boxes: str) -> None:
    """Type into the boxes of the screen showing, by id."""
    for box_id, value in boxes.items():
        app.screen.query_one(f'#{box_id.replace("_", "-")}', Input).value = value
    await settle(app, pilot)


async def submit(app: Grid5KApp, pilot: object, button: str) -> None:
    """Press a button of the screen showing, and wait."""
    await pilot.click(f'#{button}')
    await settle(app, pilot)
    await pilot.pause(0.2)
    await settle(app, pilot)


async def test_the_first_time_asks_to_sign_up(tmp_path: Path) -> None:
    """No saved login: the sign-up screen, and no tabs yet."""
    app, _ = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert isinstance(app.screen, SignUpScreen)
        assert not app.query(MainTabs)


async def test_signing_up_saves_the_login_and_opens_the_app(tmp_path: Path) -> None:
    """Login, password, PIN twice: checked, saved encrypted, and in."""
    app, vault = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await fill(
            app, pilot, user='alice', password='right', pin='1234', pin_again='1234'
        )
        await submit(app, pilot, 'sign-up')
        assert not isinstance(app.screen, SignUpScreen)
        assert app.query_one(MainTabs)
        assert app.client is not None and app.client.sites.user == 'alice'
    assert vault.open('1234') == ALICE


async def test_a_wrong_password_isnt_saved(tmp_path: Path) -> None:
    """Grid'5000 refuses it: said so, nothing saved, still signing up."""
    app, vault = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await fill(
            app, pilot, user='alice', password='wrong', pin='1234', pin_again='1234'
        )
        await submit(app, pilot, 'sign-up')
        assert isinstance(app.screen, SignUpScreen)
        assert "doesn't know this login" in message(app)
    assert not vault.exists()


async def test_the_two_pins_must_match(tmp_path: Path) -> None:
    """Different PINs: said so, nothing asked."""
    app, vault = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await fill(
            app, pilot, user='alice', password='right', pin='1234', pin_again='4321'
        )
        await submit(app, pilot, 'sign-up')
        assert "aren't the same" in message(app)
    assert not vault.exists()


async def test_next_time_the_pin_is_enough(tmp_path: Path) -> None:
    """A saved login: the PIN screen; the right PIN opens the app."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        assert isinstance(app.screen, LoginScreen)
        await fill(app, pilot, pin='1234')
        await submit(app, pilot, 'log-in')
        assert app.query_one(MainTabs)
        assert app.client is not None and app.client.sites.user == 'alice'


async def test_a_wrong_pin_says_how_many_tries_are_left(tmp_path: Path) -> None:
    """Wrong once: 2 more tries, still on the PIN screen."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await fill(app, pilot, pin='0000')
        await submit(app, pilot, 'log-in')
        assert isinstance(app.screen, LoginScreen)
        assert f'{MAX_TRIES - 1} more tries' in message(app)


async def test_three_wrong_pins_erase_the_login_and_ask_to_sign_up(
    tmp_path: Path,
) -> None:
    """The third wrong PIN: the login is erased, and it's the sign-up screen."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        for _ in range(MAX_TRIES):
            await fill(app, pilot, pin='0000')
            await submit(app, pilot, 'log-in')
        assert isinstance(app.screen, SignUpScreen)
        assert not app.screen.can_go_back  # no way around it
        assert not vault.exists()


async def test_forgot_pin_signs_up_again(tmp_path: Path) -> None:
    """Forgot PIN?: sign up again with a new PIN; it replaces the old one."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await submit(app, pilot, 'forgot')
        assert isinstance(app.screen, SignUpScreen)
        await fill(
            app, pilot, user='alice', password='right', pin='5555', pin_again='5555'
        )
        await submit(app, pilot, 'sign-up')
        assert app.query_one(MainTabs)
    assert vault.open('5555') == ALICE


async def test_escape_goes_back_from_forgot_pin(tmp_path: Path) -> None:
    """Forgot PIN?, then Esc: back to the PIN screen; nothing changed."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await submit(app, pilot, 'forgot')
        await pilot.press('escape')
        await settle(app, pilot)
        assert isinstance(app.screen, LoginScreen)
    assert vault.open('1234') == ALICE


async def test_a_login_in_the_environment_skips_the_screens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G5K_USER set: no sign-up, no PIN; straight to the tabs."""
    monkeypatch.setenv('G5K_USER', 'alice')
    monkeypatch.setenv('G5K_PASSWORD', 'right')
    app = Grid5KApp(vault=Vault(tmp_path / 'v', cost=2**10), connect=connect)
    assert app.client is not None and app.client.sites.user == 'alice'


async def test_q_quits_from_the_pin_screen(tmp_path: Path) -> None:
    """q quits, even with the cursor in the PIN box (it takes digits only)."""
    app, vault = app_with(tmp_path)
    vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press('1', 'q')
        await pilot.pause()
        assert app.return_code is not None or not app.is_running


async def test_ctrl_q_quits_from_sign_up_and_q_is_typed(tmp_path: Path) -> None:
    """Signing up, q is a letter of the login; Ctrl+Q quits."""
    app, _ = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.press('q')
        await pilot.pause()
        assert app.screen.query_one('#user', Input).value == 'q'
        await pilot.press('ctrl+q')
        await pilot.pause()
        assert app.return_code is not None or not app.is_running


@pytest.mark.parametrize('saved', [False, True])
async def test_the_quit_button_quits(tmp_path: Path, saved: bool) -> None:
    """Quit, on the sign-up screen or the PIN screen, closes the app."""
    app, vault = app_with(tmp_path)
    if saved:
        vault.save(ALICE, '1234')
    async with app.run_test(size=(100, 30)) as pilot:
        await settle(app, pilot)
        await pilot.click('#quit')
        await pilot.pause()
        assert app.return_code is not None or not app.is_running
    assert vault.exists() == saved  # nothing saved, nothing erased
