"""The Grid'5000 sites: GET /sites."""

from __future__ import annotations  # so list[...] below means the type, not our list()

import asyncio
from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models import Site
from grid_tui.models.cluster import Cluster


class SitesClient(BaseClient):
    """The calls about sites."""

    async def list(self, *, refresh: bool = False) -> list[Site]:
        """Every Grid'5000 site. Saved in the cache after the first time.

        Args:
            refresh: Ask the API again instead of using the cache.
        """
        data = await self._get('/sites', cached=True, refresh=refresh)
        return [Site.model_validate(item) for item in data.get('items', [])]

    async def list_clusters(self, site: str, *, refresh: bool = False) -> list[Cluster]:
        """The clusters of one site, e.g. await list_clusters('nancy'). Cached.

        Args:
            site: The site's uid, e.g. 'nancy'.
            refresh: Ask the API again instead of using the cache.
        """
        path = f'/sites/{quote(site, safe="")}/clusters'
        data = await self._get(path, cached=True, refresh=refresh)
        return [Cluster.model_validate(item) for item in data.get('items', [])]

    async def get_cluster(
        self, site: str, cluster: str, *, refresh: bool = False
    ) -> Cluster:
        """One cluster of a site, e.g. await get_cluster('nancy', 'gros'). Cached.

        Args:
            site: The site's uid, e.g. 'nancy'.
            cluster: The cluster's uid, e.g. 'gros'.
            refresh: Ask the API again instead of using the cache.
        """
        path = f'/sites/{quote(site, safe="")}/clusters/{quote(cluster, safe="")}'
        return Cluster.model_validate(
            await self._get(path, cached=True, refresh=refresh)
        )

    async def all_clusters(self, *, refresh: bool = False) -> dict[str, list[Cluster]]:
        """The clusters of every site, by site: {'nancy': [...], 'lyon': [...]}.

        Args:
            refresh: Ask the API again for the sites and every site's clusters.
        """
        sites = await self.list(refresh=refresh)
        answers = await asyncio.gather(
            *(self.list_clusters(s.uid, refresh=refresh) for s in sites)
        )
        return {site.uid: clusters for site, clusters in zip(sites, answers)}
