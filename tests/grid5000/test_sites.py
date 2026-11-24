from grid_tui.grid5000 import SitesClient
from grid_tui.models import Site
from tests.grid5000.fakes import fake_api

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
    assert await client.sites() == [
        Site(uid='nancy', name='Nancy', description='Grid5000 Nancy site'),
        Site(uid='lyon', name='Lyon', description='Grid5000 Lyon site'),
    ]


async def test_sites_calls_the_sites_path():
    seen = []
    client = SitesClient(transport=fake_api(seen=seen))
    await client.sites()
    assert seen[0].url.path == '/stable/sites'


async def test_missing_fields_become_empty():
    client = SitesClient(transport=fake_api(json={'items': [{'uid': 'rennes'}]}))
    assert await client.sites() == [Site(uid='rennes')]
