"""The Grid'5000 sites: GET /sites."""

from grid_tui.grid5000.base import BaseClient
from grid_tui.models import Site


class SitesClient(BaseClient):
    """The calls about sites."""

    async def list(self) -> list[Site]:
        """Every Grid'5000 site."""
        data = await self._get('/sites')
        return [Site.model_validate(item) for item in data.get('items', [])]
