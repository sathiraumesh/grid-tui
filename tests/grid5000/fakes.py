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
        {
            'uid': 'gros',
            'model': 'Dell R640',
            'queues': ['default'],
            'kavlan': True,
            'metrics': [
                {
                    'name': 'wattmetre_power_watt',
                    'description': 'Power from the wattmeter',
                    'period': 1000,
                    'optional_period': 20,
                    'only_for': ['gros-1'],
                },
                {'name': 'bmc_node_power_watt', 'description': 'Power from the BMC'},
            ],
        },
        {'uid': 'grisou', 'model': 'Dell R630', 'queues': ['default', 'admin']},
    ],
    'lyon': [
        {'uid': 'nova', 'model': 'Dell R430', 'queues': ['default'], 'exotic': True},
    ],
}


NODES = {
    ('nancy', 'gros'): [
        {
            'uid': 'gros-1',
            'cluster': 'gros',
            'architecture': {'nb_procs': 1, 'nb_cores': 18, 'nb_threads': 36},
            'processor': {'other_description': 'Intel Xeon Gold 5220'},
            'main_memory': {'ram_size': 96 * 1024**3},
        },
        {'uid': 'gros-2', 'cluster': 'gros'},
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
    nodes: dict[tuple[str, str], list[dict]] | None = None,
):
    """A fake transport that answers like Grid'5000, path by path:

    /sites                                       → sites
    /sites/{site}/clusters                       → clusters[site]
    /sites/{site}/clusters/{cluster}             → that cluster
    /sites/{site}/clusters/{cluster}/nodes       → nodes[(site, cluster)]
    /sites/{site}/clusters/{cluster}/nodes/{uid} → that node

    Anything it doesn't know is a 404. Every answer has this status instead,
    if it isn't 200 (e.g. 401).
    """
    sites = sites or []
    clusters = clusters or {}
    nodes = nodes or {}

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
        if len(parts) == 5 and parts[1] == 'sites' and parts[3] == 'clusters':
            for cluster in clusters.get(parts[2], []):
                if cluster['uid'] == parts[4]:
                    return httpx.Response(200, json=cluster)
            return httpx.Response(404, json={})
        if len(parts) in (6, 7) and parts[1] == 'sites' and parts[5] == 'nodes':
            found = nodes.get((parts[2], parts[4]))
            if found is None:
                return httpx.Response(404, json={})
            if len(parts) == 6:
                return httpx.Response(200, json={'items': found})
            for node in found:
                if node['uid'] == parts[6]:
                    return httpx.Response(200, json=node)
        return httpx.Response(404, json={})

    return httpx.MockTransport(handle)


def fake_client(
    sites: list[dict] | None = None,
    clusters: dict[str, list[dict]] | None = None,
    status: int = 200,
    nodes: dict[tuple[str, str], list[dict]] | None = None,
) -> Client:
    """A Client talking to fake_grid5000: no sites unless given, so tests stay
    offline."""
    return Client(transport=fake_grid5000(sites, clusters, status, nodes=nodes))


def g5k_client(status: int = 200) -> Client:
    """A Client talking to fake_grid5000 with SITES, CLUSTERS and NODES."""
    return fake_client(SITES, CLUSTERS, status, nodes=NODES)
