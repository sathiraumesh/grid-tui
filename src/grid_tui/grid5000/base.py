"""What every Grid'5000 API call needs: the address, the login, and GET.

On a Grid'5000 frontend no login is needed. From anywhere else the API wants
HTTP basic auth with your Grid'5000 login, read from the environment:

    G5K_USER, G5K_PASSWORD   your Grid'5000 login
    G5K_API                  the API root (default: DEFAULT_BASE_URL)

Any of these not set in the environment is read from a secret folder instead,
one file per variable holding its value base64-encoded:

    ~/.grid-secret/G5K_USER        e.g. made with: printf alice | base64
    ~/.grid-secret/G5K_PASSWORD
"""

from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path
from typing import Any, TypeVar

import httpx

DEFAULT_BASE_URL = 'https://api.grid5000.fr/stable'
SECRET_DIR_NAME = '.grid-secret'
SETTING_NAMES = ('G5K_API', 'G5K_USER', 'G5K_PASSWORD')

ClientT = TypeVar('ClientT', bound='BaseClient')  # from_env makes the same class


def find_secret_dir() -> Path:
    """The secret folder: ~/.grid-secret in your home folder."""
    return Path.home() / SECRET_DIR_NAME


def read_secrets(folder: Path | None) -> dict[str, str]:
    """The settings found in folder, each file's base64 contents decoded.

    Args:
        folder: The secret folder; None (or a missing folder) gives {}.

    Raises:
        ValueError: A file there is not valid base64 (or not UTF-8 inside).
    """
    secrets = {}
    if folder is None or not folder.is_dir():
        return secrets
    for name in SETTING_NAMES:
        path = folder / name
        if not path.is_file():
            continue
        try:
            raw = base64.b64decode(path.read_text().strip(), validate=True)
            secrets[name] = raw.decode('utf-8').strip()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise ValueError(f'{path}: not valid base64 ({error})') from error
    return secrets


def settings_from_env(secret_dir: Path | None = None) -> dict[str, str]:
    """The API address and login, from G5K_API, G5K_USER and G5K_PASSWORD.

    Each is taken from the environment if set there, else from the secret
    folder (~/.grid-secret), else left at its default.

    Args:
        secret_dir: The secret folder to read; None means ~/.grid-secret.
    """
    secrets = read_secrets(secret_dir or find_secret_dir())

    def get(name: str) -> str:
        return os.environ.get(name) or secrets.get(name, '')

    return {
        'base_url': get('G5K_API') or DEFAULT_BASE_URL,
        'user': get('G5K_USER'),
        'password': get('G5K_PASSWORD'),
    }


class ApiError(Exception):
    """The API answered with an error."""

    def __init__(self, path: str, status: int) -> None:
        """Make the error.

        Args:
            path: The API path that was asked for, e.g. '/sites'.
            status: The HTTP status the API answered with, e.g. 401.
        """
        self.path = path
        self.status = status
        message = f'GET {path}: {status} {httpx.codes.get_reason_phrase(status)}'
        if status == 401:
            message += (
                " (outside Grid'5000, set G5K_USER and G5K_PASSWORD"
                f' or put them in ~/{SECRET_DIR_NAME}/)'
            )
        super().__init__(message)


class BaseClient:
    """Connects to the Grid'5000 API. The other clients build on this."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user: str = '',
        password: str = '',
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake one
        timeout: float = 30.0,
    ) -> None:
        """Make the client.

        Args:
            base_url: The API root, e.g. 'https://api.grid5000.fr/stable'.
            user: Your Grid'5000 login; '' on a frontend, where none is needed.
            password: Your Grid'5000 password.
            transport: What sends the requests; tests give a fake one.
            timeout: How many seconds to wait for an answer.
        """
        self.base_url = base_url.rstrip('/')
        self.user = user
        self.password = password
        self._transport = transport
        self._timeout = timeout

    @classmethod
    def from_env(cls: type[ClientT]) -> ClientT:
        """A client set up from G5K_API, G5K_USER and G5K_PASSWORD."""
        return cls(**settings_from_env())

    async def _get(self, path: str) -> Any:
        """GET path and return the JSON answer."""
        auth = httpx.BasicAuth(self.user, self.password) if self.user else None
        async with httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            timeout=self._timeout,
            transport=self._transport,
        ) as http:
            response = await http.get(path, headers={'Accept': 'application/json'})
        if not response.is_success:
            raise ApiError(path, response.status_code)
        return response.json()
