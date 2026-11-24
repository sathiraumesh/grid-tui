"""What every Grid'5000 API call needs: the address, the login, and GET.

On a Grid'5000 frontend no login is needed. From anywhere else the API wants
HTTP basic auth with your Grid'5000 login, read from the environment:

    G5K_USER, G5K_PASSWORD   your Grid'5000 login
    G5K_API                  the API root (default: DEFAULT_BASE_URL)
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = 'https://api.grid5000.fr/stable'


class ApiError(Exception):
    """The API answered with an error."""

    def __init__(self, path: str, status: int) -> None:
        self.path = path
        self.status = status
        message = f'GET {path}: {status} {httpx.codes.get_reason_phrase(status)}'
        if status == 401:
            message += " (outside Grid'5000, set G5K_USER and G5K_PASSWORD)"
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
        self.base_url = base_url.rstrip('/')
        self.user = user
        self.password = password
        self._transport = transport
        self._timeout = timeout

    @classmethod
    def from_env(cls):
        """A client set up from G5K_API, G5K_USER and G5K_PASSWORD."""
        return cls(
            os.environ.get('G5K_API') or DEFAULT_BASE_URL,
            os.environ.get('G5K_USER', ''),
            os.environ.get('G5K_PASSWORD', ''),
        )

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
