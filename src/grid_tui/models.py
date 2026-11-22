"""The app's data. It knows nothing about the API or the screen."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    """One Grid'5000 site, as GET /sites lists it."""

    uid: str  # e.g. "nancy": used in every API path
    name: str = ""  # e.g. "Nancy"
    description: str = ""  # e.g. "Grid5000 Nancy site"
