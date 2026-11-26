"""The nodes of a Grid'5000 cluster: GET /sites/{site}/clusters/{cluster}/nodes."""

from __future__ import annotations  # so list[...] below means the type, not our list()

from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models import Node


def nodes_path(site: str, cluster: str) -> str:
    """The API path of a cluster's nodes, with the names escaped.

    nodes_path('nancy', 'gros') → '/sites/nancy/clusters/gros/nodes'. Escaping
    means a name can't change which path is asked for.
    """
    return f'/sites/{quote(site, safe="")}/clusters/{quote(cluster, safe="")}/nodes'


class NodesClient(BaseClient):
    """The calls about nodes."""

    async def list(
        self, site: str, cluster: str, *, refresh: bool = False
    ) -> list[Node]:
        """Every node of a cluster, with its hardware. Cached.

        Args:
            site: The site's uid, e.g. 'nancy'.
            cluster: The cluster's uid, e.g. 'gros'.
            refresh: Ask the API again instead of using the cache.
        """
        data = await self._get(nodes_path(site, cluster), cached=True, refresh=refresh)
        return [Node.model_validate(item) for item in data.get('items', [])]

    async def get(
        self, site: str, cluster: str, node: str, *, refresh: bool = False
    ) -> Node:
        """One node, with its hardware. Cached.

        Args:
            site: The site's uid, e.g. 'nancy'.
            cluster: The cluster's uid, e.g. 'gros'.
            node: The node's uid, e.g. 'gros-12'.
            refresh: Ask the API again instead of using the cache.
        """
        path = f'{nodes_path(site, cluster)}/{quote(node, safe="")}'
        return Node.model_validate(await self._get(path, cached=True, refresh=refresh))
