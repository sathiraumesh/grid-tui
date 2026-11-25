"""A cluster of a Grid'5000 site."""

from pydantic import BaseModel, ConfigDict, field_validator


class Link(BaseModel):
    """A link the API gives to a related page, e.g. a cluster's nodes."""

    model_config = ConfigDict(frozen=True)

    rel: str = ''  # what it links to, e.g. 'self' or 'nodes'
    href: str = ''  # the API path, e.g. '/stable/sites/nancy/clusters/gros/nodes'


class Cluster(BaseModel):
    """One cluster of a site, as GET /sites/{site}/clusters lists it."""

    model_config = ConfigDict(frozen=True)  # can't be changed once made

    uid: str  # e.g. 'gros': used in every API path
    model: str = ''  # the machine model, e.g. 'Dell PowerEdge R640'
    created_at: str = ''  # when it joined, e.g. 'Thu, 01 Aug 2019 00:00:00 GMT'
    type: str = ''  # the kind of entry, e.g. 'cluster'
    version: str = ''  # the version of this description in the API
    queues: tuple[str, ...] = ()  # where jobs can go, e.g. ('default', 'admin')
    metrics: tuple[str, ...] = ()  # what can be measured, e.g. ('wattmetre_power',)
    exotic: bool = False  # unusual hardware: must be asked for by name
    kavlan: bool = False  # can its nodes be put in their own network (KaVLAN)
    links: tuple[Link, ...] = ()  # related API pages

    @field_validator('model', 'created_at', 'type', 'version', mode='before')
    @classmethod
    def _as_text(cls, value):
        """Null is ''; a number (version can be one) is read as its text."""
        if value is None:
            return ''
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value

    @field_validator('queues', 'links', mode='before')
    @classmethod
    def _null_is_empty_list(cls, value):
        """A missing or null list is an empty one."""
        return () if value is None else value

    @field_validator('metrics', mode='before')
    @classmethod
    def _metric_names(cls, value):
        """Keep only the metrics' names: [{'name': 'x', ...}] → ('x',)."""
        if not isinstance(value, list):
            return ()
        return tuple(
            m['name']
            for m in value
            if isinstance(m, dict) and isinstance(m.get('name'), str)
        )

    @field_validator('exotic', 'kavlan', mode='before')
    @classmethod
    def _null_is_false(cls, value):
        """A missing or null yes/no is no."""
        return False if value is None else value
