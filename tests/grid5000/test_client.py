from datetime import datetime, timedelta

import httpx
import pytest

from grid_tui.grid5000 import DEFAULT_BASE_URL, ApiError, Client
from grid_tui.grid5000.client import clusters_path, dig, each, num, text
from grid_tui.models import GPU, NIC, Cluster, Disk, Hardware, Site

SITES = {
    "total": 2,
    "offset": 0,
    "items": [
        {"uid": "nancy", "name": "Nancy", "description": "Grid5000 Nancy site", "type": "site", "links": []},
        {"uid": "rennes", "name": "Rennes", "description": "Grid5000 Rennes site", "type": "site", "links": []},
    ],
    "links": [],
}


def fake_api(request: httpx.Request) -> httpx.Response:
    """Answers like the Grid'5000 API, and wants basic auth alice/secret."""
    if request.headers.get("Authorization") != httpx.BasicAuth("alice", "secret")._auth_header:
        return httpx.Response(401, text="<html>401 Unauthorized</html>")
    if request.url.path == "/stable/sites":
        return httpx.Response(200, json=SITES)
    if request.url.path == "/stable/broken/sites":
        return httpx.Response(200, text="{not json")
    return httpx.Response(404, json={"code": 404, "message": "no such page"})


def client(base: str = "https://api.test/stable", user: str = "alice") -> Client:
    return Client(base, user, "secret", transport=httpx.MockTransport(fake_api))


async def test_sites() -> None:
    assert await client().sites() == [
        Site("nancy", "Nancy", "Grid5000 Nancy site"),
        Site("rennes", "Rennes", "Grid5000 Rennes site"),
    ]


async def test_sites_unauthorized() -> None:
    with pytest.raises(ApiError) as e:
        await client(user="").sites()
    assert e.value.status == 401 and e.value.path == "/sites"
    assert "G5K_USER" in str(e.value)  # it says how to log in
    assert "<html>" not in str(e.value)  # but not the HTML page


async def test_error_says_what_the_api_said() -> None:
    c = client()
    with pytest.raises(ApiError, match="GET /nowhere: 404 Not Found: no such page"):
        await c._get("/nowhere")


async def test_bad_json() -> None:
    with pytest.raises(ApiError, match="reading the answer"):
        await client("https://api.test/stable/broken").sites()


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("G5K_USER", "bob")
    monkeypatch.setenv("G5K_PASSWORD", "pw")
    monkeypatch.setenv("G5K_API", "https://example.test/api/")
    c = Client.from_env()
    assert (c.user, c.password, c.base_url) == ("bob", "pw", "https://example.test/api")

    monkeypatch.delenv("G5K_API")
    assert Client.from_env().base_url == DEFAULT_BASE_URL


def test_command() -> None:
    assert Client().command("/sites") == "curl https://api.grid5000.fr/stable/sites"


CLUSTERS = {
    "total": 2,
    "offset": 0,
    "items": [
        {"uid": "graffiti", "model": "Dell PowerEdge T640", "queues": ["production", "admin"], "type": "cluster"},
        {
            "uid": "gros",
            "model": "Dell PowerEdge R640",
            "queues": ["default", "admin"],
            "metrics": [
                {"name": "wattmetre_power_watt", "period": 20, "source": {"protocol": "wattmetre"}},
                {"name": "bmc_node_power_watt", "period": 5000},
            ],
        },
    ],
}


def clusters_api(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/stable/sites/nancy/clusters":
        return httpx.Response(200, json=CLUSTERS)
    return httpx.Response(404, json={"message": "unknown site"})


async def test_clusters() -> None:
    c = Client("https://api.test/stable", transport=httpx.MockTransport(clusters_api))
    graffiti, gros = await c.clusters("nancy")
    assert graffiti == Cluster("graffiti", "Dell PowerEdge T640", ("production", "admin"))
    assert gros.queues == ("default", "admin")
    assert gros.metrics == ("wattmetre_power_watt", "bmc_node_power_watt")
    assert gros.wattmeter and not graffiti.wattmeter


async def test_clusters_unknown_site() -> None:
    c = Client("https://api.test/stable", transport=httpx.MockTransport(clusters_api))
    with pytest.raises(ApiError, match="GET /sites/atlantis/clusters: 404 Not Found: unknown site"):
        await c.clusters("atlantis")


async def test_clusters_needs_a_site() -> None:
    with pytest.raises(ValueError):
        await Client().clusters("")


def test_clusters_path_is_escaped() -> None:
    assert clusters_path("nancy") == "/sites/nancy/clusters"
    assert clusters_path("a/b") == "/sites/a%2Fb/clusters"


# The hardware of a cluster: GET …/clusters/{cluster}/nodes, read from the first node.

FULL_NODE = {
    "uid": "gros-1",
    "processor": {"model": "Intel Xeon", "other_description": "Intel Xeon Gold 5220", "clock_speed": 2200000000},
    "architecture": {"nb_procs": 1, "nb_cores": 18, "nb_threads": 36},
    "main_memory": {"ram_size": 103079215104},
    "storage_devices": [{"storage": "SSD", "interface": "SATA", "size": 480103981056}],
    "network_adapters": [
        {"interface": "Ethernet", "rate": 25000000000, "mounted": True},
        {"interface": "Ethernet", "rate": 25000000000, "mounted": False},  # not connected: left out
    ],
    "gpu_devices": {
        "1": {"vendor": "Nvidia", "model": "A100", "memory": 2},
        "0": {"vendor": "Nvidia", "model": "A100", "memory": 1},
    },
}

# What a careless answer could look like: nulls, strings for numbers, junk in lists.
MESSY_NODE = {
    "uid": "odd-1",
    "processor": None,
    "architecture": {"nb_cores": "64", "nb_threads": True},
    "main_memory": None,
    "storage_devices": None,
    "network_adapters": [None, "x", {"rate": "1e10", "mounted": True}],
    "gpu_devices": [],
}


def nodes_api(request: httpx.Request) -> httpx.Response:
    nodes = {
        "/stable/sites/nancy/clusters/gros/nodes": [FULL_NODE, {"uid": "gros-2"}],
        "/stable/sites/nancy/clusters/odd/nodes": [MESSY_NODE],
        "/stable/sites/nancy/clusters/empty/nodes": [],
    }.get(request.url.path)
    if nodes is None:
        return httpx.Response(404, json={"message": "unknown cluster"})
    return httpx.Response(200, json={"total": len(nodes), "offset": 0, "items": nodes})


def nodes_client() -> Client:
    return Client("https://api.test/stable", transport=httpx.MockTransport(nodes_api))


async def test_hardware() -> None:
    assert await nodes_client().hardware("nancy", "gros") == Hardware(
        nodes=2,
        cpu="Intel Xeon Gold 5220",
        sockets=1,
        cores=18,
        threads=36,
        clock_ghz=2.2,
        memory=103079215104,
        disks=(Disk("SSD", "SATA", 480103981056),),
        nics=(NIC("Ethernet", 25000000000),),
        gpus=(GPU("Nvidia", "A100", 1), GPU("Nvidia", "A100", 2)),  # in key order: "0", "1"
    )


async def test_hardware_reads_what_it_can_of_a_messy_answer() -> None:
    assert await nodes_client().hardware("nancy", "odd") == Hardware(
        nodes=1, cores=64, nics=(NIC("", 10000000000),)
    )


async def test_hardware_errors() -> None:
    c = nodes_client()
    with pytest.raises(ValueError, match="has no nodes"):
        await c.hardware("nancy", "empty")
    with pytest.raises(ApiError, match="404 Not Found: unknown cluster"):
        await c.hardware("nancy", "atlantis")
    with pytest.raises(ValueError):
        await c.hardware("nancy", "")


def test_safe_readers() -> None:
    data = {"a": {"b": 1, "n": None, "s": "2.5", "t": True, "x": "abc"}, "l": [{"k": 1}, None, 3]}
    assert dig(data, "a", "b") == 1
    assert dig(data, "a", "n") is None and dig(data, "a", "n", default=0) == 0
    assert dig(data, "nope", "b", default="d") == "d"
    assert dig(data, "a", "b", "deeper") is None  # 1 isn't a dict
    assert num(data, "a", "s") == 2.5 and num(data, "a", "t") == 0 and num(data, "a", "x") == 0
    assert text(data, "a", "x") == "abc" and text(data, "a", "b") == ""
    assert each(data, "l") == [{"k": 1}]
    assert each({"d": {"1": {"v": 2}, "0": {"v": 1}}}, "d") == [{"v": 1}, {"v": 2}]
    assert each(data, "a", "b") == []


# The nodes of a cluster and their jobs: GET …/clusters/{cluster}/status.

STATUS = {
    "nodes": {
        "gros-10.nancy.grid5000.fr": {"hard": "dead", "soft": "unknown", "reservations": []},
        "gros-2.nancy.grid5000.fr": {
            "hard": "alive",
            "soft": "busy",
            "reservations": [
                {"uid": 4600, "user": "eve", "queue": "default", "state": "Waiting", "walltime": 3600,
                 "started_at": None, "scheduled_at": 1800010000},
                {"uid": 4521, "user": "bob", "queue": "default", "state": "Running", "walltime": 7200,
                 "started_at": 1800000000, "scheduled_at": 1800000000},
                {"uid": 4700, "user": "x", "walltime": 3600, "started_at": None, "scheduled_at": None},  # not scheduled
            ],
        },
        "gros-1.nancy.grid5000.fr": {"hard": "alive", "soft": "free", "reservations": None},
        "junk": "not a node",
    },
    "disks": {},
}


def status_api(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/stable/sites/nancy/clusters/gros/status":
        return httpx.Response(200, json=STATUS)
    return httpx.Response(404, json={"message": "unknown cluster"})


async def test_nodes() -> None:
    c = Client("https://api.test/stable", transport=httpx.MockTransport(status_api))
    nodes = await c.nodes("nancy", "gros")
    assert [n.name for n in nodes] == ["gros-1", "gros-2", "gros-10"]  # by number, junk left out
    g1, g2, g10 = nodes
    assert (g1.hard, g1.soft, g1.reservations) == ("alive", "free", ())
    assert g10.hard == "dead"
    assert [r.job_id for r in g2.reservations] == [4521, 4600]  # by start; the unscheduled one left out
    running = g2.reservations[0]
    assert running.start == datetime.fromtimestamp(1800000000).astimezone()
    assert running.end - running.start == timedelta(hours=2)
    assert (running.user, running.queue, running.state) == ("bob", "default", "Running")


async def test_nodes_errors() -> None:
    c = Client("https://api.test/stable", transport=httpx.MockTransport(status_api))
    with pytest.raises(ApiError, match="404 Not Found: unknown cluster"):
        await c.nodes("nancy", "atlantis")
    with pytest.raises(ValueError):
        await c.nodes("", "gros")


async def test_site_nodes_is_one_call_for_the_whole_site() -> None:
    seen, queries = [], []

    def api(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        queries.append(request.url.query.decode())
        return httpx.Response(200, json=STATUS)

    nodes = await Client("https://api.test/stable", transport=httpx.MockTransport(api)).site_nodes("nancy")
    assert seen == ["/stable/sites/nancy/status"]
    assert queries == ["disks=no"]  # the disks aren't read: they aren't asked for
    assert [n.name for n in nodes] == ["gros-1", "gros-2", "gros-10"]
    with pytest.raises(ValueError):
        await Client().site_nodes("")
