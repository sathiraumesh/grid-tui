"""What every Grid'5000 API call needs: the address, the login, and GET.

On a Grid'5000 frontend no login is needed. From anywhere else the API wants
HTTP basic auth with your Grid'5000 login, read from the environment:

    G5K_USER, G5K_PASSWORD   your Grid'5000 login
    G5K_API                  the API root (default: DEFAULT_BASE_URL)

Any of these not set in the environment is read from a secret folder instead,
one file per variable holding its value base64-encoded:

    ~/.grid-secret/G5K_USER        e.g. made with: printf alice | base64
    ~/.grid-secret/G5K_PASSWORD
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import os
import time
from pathlib import Path
from typing import Any, TypeVar

import httpx

from grid_tui.grid5000.cache import Cache

DEFAULT_BASE_URL = 'https://api.grid5000.fr/stable'
SECRET_DIR_NAME = '.grid-secret'
SETTING_NAMES = ('G5K_API', 'G5K_USER', 'G5K_PASSWORD')

ClientT = TypeVar('ClientT', bound='BaseClient')  # from_env makes the same class


def find_secret_dir() -> Path:
    """The secret folder: ~/.grid-secret in your home folder."""
    return Path.home() / SECRET_DIR_NAME


def read_secrets(folder: Path | None) -> dict[str, str]:
    """The settings found in folder, each file's base64 contents decoded.

    Args:
        folder: The secret folder; None (or a missing folder) gives {}.

    Raises:
        ValueError: A file there is not valid base64 (or not UTF-8 inside).
    """
    secrets = {}
    if folder is None or not folder.is_dir():
        return secrets
    for name in SETTING_NAMES:
        path = folder / name
        if not path.is_file():
            continue
        try:
            raw = base64.b64decode(path.read_text().strip(), validate=True)
            secrets[name] = raw.decode('utf-8').strip()
        except (binascii.Error, UnicodeDecodeError) as error:
            raise ValueError(f'{path}: not valid base64 ({error})') from error
    return secrets


def settings_from_env(secret_dir: Path | None = None) -> dict[str, str]:
    """The API address and login, from G5K_API, G5K_USER and G5K_PASSWORD.

    Each is taken from the environment if set there, else from the secret
    folder (~/.grid-secret), else left at its default.

    Args:
        secret_dir: The secret folder to read; None means ~/.grid-secret.
    """
    secrets = read_secrets(secret_dir or find_secret_dir())

    def get(name: str) -> str:
        return os.environ.get(name) or secrets.get(name, '')

    return {
        'base_url': get('G5K_API') or DEFAULT_BASE_URL,
        'user': get('G5K_USER'),
        'password': get('G5K_PASSWORD'),
    }


class ApiError(Exception):
    """The API answered with an error."""

    def __init__(
        self, path: str, status: int, method: str = 'GET', detail: str = ''
    ) -> None:
        """Make the error.

        Args:
            path: The API path that was asked for, e.g. '/sites'.
            status: The HTTP status the API answered with, e.g. 401.
            method: The request's method, e.g. 'POST'.
            detail: What the API said was wrong, if it said (e.g. why a job
                was refused).
        """
        self.path = path
        self.status = status
        self.detail = detail
        reason = httpx.codes.get_reason_phrase(status)
        message = f'{method} {path}: {status} {reason}'
        if detail:
            message += f': {detail}'
        if status == 401:
            message += (
                " (outside Grid'5000, set G5K_USER and G5K_PASSWORD"
                f' or put them in ~/{SECRET_DIR_NAME}/)'
            )
        super().__init__(message)


def error_detail(response: httpx.Response) -> str:
    """What the API said was wrong, in a line: its message, else its text."""
    try:
        answer = response.json()
    except ValueError:
        return response.text.strip()[:300]
    if isinstance(answer, dict):
        for key in ('message', 'error', 'title'):
            if answer.get(key):
                return str(answer[key])[:300]
    return ''


async def _wait_for(request: asyncio.Future) -> Any:
    """Wait for a shared request's answer; giving up doesn't cancel it.

    Like asyncio.shield, but a request that fails after you gave up isn't
    logged as an error nobody saw: whoever asks next gets it (or a new try).
    """
    mine = asyncio.get_running_loop().create_future()

    def copy(done: asyncio.Future) -> None:
        if mine.done():
            return  # you gave up
        if done.cancelled():
            mine.cancel()
        elif done.exception() is not None:
            mine.set_exception(done.exception())
        else:
            mine.set_result(done.result())

    request.add_done_callback(copy)
    try:
        return await mine
    finally:
        request.remove_done_callback(copy)


class Connection:
    """One connection to the API, shared by a Client's parts.

    - It stays open between requests (keep-alive), so each request doesn't
      pay for a new TLS handshake.
    - The same GET asked for twice at once is sent once; both get the answer.
    - An answer asked for with fresh_for is kept in memory that long, so a
      repeat within it isn't sent at all.
    """

    def __init__(
        self,
        base_url: str,
        user: str,
        password: str,
        transport: httpx.AsyncBaseTransport | None,
        timeout: float,
    ) -> None:
        """Get ready to connect (the connection opens on the first request)."""
        self.base_url = base_url
        self.auth = httpx.BasicAuth(user, password) if user else None
        self.transport = transport
        self.timeout = timeout
        self.sent = 0  # how many requests went to the API (for tests, stats)
        self._http: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._memory: dict[str, tuple[float, Any]] = {}  # key → (until, answer)
        self._waiting: dict[str, asyncio.Future] = {}  # key → the request on its way

    def _client(self) -> httpx.AsyncClient:
        """The open connection; a new one if there's none on this event loop."""
        loop = asyncio.get_running_loop()
        if self._http is None or self._loop is not loop or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                auth=self.auth,
                timeout=self.timeout,
                transport=self.transport,
                headers={'Accept': 'application/json'},
            )
            self._loop = loop
            self._waiting.clear()
        return self._http

    async def get(self, path: str, fresh_for: float = 0, refresh: bool = False) -> Any:
        """GET path and return the JSON answer, sharing and remembering answers.

        Args:
            path: The API path, e.g. '/sites/nancy/status'.
            fresh_for: Keep the answer this many seconds; a repeat within it
                is answered from memory. 0 keeps nothing.
            refresh: Ask the API even if a remembered answer is still fresh.
        """
        now = time.monotonic()
        if fresh_for and not refresh:
            remembered = self._memory.get(path)
            if remembered is not None and remembered[0] > now:
                return remembered[1]
        http = self._client()
        waiting = self._waiting.get(path)
        if waiting is None:
            # the request runs on its own: if whoever asked gives up (e.g.
            # you moved to another site), it still finishes, and its answer
            # is remembered for the next to ask, instead of starting over
            waiting = asyncio.ensure_future(self._send(http, path, fresh_for))
            self._waiting[path] = waiting
            waiting.add_done_callback(lambda done: self._done(path, done))
        return await _wait_for(waiting)

    async def _send(self, http: httpx.AsyncClient, path: str, fresh_for: float) -> Any:
        """Send one GET, and remember its answer for fresh_for seconds."""
        self.sent += 1
        response = await http.get(path)
        if not response.is_success:
            raise ApiError(path, response.status_code)
        answer = response.json()
        if fresh_for:
            self._memory[path] = (time.monotonic() + fresh_for, answer)
        return answer

    def _done(self, path: str, request: asyncio.Future) -> None:
        """A request finished: it's no longer on its way."""
        if self._waiting.get(path) is request:
            del self._waiting[path]
        if not request.cancelled():
            request.exception()  # marked as seen: no warning if nobody waited

    async def send(self, method: str, path: str, body: Any = None) -> Any:
        """Send a request that changes something (POST, DELETE): never shared
        nor remembered.

        Args:
            method: 'POST' or 'DELETE'.
            path: The API path, e.g. '/sites/nancy/jobs'.
            body: The JSON to send, if any.

        Returns:
            The JSON answer; None if the answer has none.
        """
        http = self._client()
        self.sent += 1
        response = await http.request(method, path, json=body)
        if not response.is_success:
            raise ApiError(path, response.status_code, method, error_detail(response))
        try:
            return response.json()
        except ValueError:
            return None

    def forget(self, prefix: str) -> None:
        """Forget the remembered answers whose path starts with prefix, e.g.
        a site's after you reserved there: the next ask gets the news."""
        for path in [path for path in self._memory if path.startswith(prefix)]:
            del self._memory[path]

    async def aclose(self) -> None:
        """Stop the requests still on their way, and close the connection."""
        for request in list(self._waiting.values()):
            request.cancel()
        self._waiting.clear()
        if self._http is not None:
            await self._http.aclose()
            self._http = None


class BaseClient:
    """Connects to the Grid'5000 API. The other clients build on this."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user: str = '',
        password: str = '',
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake one
        timeout: float = 30.0,
        cache: Cache | None = None,
        connection: Connection | None = None,
    ) -> None:
        """Make the client.

        Args:
            base_url: The API root, e.g. 'https://api.grid5000.fr/stable'.
            user: Your Grid'5000 login; '' on a frontend, where none is needed.
            password: Your Grid'5000 password.
            transport: What sends the requests; tests give a fake one.
            timeout: How many seconds to wait for an answer.
            cache: Where to save answers asked for with cached=True; None
                saves nothing (tests leave it out).
            connection: The connection to share with other parts; None
                opens its own.
        """
        self.base_url = base_url.rstrip('/')
        self.user = user
        self.password = password
        self._transport = transport
        self._timeout = timeout
        self.cache = cache
        self.connection = connection or Connection(
            self.base_url, user, password, transport, timeout
        )

    @classmethod
    def from_env(cls: type[ClientT]) -> ClientT:
        """A client set up from G5K_API, G5K_USER and G5K_PASSWORD, with a cache."""
        return cls(**settings_from_env(), cache=Cache())

    async def _get(
        self,
        path: str,
        *,
        cached: bool = False,
        refresh: bool = False,
        fresh_for: float = 0,
    ) -> Any:
        """GET path and return the JSON answer.

        Args:
            path: The API path, e.g. '/sites'.
            cached: Use the saved answer if there is one, and save new ones.
                Only for answers that hardly change, like the sites.
            refresh: Ask the API even if an answer is saved or remembered, and
                save the new one (the r key).
            fresh_for: For answers that change: remember it this many seconds
                in memory, so a repeat within it isn't sent again.
        """
        key = self.base_url + path  # another API root has its own answers
        if cached and self.cache is not None and not refresh:
            saved = self.cache.get(key)
            if saved is not None:
                return saved
        answer = await self.connection.get(path, fresh_for, refresh)
        if cached and self.cache is not None:
            self.cache.put(key, answer)
        return answer
