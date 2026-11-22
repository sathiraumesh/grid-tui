"""A small async client for the Grid'5000 API.

On a Grid'5000 frontend no login is needed. From anywhere else the API wants
HTTP basic auth with your Grid'5000 login, read from the environment:

    G5K_USER, G5K_PASSWORD   your Grid'5000 login (not needed on a frontend)
    G5K_API                  the API root, default DEFAULT_BASE_URL

Lists come wrapped as {"items": [...], "total": n, "offset": 0}.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from grid_tui.models import Site

DEFAULT_BASE_URL = "https://api.grid5000.fr/stable"
SITES_PATH = "/sites"


class ApiError(Exception):
    """An answer that isn't a success."""

    def __init__(self, method: str, path: str, status: int, detail: str = "") -> None:
        self.method, self.path, self.status, self.detail = method, path, status, detail
        message = f"{method} {path}: {status} {httpx.codes.get_reason_phrase(status)}"
        if detail:
            message += f": {detail}"
        if status == 401:
            message += " (outside Grid'5000, set G5K_USER and G5K_PASSWORD)"
        super().__init__(message)


class Client:
    """Calls the Grid'5000 API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user: str = "",
        password: str = "",
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # tests give a fake one
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user, self.password = user, password
        self._transport, self._timeout = transport, timeout

    @classmethod
    def from_env(cls) -> Client:
        """A client from G5K_API, G5K_USER and G5K_PASSWORD."""
        return cls(
            os.environ.get("G5K_API") or DEFAULT_BASE_URL,
            os.environ.get("G5K_USER", ""),
            os.environ.get("G5K_PASSWORD", ""),
        )

    def command(self, path: str) -> str:
        """The curl command for GET path, to show what a screen is made of."""
        return f"curl {self.base_url}{path}"

    async def _get(self, path: str) -> Any:
        auth = httpx.BasicAuth(self.user, self.password) if self.user else None
        async with httpx.AsyncClient(
            base_url=self.base_url, auth=auth, timeout=self._timeout, transport=self._transport
        ) as http:
            response = await http.get(path, headers={"Accept": "application/json"})
        if not response.is_success:
            raise ApiError("GET", path, response.status_code, _detail(response))
        try:
            return response.json()
        except ValueError as e:
            raise ApiError("GET", path, response.status_code, f"reading the answer: {e}") from e

    async def sites(self) -> list[Site]:
        """Every Grid'5000 site: GET /stable/sites."""
        data = await self._get(SITES_PATH)
        return [
            Site(uid=item.get("uid", ""), name=item.get("name", ""), description=item.get("description", ""))
            for item in data.get("items", [])
        ]


def _detail(response: httpx.Response) -> str:
    """What an error answer says: its JSON "message", else its first line of
    text; nothing for an HTML page."""
    text = response.text.strip()
    if not text or text.startswith("<"):
        return ""
    try:
        message = response.json().get("message", "")
        return message if isinstance(message, str) else ""
    except (ValueError, AttributeError):
        return text.splitlines()[0]
