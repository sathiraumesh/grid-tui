"""Your Grid'5000 login, saved encrypted with a PIN.

Sign up once with your login and a PIN; after that the PIN opens the login.
Forgot the PIN? Sign up again: the new login and PIN replace the old ones.
After MAX_TRIES wrong PINs in a row the saved login is erased: sign up again.
The count is kept in the file, so quitting the app doesn't reset it.

    vault = Vault()                        # ~/.grid-secret/credentials.vault
    vault.save(Credentials('alice', 'p4ss'), '1234')
    vault.open('1234')                     # Credentials('alice', 'p4ss')
    vault.open('0000')                     # raises WrongPinError

How it's kept: the PIN is stretched into a key with scrypt (slow on purpose,
and with a random salt), and the login is encrypted with AES-GCM, which also
tells a wrong PIN from the right one. The file holds the salt, the nonce and
the encrypted login, each base64-encoded, and only you can read it (600).

How safe that is: a 4-digit PIN has 10,000 values. Someone with a copy of
the file can try them all; scrypt makes that take a while (tens of minutes),
not forever. It keeps the login from being read by a glance or a stray
backup, not from a determined attacker. A longer PIN (PIN_LENGTH) helps.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from grid_tui.grid5000.base import find_secret_dir

PIN_LENGTH = 4
VAULT_NAME = 'credentials.vault'
VERSION = 1
# scrypt's cost: 2**17 × 8 × 128 bytes = 128 MiB of memory, about 0.3 s a try,
# so all 10,000 four-digit PINs take nearly an hour
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**17, 8, 1
CONTEXT = b'grid-tui credentials v1'  # bound into the encryption
MAX_TRIES = 3  # wrong PINs in a row before the saved login is erased


class VaultError(Exception):
    """The saved login can't be read: missing, broken, or another version."""


class WrongPinError(VaultError):
    """The PIN doesn't open the saved login; tries_left more before it's erased."""

    def __init__(self, tries_left: int) -> None:
        """Make the error, saying how many tries are left."""
        self.tries_left = tries_left
        super().__init__(f'Wrong PIN: {tries_left} more tries.')


class VaultBlockedError(VaultError):
    """Too many wrong PINs: the saved login was erased; sign up again."""


@dataclass(frozen=True)
class Credentials:
    """A Grid'5000 login."""

    user: str
    password: str


def valid_pin(pin: str) -> bool:
    """Is it a PIN: exactly PIN_LENGTH digits."""
    return len(pin) == PIN_LENGTH and pin.isdigit()


def default_vault_path() -> Path:
    """Where the login is saved: ~/.grid-secret/credentials.vault."""
    return find_secret_dir() / VAULT_NAME


def _key(pin: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    """The 32-byte key a PIN and a salt make, by scrypt."""
    return hashlib.scrypt(
        pin.encode(), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=256 * 1024 * 1024
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


class Vault:
    """The login saved encrypted in one file."""

    def __init__(self, path: Path | str | None = None, *, cost: int = SCRYPT_N) -> None:
        """Use the vault file at path.

        Args:
            path: The file; None for ~/.grid-secret/credentials.vault.
            cost: scrypt's N for new saves (opening reads it from the file);
                tests pass a small one to run fast.
        """
        self.path = Path(path) if path is not None else default_vault_path()
        self.cost = cost

    def exists(self) -> bool:
        """Has a login been saved (signed up)."""
        return self.path.is_file()

    def save(self, credentials: Credentials, pin: str) -> None:
        """Encrypt the login with the PIN and save it, replacing any before.

        Raises:
            ValueError: The PIN isn't PIN_LENGTH digits.
        """
        if not valid_pin(pin):
            raise ValueError(f'The PIN must be {PIN_LENGTH} digits.')
        salt, nonce = os.urandom(16), os.urandom(12)
        key = _key(pin, salt, self.cost, SCRYPT_R, SCRYPT_P)
        secret = json.dumps(
            {'user': credentials.user, 'password': credentials.password}
        )
        sealed = AESGCM(key).encrypt(nonce, secret.encode(), CONTEXT)
        record = {
            'version': VERSION,
            'kdf': {'name': 'scrypt', 'n': self.cost, 'r': SCRYPT_R, 'p': SCRYPT_P},
            'salt': _b64(salt),
            'nonce': _b64(nonce),
            'secret': _b64(sealed),
        }
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self._write(record)

    def _write(self, record: dict) -> None:
        """Write the vault file, whole, readable by you only."""
        # written whole to a new file, then put in place: never half a vault
        new = self.path.with_suffix('.new')
        fd = os.open(new, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as file:
            json.dump(record, file)
        os.replace(new, self.path)

    def open(self, pin: str) -> Credentials:
        """The saved login, opened with the PIN.

        Raises:
            WrongPinError: The PIN isn't the one it was saved with.
            VaultBlockedError: That was the MAX_TRIES-th wrong PIN in a row:
                the saved login is erased.
            VaultError: There's no saved login, or it can't be read.
        """
        try:
            record = json.loads(self.path.read_text())
        except FileNotFoundError:
            raise VaultError('No login saved yet: sign up first.') from None
        except (OSError, ValueError) as error:
            raise VaultError(f"{self.path} can't be read: {error}") from None
        if not isinstance(record, dict) or record.get('version') != VERSION:
            raise VaultError(f'{self.path} is of another version: sign up again.')
        try:
            kdf = record['kdf']
            salt = base64.b64decode(record['salt'], validate=True)
            nonce = base64.b64decode(record['nonce'], validate=True)
            sealed = base64.b64decode(record['secret'], validate=True)
            key = _key(pin, salt, int(kdf['n']), int(kdf['r']), int(kdf['p']))
        except (KeyError, TypeError, ValueError) as error:
            raise VaultError(f'{self.path} is broken: {error}') from None
        try:
            secret = AESGCM(key).decrypt(nonce, sealed, CONTEXT)
        except InvalidTag:
            failed = int(record.get('failed', 0)) + 1
            if failed >= MAX_TRIES:
                self.erase()
                raise VaultBlockedError(
                    f'{MAX_TRIES} wrong PINs: the saved login was erased. '
                    'Sign up again.'
                ) from None
            self._write({**record, 'failed': failed})
            raise WrongPinError(MAX_TRIES - failed) from None
        if record.get('failed'):
            self._write({**record, 'failed': 0})  # the right PIN: count again
        login = json.loads(secret)
        return Credentials(login['user'], login['password'])

    def erase(self) -> None:
        """Delete the saved login (too many wrong PINs)."""
        self.path.unlink(missing_ok=True)
