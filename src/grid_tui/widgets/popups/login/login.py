"""The screens before the app: sign up (login and a PIN), and log in (the PIN).

- Sign up: your Grid'5000 login and password, and a 4-digit PIN twice. The
  login is checked with the API, then saved encrypted with the PIN (see
  grid_tui.vault).
- Log in: the PIN opens the saved login.
- Forgot the PIN: sign up again; the new login and PIN replace the old.

Both close with the login (Credentials), for the app to connect with.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx
from rich.text import Text
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from grid_tui.grid5000 import ApiError
from grid_tui.vault import (
    PIN_LENGTH,
    Credentials,
    Vault,
    VaultBlockedError,
    VaultError,
    WrongPinError,
    valid_pin,
)

CSS = (Path(__file__).parent / 'login.tcss').read_text()
DIGITS = r'[0-9]*'  # what a PIN box takes

Check = Callable[[Credentials], Awaitable[None]]  # raises ApiError if refused

# the name in block letters, two rows of half blocks, over the card
BANNER = '█▀▀ █▀█ █ █▀▄ ▀ █▀▀ █▀█ █▀█ █▀█\n█▄█ █▀▄ █ █▄▀   ▄▄█ █▄█ █▄█ █▄█'
TAGLINE = 'the testbed, in your terminal'
ORANGE, GREEN, RED, MUTED, EMPTY = '#fab387', '#a6e3a1', '#f38ba8', '#a6adc8', '#45475a'


def banner() -> ComposeResult:
    """The name in block letters, and what the app is, over the card."""
    yield Static(Text(BANNER, style=f'bold {ORANGE}'), classes='banner')
    yield Static(Text(TAGLINE, style=MUTED), classes='tagline')


def pin_dots(typed: int) -> Text:
    """A dot for each digit of the PIN: filled for those typed, e.g. ● ● ○ ○."""
    text = Text()
    for index in range(PIN_LENGTH):
        if index:
            text.append('  ')
        filled = index < typed
        text.append('●' if filled else '○', ORANGE if filled else EMPTY)
    return text


def say_on(screen: Screen, text: str, error: bool) -> None:
    """Put a line under a card's boxes: ✗ and red for what's wrong, else grey."""
    message = screen.query_one('#message', Static)
    message.update(Text(('✗ ' if error else '') + text, style=RED if error else MUTED))


class QuittingPinInput(Input):
    """A PIN box where q quits the app: it takes digits only, so q is free."""

    async def _on_key(self, event: events.Key) -> None:
        """q quits; any other key is as in any box."""
        if event.key == 'q':
            event.stop()
            await self.app.action_quit()
            return
        await super()._on_key(event)


def pin_box(box_id: str, placeholder: str, *, q_quits: bool = False) -> Input:
    """A box for a PIN: digits only, PIN_LENGTH of them, shown as dots.

    Args:
        box_id: The box's id.
        placeholder: What it shows while empty.
        q_quits: q quits the app (the PIN screen, where nothing else is typed).
    """
    kind = QuittingPinInput if q_quits else Input
    return kind(
        placeholder=placeholder,
        password=True,
        restrict=DIGITS,
        max_length=PIN_LENGTH,
        compact=True,
        id=box_id,
    )


class SignUpScreen(Screen[Credentials]):
    """Your Grid'5000 login and a new PIN: checked, saved encrypted, done."""

    DEFAULT_CSS = CSS
    BINDINGS = [
        Binding('escape', 'back', 'Back', show=False),
        # q types a q in the login and password boxes: Ctrl+Q quits from anywhere
        Binding('ctrl+q', 'app.quit', 'Quit', priority=True, show=False),
    ]

    def __init__(
        self, vault: Vault, check: Check, *, can_go_back: bool = False
    ) -> None:
        """Make the screen.

        Args:
            vault: Where the login is saved.
            check: Tries the login on the API; raises ApiError if refused.
            can_go_back: Esc goes back (to the PIN screen, if you came from
                'Forgot PIN'); on a first sign-up there's nothing to go back to.
        """
        super().__init__()
        self.vault = vault
        self.check = check
        self.can_go_back = can_go_back

    def compose(self) -> ComposeResult:
        """The banner, then the card: the boxes, the message line, the button."""
        with Center(classes='page'):
            yield from banner()
            with Vertical(classes='card') as card:
                card.border_title = (
                    'Sign up' if not self.vault.exists() else 'Sign up again'
                )
                card.border_subtitle = (
                    'Esc: back · Ctrl+Q: quit' if self.can_go_back else 'Ctrl+Q: quit'
                )
                yield Static(
                    "Your Grid'5000 login, and a PIN to unlock it next time.",
                    classes='intro',
                )
                with Grid(classes='form'):
                    yield Label('Login', classes='form-label')
                    yield Input(placeholder='e.g. alice', compact=True, id='user')
                    yield Label('Password', classes='form-label')
                    yield Input(
                        placeholder="your Grid'5000 password",
                        password=True,
                        compact=True,
                        id='password',
                    )
                    yield Label('PIN', classes='form-label')
                    with Horizontal(classes='pin-row'):
                        yield pin_box('pin', f'{PIN_LENGTH} digits')
                        yield Static(pin_dots(0), classes='dots', id='pin-dots')
                    yield Label('PIN again', classes='form-label')
                    with Horizontal(classes='pin-row'):
                        yield pin_box('pin-again', 'the same')
                        yield Static('', classes='dots', id='pin-match')
                yield Static('', classes='message', id='message')
                with Horizontal(classes='buttons'):
                    yield Button('Sign up  ›', compact=True, id='sign-up')
            yield Static(
                '◆ Kept on this computer only, encrypted with your PIN.',
                classes='note',
            )

    @on(Input.Changed, '#pin')
    @on(Input.Changed, '#pin-again')
    def _pins_typed(self) -> None:
        """Fill the PIN's dots, and say once the two PINs match."""
        pin = self.query_one('#pin', Input).value
        again = self.query_one('#pin-again', Input).value
        self.query_one('#pin-dots', Static).update(pin_dots(len(pin)))
        match = self.query_one('#pin-match', Static)
        if valid_pin(pin) and again == pin:
            match.update(Text('✓ same', style=GREEN))
        elif len(again) == PIN_LENGTH:
            match.update(Text('✗ not the same', style=RED))
        else:
            match.update('')

    def on_mount(self) -> None:
        """The cursor in the first box."""
        self.query_one('#user', Input).focus()

    def say(self, text: str, error: bool = True) -> None:
        """Put a line under the boxes: what's wrong (red), or what's going on."""
        say_on(self, text, error)

    def filled_in(self) -> tuple[Credentials, str]:
        """The login and the PIN, as typed.

        Raises:
            ValueError: Something is missing or doesn't match; says what.
        """
        user = self.query_one('#user', Input).value.strip()
        password = self.query_one('#password', Input).value
        pin = self.query_one('#pin', Input).value
        again = self.query_one('#pin-again', Input).value
        if not user or not password:
            raise ValueError("Type your Grid'5000 login and password.")
        if not valid_pin(pin):
            raise ValueError(f'The PIN is {PIN_LENGTH} digits.')
        if pin != again:
            raise ValueError("The two PINs aren't the same.")
        return Credentials(user, password), pin

    @on(Button.Pressed, '#sign-up')
    @on(Input.Submitted)
    def _submit(self) -> None:
        """Sign up (the button, or Enter in any box), if it's all filled in."""
        try:
            credentials, pin = self.filled_in()
        except ValueError as error:
            self.say(str(error))
            return
        self.sign_up(credentials, pin)

    @work(exclusive=True)
    async def sign_up(self, credentials: Credentials, pin: str) -> None:
        """Check the login with the API, save it encrypted, and close with it."""
        button = self.query_one('#sign-up', Button)
        button.disabled = True
        self.say("Checking your login with Grid'5000…", error=False)
        try:
            await self.check(credentials)
        except ApiError as error:
            button.disabled = False
            if error.status == 401:
                self.say("Grid'5000 doesn't know this login and password.")
            else:
                self.say(f"Couldn't check the login: {error}")
            return
        except httpx.HTTPError:
            button.disabled = False
            self.say("Couldn't reach Grid'5000 to check the login. Try again.")
            return
        self.say('Saving it, encrypted…', error=False)
        # scrypt is slow on purpose: not on the screen's thread
        await asyncio.to_thread(self.vault.save, credentials, pin)
        self.dismiss(credentials)

    def action_back(self) -> None:
        """Back to the PIN screen (Esc), if you came from it."""
        if self.can_go_back:
            self.dismiss(None)


class LoginScreen(Screen[Credentials]):
    """The PIN, to open the saved login; or 'Forgot PIN' to sign up again."""

    DEFAULT_CSS = CSS
    BINDINGS = [
        Binding('q', 'app.quit', 'Quit', show=False),  # off the PIN box
        Binding('ctrl+q', 'app.quit', 'Quit', priority=True, show=False),
    ]

    def __init__(self, vault: Vault, check: Check) -> None:
        """Make the screen.

        Args:
            vault: Where the login is saved.
            check: For signing up again: tries a login on the API.
        """
        super().__init__()
        self.vault = vault
        self.check = check
        self.checking = False  # a PIN is being checked

    def compose(self) -> ComposeResult:
        """The banner, then the card: the PIN, the message line, the buttons."""
        with Center(classes='page'):
            yield from banner()
            with Vertical(classes='card') as card:
                card.border_title = 'Welcome back'
                card.border_subtitle = 'q: quit'
                yield Static(
                    f'Type your {PIN_LENGTH}-digit PIN to unlock.', classes='intro'
                )
                yield Static(pin_dots(0), classes='dots big', id='pin-dots')
                with Center():
                    yield pin_box('pin', '', q_quits=True)  # q quits there too
                yield Static('', classes='message', id='message')
                with Horizontal(classes='buttons'):
                    yield Button('Forgot PIN?', compact=True, id='forgot')
                    yield Button('Unlock  ›', compact=True, id='log-in')
            yield Static(
                '◆ 3 wrong PINs erase the saved login: then sign up again.',
                classes='note',
            )

    @on(Input.Changed, '#pin')
    def _pin_typed(self, event: Input.Changed) -> None:
        """Fill a dot for each digit typed."""
        self.query_one('#pin-dots', Static).update(pin_dots(len(event.value)))

    def on_mount(self) -> None:
        """The cursor in the PIN box."""
        self.query_one('#pin', Input).focus()

    def say(self, text: str, error: bool = True) -> None:
        """Put a line under the box: what's wrong (red), or what's going on."""
        say_on(self, text, error)

    @on(Button.Pressed, '#log-in')
    @on(Input.Submitted, '#pin')
    def _submit(self) -> None:
        """Log in (the button, or Enter), if the PIN is whole.

        Not while a PIN is being checked: a second Enter would count as a
        second try of the same PIN.
        """
        if self.checking:
            return
        pin = self.query_one('#pin', Input).value
        if not valid_pin(pin):
            self.say(f'The PIN is {PIN_LENGTH} digits.')
            return
        self.log_in(pin)

    @work(exclusive=True)
    async def log_in(self, pin: str) -> None:
        """Open the saved login with the PIN, and close with it."""
        self.say('Opening…', error=False)
        box = self.query_one('#pin', Input)
        self.checking = True
        try:
            credentials = await asyncio.to_thread(self.vault.open, pin)
        except WrongPinError as error:
            box.value = ''
            left = error.tries_left
            self.say(f'Wrong PIN: {left} more {"try" if left == 1 else "tries"}.')
            return
        except VaultBlockedError as error:
            self.blocked(str(error))
            return
        except VaultError as error:
            box.value = ''
            self.say(f'{error} Use Forgot PIN? to sign up again.')
            return
        finally:
            self.checking = False
        self.dismiss(credentials)

    def blocked(self, why: str) -> None:
        """Too many wrong PINs: the login is erased; only signing up is left."""
        self.app.notify(why, title='Login erased', severity='error', timeout=10)

        def signed_up(credentials: Credentials | None) -> None:
            if credentials is not None:
                self.dismiss(credentials)

        self.app.push_screen(SignUpScreen(self.vault, self.check), signed_up)

    @on(Button.Pressed, '#forgot')
    def forgot(self) -> None:
        """Sign up again: a new login and PIN replace the saved ones."""

        def signed_up(credentials: Credentials | None) -> None:
            if credentials is not None:
                self.dismiss(credentials)

        self.app.push_screen(
            SignUpScreen(self.vault, self.check, can_go_back=True), signed_up
        )
