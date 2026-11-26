"""What the nodes are doing now: GET /sites/{site}/status.

Never saved to disk: it changes every minute. An answer is remembered in
memory for FRESH_FOR seconds (the API's own max-age), so the same question
asked again within it isn't sent.
"""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models.reservation import Schedule
from grid_tui.models.site import Site
from grid_tui.models.usage import Usage

# leave out each node's jobs and the site's disks: ~50 KB instead of ~750 KB
LIGHT = '?disks=no&job_details=no&waiting=no'
FRESH_FOR = 60  # seconds an answer is remembered: the API's max-age


class StatusClient(BaseClient):
    """The calls about what the nodes are doing now."""

    async def site_usage(self, site: str, *, refresh: bool = False) -> Usage:
        """How busy one site's nodes are, e.g. await site_usage('nancy').

        Args:
            site: The site.
            refresh: Ask the API even if it was asked within FRESH_FOR.
        """
        answer = await self._get(
            f'/sites/{quote(site, safe="")}/status{LIGHT}',
            fresh_for=FRESH_FOR,
            refresh=refresh,
        )
        return Usage.from_status(answer)

    async def schedule(
        self, site: str, cluster: str, *, refresh: bool = False
    ) -> Schedule:
        """A cluster's nodes and their reservations, now and to come.

        Args:
            site: The site, e.g. 'nancy'.
            cluster: The cluster, e.g. 'gros'.
            refresh: Ask the API even if it was asked within FRESH_FOR.
        """
        path = (
            f'/sites/{quote(site, safe="")}/clusters/{quote(cluster, safe="")}'
            '/status?disks=no'
        )
        answer = await self._get(path, fresh_for=FRESH_FOR, refresh=refresh)
        return Schedule.from_status(answer)

    async def usage_by_site(self, *, refresh: bool = False) -> dict[str, Usage]:
        """How busy each site is: {'nancy': Usage(...), 'lyon': ...}.

        A site whose status can't be loaded is left out; if none can be, the
        first error is raised.
        """
        data = await self._get('/sites', cached=True)  # the sites hardly change
        sites = [Site.model_validate(item).uid for item in data.get('items', [])]
        answers = await asyncio.gather(
            *(self.site_usage(site, refresh=refresh) for site in sites),
            return_exceptions=True,
        )
        by_site = {
            site: answer
            for site, answer in zip(sites, answers)
            if isinstance(answer, Usage)
        }
        errors = [a for a in answers if isinstance(a, BaseException)]
        if errors and not by_site:
            raise errors[0]
        return by_site

    async def usage(self, site: str | None = None) -> Usage:
        """How busy one site is, or all of Grid'5000 (every site together).

        Args:
            site: The site, e.g. 'nancy'; None for every site (see
                usage_by_site for what happens when some can't be loaded).
        """
        if site is not None:
            return await self.site_usage(site)
        return sum((await self.usage_by_site()).values(), Usage())
