"""The connection to the Grid'5000 REST API (https://api.grid5000.fr)."""

from grid_tui.grid5000.client import DEFAULT_BASE_URL, ApiError, Client

__all__ = ["DEFAULT_BASE_URL", "ApiError", "Client"]
