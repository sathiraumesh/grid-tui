"""A Grid'5000 site."""

from pydantic import BaseModel, ConfigDict, field_validator


class Site(BaseModel):
    """One Grid'5000 site, as GET /sites lists it."""

    model_config = ConfigDict(frozen=True)  # can't be changed once made

    uid: str  # e.g. 'nancy': used in every API path
    name: str = ''  # e.g. 'Nancy'
    description: str = ''  # e.g. 'Grid5000 Nancy site'

    @field_validator('name', 'description', mode='before')
    @classmethod
    def _null_is_empty(cls, value):
        """The API sometimes sends null: read it as ''."""
        return '' if value is None else value
