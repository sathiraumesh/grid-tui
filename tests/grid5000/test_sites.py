"""Tests for SitesClient: the sites, and the clusters of each site."""

import pytest

from grid_tui.grid5000 import ApiError, SitesClient
from grid_tui.models import Site
from tests.grid5000.fakes import CLUSTERS, SITES, fake_api, fake_grid5000

SITES_ANSWER = {
    'items': [
        {'uid': 'nancy', 'name': 'Nancy', 'description': 'Grid5000 Nancy site'},
        {'uid': 'lyon', 'name': 'Lyon', 'description': 'Grid5000 Lyon site'},
    ],
    'total': 2,
    'offset': 0,
}


async def test_sites_reads_the_list():
    """list() turns the API's items into Sites."""
    client = SitesClient(transport=fake_api(json=SITES_ANSWER))
    assert await client.list() == [
        Site(uid='nancy', name='Nancy', description='Grid5000 Nancy site'),
        Site(uid='lyon', name='Lyon', description='Grid5000 Lyon site'),
    ]


async def test_sites_calls_the_sites_path():
    """list() asks for /sites."""
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list()
    assert seen[0].url.path == '/stable/sites'


async def test_missing_fields_become_empty():
    """A site with only a uid gets '' for the rest."""
    client = SitesClient(transport=fake_api(json={'items': [{'uid': 'rennes'}]}))
    assert await client.list() == [Site(uid='rennes')]


# The clusters of the sites


async def test_list_clusters_reads_one_sites_clusters():
    """list_clusters() turns one site's items into Clusters."""
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    clusters = await client.list_clusters('nancy')
    assert [c.uid for c in clusters] == ['gros', 'grisou']
    gros = clusters[0]
    assert (gros.model, gros.queues, gros.kavlan) == ('Dell R640', ('default',), True)
    assert gros.metric_names == ('wattmetre_power_watt', 'bmc_node_power_watt')


async def test_list_clusters_calls_the_sites_clusters_path():
    """list_clusters('nancy') asks for /sites/nancy/clusters."""
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list_clusters('nancy')
    assert seen[0].url.path == '/stable/sites/nancy/clusters'


async def test_list_clusters_escapes_the_site_name():
    """A site name can't change which path is asked for."""
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list_clusters('a/b')  # can't reach another path
    assert seen[0].url.raw_path == b'/stable/sites/a%2Fb/clusters'


async def test_list_clusters_of_an_unknown_site_raises():
    """A site the API doesn't know raises ApiError (404)."""
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    with pytest.raises(ApiError) as error:
        await client.list_clusters('nowhere')
    assert error.value.status == 404


async def test_all_clusters_gives_every_sites_clusters_by_site():
    """all_clusters() gives each site's clusters, in the order of the sites."""
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    by_site = await client.all_clusters()
    assert list(by_site) == ['nancy', 'lyon']  # in the order of the sites
    assert [c.uid for c in by_site['nancy']] == ['gros', 'grisou']
    assert [c.uid for c in by_site['lyon']] == ['nova']


async def test_all_clusters_with_no_sites_is_empty():
    """With no sites, all_clusters() gives {}."""
    client = SitesClient(transport=fake_grid5000())
    assert await client.all_clusters() == {}


async def test_all_clusters_fails_if_one_site_fails():
    """If one site's clusters fail to load, all_clusters() raises."""
    sites = [*SITES, {'uid': 'nowhere'}]  # no clusters answer for this one
    client = SitesClient(transport=fake_grid5000(sites, CLUSTERS))
    with pytest.raises(ApiError):
        await client.all_clusters()


async def test_get_cluster_reads_one_cluster():
    """get_cluster() gives the one cluster asked for, with its metrics."""
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    gros = await client.get_cluster('nancy', 'gros')
    assert gros.uid == 'gros'
    assert gros.metric_names == ('wattmetre_power_watt', 'bmc_node_power_watt')


async def test_get_cluster_calls_the_clusters_path():
    """get_cluster('nancy', 'gros') asks for /sites/nancy/clusters/gros."""
    seen = []
    client = SitesClient(transport=fake_api(json={'uid': 'gros'}, seen=seen))
    await client.get_cluster('nancy', 'gros')
    assert seen[0].url.path == '/stable/sites/nancy/clusters/gros'


async def test_get_cluster_of_an_unknown_cluster_raises():
    """A cluster the API doesn't know raises ApiError (404)."""
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    with pytest.raises(ApiError) as error:
        await client.get_cluster('nancy', 'nowhere')
    assert error.value.status == 404
