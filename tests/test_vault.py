"""Tests for the vault: the login saved encrypted with a PIN."""

import json
import os
from pathlib import Path

import pytest

from grid_tui.vault import (
    MAX_TRIES,
    Credentials,
    Vault,
    VaultBlockedError,
    VaultError,
    WrongPinError,
    valid_pin,
)

ALICE = Credentials('alice', 'p4ssw0rd')


def vault(tmp_path: Path) -> Vault:
    """A vault in a temp folder, with a cheap scrypt so tests run fast."""
    return Vault(tmp_path / 'secret' / 'credentials.vault', cost=2**10)


def test_the_pin_opens_the_login(tmp_path: Path) -> None:
    """Saved with 1234, opened with 1234."""
    v = vault(tmp_path)
    assert not v.exists()
    v.save(ALICE, '1234')
    assert v.exists()
    assert v.open('1234') == ALICE


def test_the_file_doesnt_show_the_login(tmp_path: Path) -> None:
    """Neither the login nor the password is in the file; only you can read it."""
    v = vault(tmp_path)
    v.save(ALICE, '1234')
    text = v.path.read_text()
    assert 'alice' not in text and 'p4ssw0rd' not in text
    assert os.stat(v.path).st_mode & 0o777 == 0o600
    assert os.stat(v.path.parent).st_mode & 0o777 == 0o700


def test_a_wrong_pin_says_how_many_tries_are_left(tmp_path: Path) -> None:
    """Each wrong PIN counts down; the count is kept in the file."""
    v = vault(tmp_path)
    v.save(ALICE, '1234')
    with pytest.raises(WrongPinError) as first:
        v.open('0000')
    assert first.value.tries_left == MAX_TRIES - 1
    again = vault(tmp_path)  # as if the app was started again
    with pytest.raises(WrongPinError) as second:
        again.open('1111')
    assert second.value.tries_left == MAX_TRIES - 2


def test_three_wrong_pins_erase_the_login(tmp_path: Path) -> None:
    """The third wrong PIN in a row erases it: only signing up is left."""
    v = vault(tmp_path)
    v.save(ALICE, '1234')
    for _ in range(MAX_TRIES - 1):
        with pytest.raises(WrongPinError):
            v.open('0000')
    with pytest.raises(VaultBlockedError):
        v.open('0000')
    assert not v.exists()
    with pytest.raises(VaultError):
        v.open('1234')  # gone, even with the right PIN


def test_the_right_pin_starts_the_count_again(tmp_path: Path) -> None:
    """Two wrong, then right: the next wrong one has every try again."""
    v = vault(tmp_path)
    v.save(ALICE, '1234')
    for _ in range(MAX_TRIES - 1):
        with pytest.raises(WrongPinError):
            v.open('0000')
    assert v.open('1234') == ALICE
    with pytest.raises(WrongPinError) as wrong:
        v.open('0000')
    assert wrong.value.tries_left == MAX_TRIES - 1


def test_signing_up_again_replaces_the_login(tmp_path: Path) -> None:
    """A new login and PIN: the old PIN no longer opens anything."""
    v = vault(tmp_path)
    v.save(ALICE, '1234')
    v.save(Credentials('bob', 'secret'), '9876')
    assert v.open('9876') == Credentials('bob', 'secret')
    with pytest.raises(WrongPinError):
        v.open('1234')


def test_a_broken_file_is_an_error_not_a_crash(tmp_path: Path) -> None:
    """Not JSON, or another version: VaultError, saying to sign up again."""
    v = vault(tmp_path)
    v.path.parent.mkdir(parents=True)
    v.path.write_text('not json')
    with pytest.raises(VaultError):
        v.open('1234')
    v.path.write_text(json.dumps({'version': 99}))
    with pytest.raises(VaultError, match='another version'):
        v.open('1234')


def test_valid_pin() -> None:
    """Exactly 4 digits."""
    assert valid_pin('0123')
    assert not valid_pin('123')
    assert not valid_pin('12345')
    assert not valid_pin('12a4')
    with pytest.raises(ValueError):
        Vault(Path('/nowhere/x')).save(ALICE, '12')
