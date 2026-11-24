import pytest

from grid_tui.grid5000 import ApiError, BaseClient
from tests.grid5000.fakes import fake_api


async def test_get_calls_the_path_under_the_base_url():
    seen = []
    client = BaseClient('https://api.example/stable/', transport=fake_api(seen=seen))
    await client._get('/sites')
    assert str(seen[0].url) == 'https://api.example/stable/sites'


async def test_get_returns_the_json():
    client = BaseClient(transport=fake_api(json={'items': []}))
    assert await client._get('/sites') == {'items': []}


async def test_sends_login_when_given():
    seen = []
    client = BaseClient(user='alice', password='secret', transport=fake_api(seen=seen))
    await client._get('/sites')
    assert seen[0].headers['Authorization'].startswith('Basic ')


async def test_no_login_on_a_frontend():
    seen = []
    client = BaseClient(transport=fake_api(seen=seen))
    await client._get('/sites')
    assert 'Authorization' not in seen[0].headers


async def test_error_answer_raises():
    client = BaseClient(transport=fake_api(status=401))
    with pytest.raises(ApiError) as error:
        await client._get('/sites')
    assert error.value.status == 401
    assert 'G5K_USER' in str(error.value)


def test_from_env(monkeypatch):
    monkeypatch.setenv('G5K_API', 'https://api.example/stable')
    monkeypatch.setenv('G5K_USER', 'alice')
    monkeypatch.setenv('G5K_PASSWORD', 'secret')
    client = BaseClient.from_env()
    assert client.base_url == 'https://api.example/stable'
    assert client.user == 'alice'
    assert client.password == 'secret'
