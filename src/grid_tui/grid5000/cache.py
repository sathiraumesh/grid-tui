"""A local cache of API answers, in one SQLite file.

Sites, clusters and nodes hardly ever change, so after the first load their
answers are read from disk instead of the network. Reloading (the r key) asks
the API again and saves the new answer.

    cache = Cache()                         # ~/.cache/grid-tui/cache.db
    cache.put('/sites', {'items': [...]})
    cache.get('/sites')                     # {'items': [...]}, or None if not saved

The file is $XDG_CACHE_HOME/grid-tui/cache.db, or ~/.cache/grid-tui/cache.db.
Delete it to start again.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    path     TEXT PRIMARY KEY,  -- the API path, e.g. '/sites'
    body     TEXT NOT NULL,     -- the JSON answer
    saved_at REAL NOT NULL      -- when it was saved, in seconds since 1970
)
"""


def default_cache_path() -> Path:
    """Where the cache lives: $XDG_CACHE_HOME/grid-tui or ~/.cache/grid-tui."""
    root = os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache'
    return Path(root) / 'grid-tui' / 'cache.db'


class Cache:
    """API answers saved by path, in a SQLite file."""

    def __init__(self, path: Path | str | None = None) -> None:
        """Open the cache, making the file (and its folder) if needed.

        Args:
            path: The SQLite file; None for default_cache_path(). ':memory:'
                keeps it in memory only, for tests.
        """
        self.path = default_cache_path() if path is None else path
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.execute(SCHEMA)

    def get(self, path: str) -> Any | None:
        """The saved answer for an API path, or None if there is none."""
        row = self._db.execute(
            'SELECT body FROM answers WHERE path = ?', (path,)
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None  # a broken entry is as good as none: ask the API again

    def put(self, path: str, answer: Any) -> None:
        """Save the answer for an API path, replacing any older one."""
        with self._db:  # commits
            self._db.execute(
                'INSERT OR REPLACE INTO answers (path, body, saved_at) '
                'VALUES (?, ?, ?)',
                (path, json.dumps(answer), time.time()),
            )

    def clear(self) -> None:
        """Forget every saved answer."""
        with self._db:
            self._db.execute('DELETE FROM answers')

    def close(self) -> None:
        """Close the file."""
        self._db.close()
