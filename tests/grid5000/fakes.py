"""A fake Grid'5000 API for the tests."""

import httpx

from grid_tui.grid5000 import Client


def fake_api(status: int = 200, json: dict | None = None, seen: list | None = None):
    """A fake transport: answers every request with status and json,
    and keeps the requests in seen (if given) so a test can check them."""

    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=json or {})

    return httpx.MockTransport(handle)


def fake_client() -> Client:
    """A Client whose API answers with no sites, so tests stay offline."""
    return Client(transport=fake_api(json={'items': []}))
