"""Settings for every test."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _cache_in_a_temp_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep any cache a test makes (e.g. through from_env) out of ~/.cache."""
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
