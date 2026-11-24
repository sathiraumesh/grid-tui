from grid_tui.grid5000 import Client, SitesClient
from grid_tui.models import Site
from tests.grid5000.fakes import fake_api


def test_has_the_sites_part():
    assert isinstance(Client().sites, SitesClient)


async def test_sites_part_uses_the_clients_settings():
    seen = []
    client = Client(
        'https://api.example/stable',
        user='alice',
        password='secret',
        transport=fake_api(json={'items': [{'uid': 'nancy'}]}, seen=seen),
    )
    assert await client.sites.list() == [Site(uid='nancy')]
    assert str(seen[0].url) == 'https://api.example/stable/sites'
    assert seen[0].headers['Authorization'].startswith('Basic ')


def test_from_env(monkeypatch):
    monkeypatch.setenv('G5K_API', 'https://api.example/stable')
    monkeypatch.setenv('G5K_USER', 'alice')
    monkeypatch.setenv('G5K_PASSWORD', 'secret')
    client = Client.from_env()
    assert client.sites.base_url == 'https://api.example/stable'
    assert client.sites.user == 'alice'
