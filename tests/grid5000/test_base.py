"""Tests for BaseClient: the address, the login, GET and errors."""

from pathlib import Path

import pytest

from grid_tui.grid5000 import ApiError, BaseClient
from tests.grid5000.fakes import fake_api


async def test_get_calls_the_path_under_the_base_url() -> None:
    """A path is asked for under the API root, with no double slash."""
    seen = []
    client = BaseClient('https://api.example/stable/', transport=fake_api(seen=seen))
    await client._get('/sites')
    assert str(seen[0].url) == 'https://api.example/stable/sites'


async def test_get_returns_the_json() -> None:
    """GET gives back the answer's JSON."""
    client = BaseClient(transport=fake_api(json={'items': []}))
    assert await client._get('/sites') == {'items': []}


async def test_sends_login_when_given() -> None:
    """With a user and password, every request carries basic auth."""
    seen = []
    client = BaseClient(user='alice', password='secret', transport=fake_api(seen=seen))
    await client._get('/sites')
    assert seen[0].headers['Authorization'].startswith('Basic ')


async def test_no_login_on_a_frontend() -> None:
    """With no user (on a frontend), no login is sent."""
    seen = []
    client = BaseClient(transport=fake_api(seen=seen))
    await client._get('/sites')
    assert 'Authorization' not in seen[0].headers


async def test_error_answer_raises() -> None:
    """An error answer raises ApiError, and a 401 says how to log in."""
    client = BaseClient(transport=fake_api(status=401))
    with pytest.raises(ApiError) as error:
        await client._get('/sites')
    assert error.value.status == 401
    assert 'G5K_USER' in str(error.value)


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """from_env reads the API root and the login from the environment."""
    monkeypatch.setenv('G5K_API', 'https://api.example/stable')
    monkeypatch.setenv('G5K_USER', 'alice')
    monkeypatch.setenv('G5K_PASSWORD', 'secret')
    client = BaseClient.from_env()
    assert client.base_url == 'https://api.example/stable'
    assert client.user == 'alice'
    assert client.password == 'secret'


def _write_secret(folder: Path, name: str, value: str) -> None:
    """Put value, base64-encoded, in folder/name."""
    import base64

    (folder / name).write_text(base64.b64encode(value.encode()).decode() + '\n')


def test_settings_from_the_secret_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With nothing in the environment, the login comes from the secret folder."""
    from grid_tui.grid5000.base import settings_from_env

    for name in ('G5K_API', 'G5K_USER', 'G5K_PASSWORD'):
        monkeypatch.delenv(name, raising=False)
    _write_secret(tmp_path, 'G5K_USER', 'alice')
    _write_secret(tmp_path, 'G5K_PASSWORD', 's3cret')
    settings = settings_from_env(tmp_path)
    assert settings['user'] == 'alice'
    assert settings['password'] == 's3cret'
    assert settings['base_url'] == 'https://api.grid5000.fr/stable'


def test_environment_wins_over_the_secret_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A variable set in the environment is used before the secret folder's."""
    from grid_tui.grid5000.base import settings_from_env

    monkeypatch.setenv('G5K_USER', 'bob')
    _write_secret(tmp_path, 'G5K_USER', 'alice')
    assert settings_from_env(tmp_path)['user'] == 'bob'


def test_secret_folder_is_in_the_home_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no folder given, the secret folder is ~/.grid-secret."""
    monkeypatch.delenv('G5K_USER', raising=False)
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    (tmp_path / '.grid-secret').mkdir()
    _write_secret(tmp_path / '.grid-secret', 'G5K_USER', 'alice')
    assert BaseClient.from_env().user == 'alice'


def test_bad_base64_in_the_secret_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that is not base64 says which one it is."""
    from grid_tui.grid5000.base import settings_from_env

    monkeypatch.delenv('G5K_USER', raising=False)
    (tmp_path / 'G5K_USER').write_text('not base64!!')
    with pytest.raises(ValueError, match='G5K_USER'):
        settings_from_env(tmp_path)
