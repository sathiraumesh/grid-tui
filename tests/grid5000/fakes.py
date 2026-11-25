"""A fake Grid'5000 API for the tests."""

import httpx

from grid_tui.grid5000 import Client

# two sites, each with clusters: what most panel tests use
SITES = [
    {'uid': 'nancy', 'name': 'Nancy', 'description': 'Grid5000 Nancy site'},
    {'uid': 'lyon', 'name': 'Lyon', 'description': 'Grid5000 Lyon site'},
]
CLUSTERS = {
    'nancy': [
        {'uid': 'gros', 'model': 'Dell R640', 'queues': ['default'], 'kavlan': True},
        {'uid': 'grisou', 'model': 'Dell R630', 'queues': ['default', 'admin']},
    ],
    'lyon': [
        {'uid': 'nova', 'model': 'Dell R430', 'queues': ['default'], 'exotic': True},
    ],
}


def fake_api(status: int = 200, json: dict | None = None, seen: list | None = None):
    """A fake transport: answers every request with status and json,
    and keeps the requests in seen (if given) so a test can check them."""

    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=json or {})

    return httpx.MockTransport(handle)


def fake_grid5000(
    sites: list[dict] | None = None,
    clusters: dict[str, list[dict]] | None = None,
    status: int = 200,
    seen: list | None = None,
):
    """A fake transport that answers like Grid'5000, path by path:

    /sites                  → sites
    /sites/{site}/clusters  → clusters[site] (404 for a site it doesn't know)

    Every answer has this status instead, if it isn't 200 (e.g. 401).
    """
    sites = sites or []
    clusters = clusters or {}

    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if status != 200:
            return httpx.Response(status, json={})
        parts = request.url.path.strip('/').split('/')  # ['stable', 'sites', ...]
        if parts[1:] == ['sites']:
            return httpx.Response(200, json={'items': sites})
        if len(parts) == 4 and parts[1] == 'sites' and parts[3] == 'clusters':
            if parts[2] not in clusters:
                return httpx.Response(404, json={})
            return httpx.Response(200, json={'items': clusters[parts[2]]})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handle)


def fake_client(
    sites: list[dict] | None = None,
    clusters: dict[str, list[dict]] | None = None,
    status: int = 200,
) -> Client:
    """A Client talking to fake_grid5000: no sites unless given, so tests stay
    offline."""
    return Client(transport=fake_grid5000(sites, clusters, status))


def g5k_client(status: int = 200) -> Client:
    """A Client talking to fake_grid5000 with SITES and CLUSTERS."""
    return fake_client(SITES, CLUSTERS, status)
