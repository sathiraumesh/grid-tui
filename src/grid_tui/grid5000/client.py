"""The one client the app passes around: every part of the API in one place.

    client = Client.from_env()
    await client.sites.list()                          # every site
    await client.sites.list_clusters('nancy')          # a site's clusters
    await client.nodes.list('nancy', 'gros')           # a cluster's nodes
    await client.nodes.get('nancy', 'gros', 'gros-1')  # one node
    await client.status.usage()                        # how busy it all is now

To add a part, write it like sites.py and register it in __init__ below,
e.g. self.jobs = JobsClient(**settings).
"""

from __future__ import annotations

import httpx

from grid_tui.grid5000.base import DEFAULT_BASE_URL, settings_from_env
from grid_tui.grid5000.cache import Cache
from grid_tui.grid5000.jobs import JobsClient
from grid_tui.grid5000.nodes import NodesClient
from grid_tui.grid5000.sites import SitesClient
from grid_tui.grid5000.status import StatusClient


class Client:
    """Every part of the Grid'5000 API, all with the same address and login."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        user: str = '',
        password: str = '',
        *,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake one
        timeout: float = 30.0,
        cache: Cache | None = None,
    ) -> None:
        """Make the client and every part of it, all with these settings.

        Args:
            base_url: The API root, e.g. 'https://api.grid5000.fr/stable'.
            user: Your Grid'5000 login; '' on a frontend, where none is needed.
            password: Your Grid'5000 password.
            transport: What sends the requests; tests give a fake one.
            timeout: How many seconds to wait for an answer.
            cache: Where the parts save the answers that hardly change; one
                for them all. None saves nothing.
        """
        self.cache = cache
        settings = {
            'base_url': base_url,
            'user': user,
            'password': password,
            'transport': transport,
            'timeout': timeout,
            'cache': cache,
        }
        # the parts of the API
        self.sites = SitesClient(**settings)
        self.nodes = NodesClient(**settings)
        self.status = StatusClient(**settings)
        self.jobs = JobsClient(**settings)

    @classmethod
    def from_env(cls) -> Client:
        """A client set up from G5K_API, G5K_USER and G5K_PASSWORD, with a cache."""
        return cls(**settings_from_env(), cache=Cache())
