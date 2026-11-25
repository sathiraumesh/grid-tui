"""The Grid'5000 sites: GET /sites."""

from __future__ import annotations  # so list[...] below means the type, not our list()

import asyncio
from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models import Site
from grid_tui.models.cluster import Cluster


class SitesClient(BaseClient):
    """The calls about sites."""

    async def list(self) -> list[Site]:
        """Every Grid'5000 site."""
        data = await self._get('/sites')
        return [Site.model_validate(item) for item in data.get('items', [])]

    async def list_clusters(self, site: str) -> list[Cluster]:
        """The clusters of one site, e.g. await list_clusters('nancy')."""
        data = await self._get(f'/sites/{quote(site, safe="")}/clusters')
        return [Cluster.model_validate(item) for item in data.get('items', [])]

    async def get_cluster(self, site: str, cluster: str) -> Cluster:
        """One cluster of a site, e.g. await get_cluster('nancy', 'gros')."""
        path = f'/sites/{quote(site, safe="")}/clusters/{quote(cluster, safe="")}'
        return Cluster.model_validate(await self._get(path))

    async def all_clusters(self) -> dict[str, list[Cluster]]:
        """The clusters of every site, by site: {'nancy': [...], 'lyon': [...]}."""
        sites = await self.list()
        answers = await asyncio.gather(*(self.list_clusters(s.uid) for s in sites))
        return {site.uid: clusters for site, clusters in zip(sites, answers)}
