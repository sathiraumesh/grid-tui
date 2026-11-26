"""What the nodes are doing now: GET /sites/{site}/status.

Never cached: it changes every minute.
"""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from grid_tui.grid5000.base import BaseClient
from grid_tui.models.site import Site
from grid_tui.models.usage import Usage

# leave out each node's jobs and the site's disks: ~50 KB instead of ~750 KB
LIGHT = '?disks=no&job_details=no&waiting=no'


class StatusClient(BaseClient):
    """The calls about what the nodes are doing now."""

    async def site_usage(self, site: str) -> Usage:
        """How busy one site's nodes are, e.g. await site_usage('nancy')."""
        answer = await self._get(f'/sites/{quote(site, safe="")}/status{LIGHT}')
        return Usage.from_status(answer)

    async def usage(self, site: str | None = None) -> Usage:
        """How busy one site is, or all of Grid'5000 (every site together).

        Args:
            site: The site, e.g. 'nancy'; None for every site. With every
                site, one whose status can't be loaded is left out; if none
                can be, the first error is raised.
        """
        if site is not None:
            return await self.site_usage(site)
        data = await self._get('/sites', cached=True)  # the sites hardly change
        sites = [Site.model_validate(item) for item in data.get('items', [])]
        answers = await asyncio.gather(
            *(self.site_usage(site.uid) for site in sites), return_exceptions=True
        )
        counts = [a for a in answers if isinstance(a, Usage)]
        errors = [a for a in answers if isinstance(a, BaseException)]
        if errors and not counts:
            raise errors[0]
        return sum(counts, Usage())
