import pytest

from grid_tui.grid5000 import ApiError, SitesClient
from grid_tui.models import Cluster, Site
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
    client = SitesClient(transport=fake_api(json=SITES_ANSWER))
    assert await client.list() == [
        Site(uid='nancy', name='Nancy', description='Grid5000 Nancy site'),
        Site(uid='lyon', name='Lyon', description='Grid5000 Lyon site'),
    ]


async def test_sites_calls_the_sites_path():
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list()
    assert seen[0].url.path == '/stable/sites'


async def test_missing_fields_become_empty():
    client = SitesClient(transport=fake_api(json={'items': [{'uid': 'rennes'}]}))
    assert await client.list() == [Site(uid='rennes')]


# The clusters of the sites


async def test_list_clusters_reads_one_sites_clusters():
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    clusters = await client.list_clusters('nancy')
    assert [c.uid for c in clusters] == ['gros', 'grisou']
    assert clusters[0] == Cluster(
        uid='gros', model='Dell R640', queues=('default',), kavlan=True
    )


async def test_list_clusters_calls_the_sites_clusters_path():
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list_clusters('nancy')
    assert seen[0].url.path == '/stable/sites/nancy/clusters'


async def test_list_clusters_escapes_the_site_name():
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.list_clusters('a/b')  # can't reach another path
    assert seen[0].url.raw_path == b'/stable/sites/a%2Fb/clusters'


async def test_list_clusters_of_an_unknown_site_raises():
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    with pytest.raises(ApiError) as error:
        await client.list_clusters('nowhere')
    assert error.value.status == 404


async def test_all_clusters_gives_every_sites_clusters_by_site():
    client = SitesClient(transport=fake_grid5000(SITES, CLUSTERS))
    by_site = await client.all_clusters()
    assert list(by_site) == ['nancy', 'lyon']  # in the order of the sites
    assert [c.uid for c in by_site['nancy']] == ['gros', 'grisou']
    assert [c.uid for c in by_site['lyon']] == ['nova']


async def test_all_clusters_with_no_sites_is_empty():
    client = SitesClient(transport=fake_grid5000())
    assert await client.all_clusters() == {}


async def test_all_clusters_fails_if_one_site_fails():
    sites = [*SITES, {'uid': 'nowhere'}]  # no clusters answer for this one
    client = SitesClient(transport=fake_grid5000(sites, CLUSTERS))
    with pytest.raises(ApiError):
        await client.all_clusters()
