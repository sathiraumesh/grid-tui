import httpx
import pytest

from grid_tui.grid5000 import DEFAULT_BASE_URL, ApiError, Client
from grid_tui.grid5000.client import clusters_path
from grid_tui.models import Cluster, Site

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
