"""A fake Grid'5000 API for the client tests."""

import httpx


def fake_api(status: int = 200, json: dict | None = None, seen: list | None = None):
    """A fake transport: answers every request with status and json,
    and keeps the requests in seen (if given) so a test can check them."""

    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=json or {})

    return httpx.MockTransport(handle)
