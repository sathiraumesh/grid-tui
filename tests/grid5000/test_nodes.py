"""Tests for NodesClient: the nodes of a cluster, and one node."""

import pytest

from grid_tui.grid5000 import ApiError, NodesClient
from grid_tui.grid5000.nodes import nodes_path
from grid_tui.models import Node
from tests.grid5000.fakes import NODES, fake_api, fake_grid5000, g5k_client


def client(status: int = 200) -> NodesClient:
    """A NodesClient talking to the fake API with NODES."""
    return NodesClient(transport=fake_grid5000(status=status, nodes=NODES))


def test_nodes_path():
    """nodes_path builds the path of a cluster's nodes."""
    assert nodes_path('nancy', 'gros') == '/sites/nancy/clusters/gros/nodes'


def test_nodes_path_escapes_the_names():
    """A site or cluster name can't change which path is asked for."""
    assert nodes_path('a/b', 'c?d') == '/sites/a%2Fb/clusters/c%3Fd/nodes'


async def test_list_reads_every_node_of_a_cluster():
    """list() turns a cluster's items into Nodes, with their hardware."""
    nodes = await client().list('nancy', 'gros')
    assert [node.uid for node in nodes] == ['gros-1', 'gros-2']
    assert nodes[0].architecture.nb_cores == 18
    assert nodes[0].processor.name == 'Intel Xeon Gold 5220'
    assert nodes[0].main_memory.gib == 96.0
    assert nodes[1] == Node(uid='gros-2', cluster='gros')


async def test_list_calls_the_clusters_nodes_path():
    """list('nancy', 'gros') asks for /sites/nancy/clusters/gros/nodes."""
    seen = []
    await NodesClient(transport=fake_api(seen=seen)).list('nancy', 'gros')
    assert seen[0].url.path == '/stable/sites/nancy/clusters/gros/nodes'


async def test_list_of_a_cluster_with_no_nodes_is_empty():
    """An answer with no items gives no nodes."""
    nodes_client = NodesClient(transport=fake_api(json={'items': []}))
    assert await nodes_client.list('nancy', 'gros') == []


async def test_list_of_an_unknown_cluster_raises():
    """A cluster the API doesn't know raises ApiError (404)."""
    with pytest.raises(ApiError) as error:
        await client().list('nancy', 'nowhere')
    assert error.value.status == 404


async def test_get_reads_one_node():
    """get() gives the one node asked for."""
    node = await client().get('nancy', 'gros', 'gros-1')
    assert node.uid == 'gros-1'
    assert node.architecture.nb_threads == 36


async def test_get_calls_the_nodes_path():
    """get('nancy', 'gros', 'gros-1') asks for .../nodes/gros-1."""
    seen = []
    nodes_client = NodesClient(transport=fake_api(json={'uid': 'gros-1'}, seen=seen))
    await nodes_client.get('nancy', 'gros', 'gros-1')
    assert seen[0].url.path == '/stable/sites/nancy/clusters/gros/nodes/gros-1'


async def test_get_escapes_the_node_name():
    """A node name can't change which path is asked for."""
    seen = []
    nodes_client = NodesClient(transport=fake_api(json={'uid': 'x'}, seen=seen))
    await nodes_client.get('nancy', 'gros', '../x')
    assert seen[0].url.raw_path == b'/stable/sites/nancy/clusters/gros/nodes/..%2Fx'


async def test_get_of_an_unknown_node_raises():
    """A node the API doesn't know raises ApiError (404)."""
    with pytest.raises(ApiError) as error:
        await client().get('nancy', 'gros', 'gros-99')
    assert error.value.status == 404


async def test_an_error_answer_raises():
    """A 401 (no login) raises ApiError and says how to log in."""
    with pytest.raises(ApiError) as error:
        await client(status=401).list('nancy', 'gros')
    assert error.value.status == 401
    assert 'G5K_USER' in str(error.value)


async def test_the_client_has_the_nodes_calls():
    """Client.nodes works against the same fake API."""
    nodes = await g5k_client().nodes.list('nancy', 'gros')
    assert [node.uid for node in nodes] == ['gros-1', 'gros-2']
